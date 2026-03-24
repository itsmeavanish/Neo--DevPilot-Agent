"""
Planner module for JARVIS.

Uses LLM to create execution plans from natural language intents.
"""

import json
import re
from typing import Any

from jarvis.agent.models.plan import Plan, PlanStep
from jarvis.core.constants import RiskLevel, OnError, MAX_PLAN_STEPS
from jarvis.core.logging import get_logger
from jarvis.core.exceptions import PlanningError

logger = get_logger("jarvis.agent.planner")


# System prompt for planning
PLANNER_SYSTEM_PROMPT = """You are JARVIS, an autonomous developer assistant. Your task is to create execution plans.

Given a user's intent, create a step-by-step plan using available tools.

## Available Tools:
{tools_description}

## Output Format:
Return a JSON object with this structure:
```json
{{
  "reasoning": "Brief explanation of your approach",
  "steps": [
    {{
      "tool": "tool_name",
      "params": {{"param1": "value1"}},
      "description": "What this step does",
      "risk": "low|medium|high|critical"
    }}
  ]
}}
```

## Guidelines:
1. Break complex tasks into atomic steps
2. Use the minimum number of steps needed
3. Order steps logically (dependencies first)
4. Assess risk accurately:
   - LOW: Read-only operations
   - MEDIUM: Local file changes
   - HIGH: System changes, git push, docker operations
   - CRITICAL: Destructive operations
5. If a task cannot be done with available tools, explain why in reasoning and return empty steps
6. Maximum {max_steps} steps per plan

Return ONLY valid JSON, no markdown code blocks or extra text."""


class Planner:
    """
    Creates execution plans from natural language intents.

    Uses an LLM to:
    1. Parse the user's intent
    2. Select appropriate tools
    3. Generate step-by-step execution plan
    """

    def __init__(self, llm_client=None, tool_registry=None):
        """
        Initialize the planner.

        Args:
            llm_client: LLM client for generating plans
            tool_registry: Registry of available tools
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.logger = get_logger("jarvis.agent.planner")

    def set_llm_client(self, client):
        """Set the LLM client."""
        self.llm_client = client

    def set_tool_registry(self, registry):
        """Set the tool registry."""
        self.tool_registry = registry

    async def create_plan(
        self,
        intent: str,
        context: dict[str, Any] | None = None,
    ) -> Plan:
        """
        Create an execution plan for the given intent.

        Args:
            intent: Natural language description of what to do
            context: Additional context (current directory, project info, etc.)

        Returns:
            Plan object with steps to execute

        Raises:
            PlanningError: If plan cannot be created
        """
        if not self.llm_client:
            # Fallback to simple parsing if no LLM
            return self._parse_simple_intent(intent)

        if not self.tool_registry:
            raise PlanningError("Tool registry not configured")

        # Build prompt
        tools_description = self._build_tools_description()
        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            tools_description=tools_description,
            max_steps=MAX_PLAN_STEPS,
        )

        # Build user message with context
        user_message = f"Intent: {intent}"
        if context:
            user_message += f"\n\nContext:\n{json.dumps(context, indent=2)}"

        self.logger.info(f"Creating plan for: {intent}")

        try:
            # Call LLM
            response = await self.llm_client.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # Parse response
            plan = self._parse_llm_response(intent, response)
            self.logger.info(f"Created plan with {len(plan.steps)} steps")
            return plan

        except Exception as e:
            self.logger.exception(f"Failed to create plan: {e}")
            raise PlanningError(f"Failed to create plan: {e}")

    def _build_tools_description(self) -> str:
        """Build description of available tools for the prompt."""
        if not self.tool_registry:
            return "No tools available"

        descriptions = []
        for tool in self.tool_registry.get_all():
            params = []
            for name, schema in tool.schema.get("properties", {}).items():
                required = name in tool.schema.get("required", [])
                param_desc = f"  - {name}: {schema.get('description', 'No description')}"
                if required:
                    param_desc += " (required)"
                params.append(param_desc)

            tool_desc = f"""### {tool.name}
{tool.description}
Risk Level: {tool.risk_level.name}
Parameters:
{chr(10).join(params)}"""
            descriptions.append(tool_desc)

        return "\n\n".join(descriptions)

    def _parse_llm_response(self, intent: str, response: str) -> Plan:
        """Parse LLM response into a Plan."""
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            raise PlanningError(f"No JSON found in response: {response[:200]}")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            raise PlanningError(f"Invalid JSON in response: {e}")

        plan = Plan(
            intent=intent,
            reasoning=data.get("reasoning", ""),
        )

        for step_data in data.get("steps", []):
            risk_str = step_data.get("risk", "medium").upper()
            try:
                risk = RiskLevel[risk_str]
            except KeyError:
                risk = RiskLevel.MEDIUM

            step = PlanStep(
                tool_name=step_data.get("tool", ""),
                params=step_data.get("params", {}),
                description=step_data.get("description", ""),
                risk_level=risk,
                requires_approval=risk >= RiskLevel.HIGH,
            )
            plan.steps.append(step)

        return plan

    def _parse_simple_intent(self, intent: str) -> Plan:
        """
        Simple intent parsing without LLM.

        Handles common patterns directly.
        """
        intent_lower = intent.lower().strip()
        plan = Plan(intent=intent)

        # Git status
        if intent_lower in ("git status", "status", "show git status"):
            plan.add_step("git", {"operation": "status"}, "Check git status", RiskLevel.LOW)

        # Git diff
        elif intent_lower in ("git diff", "show diff", "diff"):
            plan.add_step("git", {"operation": "diff"}, "Show git diff", RiskLevel.LOW)

        # Git log
        elif intent_lower.startswith("git log") or intent_lower == "show commits":
            plan.add_step("git", {"operation": "log", "args": ["-10", "--oneline"]}, "Show recent commits", RiskLevel.LOW)

        # List files
        elif intent_lower.startswith("ls ") or intent_lower.startswith("list "):
            path = intent_lower.split(maxsplit=1)[1] if " " in intent_lower else "."
            plan.add_step("list_directory", {"path": path}, f"List files in {path}", RiskLevel.LOW)

        # Read file
        elif intent_lower.startswith("cat ") or intent_lower.startswith("read "):
            path = intent_lower.split(maxsplit=1)[1]
            plan.add_step("read_file", {"path": path}, f"Read {path}", RiskLevel.LOW)

        # System info
        elif intent_lower in ("system info", "system status", "health"):
            plan.add_step("system_info", {"info_type": "health"}, "Check system health", RiskLevel.LOW)

        # Open VS Code
        elif intent_lower.startswith("code ") or intent_lower.startswith("open "):
            path = intent_lower.split(maxsplit=1)[1] if " " in intent_lower else "."
            plan.add_step("vscode", {"action": "open_folder", "path": path}, f"Open {path} in VS Code", RiskLevel.LOW)

        # Run command (generic)
        elif intent_lower.startswith("run "):
            cmd = intent_lower[4:].strip()
            plan.add_step("run_command", {"command": cmd}, f"Run: {cmd}", RiskLevel.MEDIUM)

        # Unknown - use as command if it looks like one
        elif " " in intent_lower and not any(c in intent_lower for c in "?!"):
            # Might be a command
            plan.add_step("run_command", {"command": intent}, f"Run: {intent}", RiskLevel.MEDIUM)
            plan.reasoning = "Interpreted as shell command"

        else:
            plan.reasoning = f"Could not parse intent: {intent}. Please be more specific."

        return plan


__all__ = ["Planner", "PLANNER_SYSTEM_PROMPT"]
