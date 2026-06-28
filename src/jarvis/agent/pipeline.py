"""
Multi-Model Pipeline Orchestrator.

Routes a task through three phases, each handled by a different LLM model
selected based on its strengths:

  1. UNDERSTAND - Fast, high-context model analyzes the task and gathers info
  2. PLAN - Strong reasoning model designs the implementation strategy
  3. IMPLEMENT - Best coding model executes the plan with tool calls

The FreeLLM router automatically selects the best available model from
50+ free-tier models across 16 providers based on real-time availability.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

from jarvis.core.logging import get_logger
from jarvis.tools.registry import ToolRegistry, tool_registry

logger = get_logger("jarvis.agent.pipeline")


class PipelinePhase(str, Enum):
    UNDERSTAND = "understand"
    PLAN = "plan"
    IMPLEMENT = "implement"


# Model selection hints passed to FreeLLM's /v1/chat/completions.
# FreeLLM's router uses these to pick the best available model from
# its priority chain. "auto" means the server picks the best available.
# Specific model IDs target specialized models when available.
PHASE_MODEL_PREFERENCES = {
    PipelinePhase.UNDERSTAND: "auto",
    PipelinePhase.PLAN: "auto",
    PipelinePhase.IMPLEMENT: "auto",
}


@dataclass
class PipelineStep:
    """One event in the pipeline execution."""

    phase: str
    type: str  # phase_start, thinking, tool_call, tool_result, phase_result, final_answer, error
    content: str = ""
    model_used: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[Any] = None
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = {
            "phase": self.phase,
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.model_used:
            d["model_used"] = self.model_used
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.tool_args is not None:
            d["tool_args"] = self.tool_args
        if self.tool_result is not None:
            d["tool_result"] = self.tool_result
        if self.duration_ms:
            d["duration_ms"] = self.duration_ms
        return d


UNDERSTAND_SYSTEM_PROMPT = """You are an expert task analyst. Your job is to deeply understand a developer's request and produce a structured analysis.

Given a task description and optional code context, produce a JSON response with:
{{
  "summary": "One-line summary of what the user wants",
  "intent": "create|modify|fix|refactor|explain|delete",
  "files_involved": ["list of files that likely need changes based on context"],
  "dependencies": ["what needs to exist or be understood first"],
  "constraints": ["any constraints or requirements mentioned"],
  "questions": ["any ambiguities that need resolution (empty if clear)"],
  "complexity": "low|medium|high",
  "context_needed": "what additional context would help implementation"
}}

Be precise and concise. Output ONLY valid JSON."""


PLAN_SYSTEM_PROMPT = """You are an expert software architect. Given a task analysis, produce a detailed implementation plan.

You will receive a task analysis from a previous model. Create a step-by-step plan that a coding model can follow mechanically.

Produce a JSON response with:
{{
  "approach": "Brief description of the chosen approach",
  "steps": [
    {{
      "order": 1,
      "action": "read_file|write_file|modify_file|run_command|create_file|delete_file",
      "target": "file path or command",
      "description": "What to do and why",
      "details": "Specific content changes, code to write, or command to run"
    }}
  ],
  "validation": "How to verify the changes work",
  "risks": ["potential issues to watch for"]
}}

Be specific enough that each step can be executed without additional context.
Output ONLY valid JSON."""


IMPLEMENT_SYSTEM_PROMPT = """You are JARVIS, an autonomous AI developer assistant with direct tool access.
You help developers by executing commands, reading/writing files, managing git, and answering questions.

You have been given a PLAN created by an architect model. Execute each step precisely.

## Available Tools:
{tools_json}

## Response Format:
You MUST respond in EXACTLY one of these JSON formats (no other text):

### When you need to use a tool:
{{"action": "tool_call", "tool": "<tool_name>", "args": {{"param1": "value1"}}}}

### When you have completed all steps:
{{"action": "final_answer", "answer": "<summary of all changes made>"}}

## Rules:
1. Follow the plan step by step. Execute each action using the appropriate tool.
2. After each tool result, proceed to the next plan step or report completion.
3. Never fabricate tool results. Always call the tool to get real data.
4. Maximum {max_steps} tool calls per turn.
5. If a step fails, explain the error and try an alternative approach.
6. Report what you actually changed, not what you intended to change.
7. For file operations, use the actual file paths from the workspace.

## PLAN TO EXECUTE:
{plan_json}
"""


def _should_use_pipeline(message: str) -> bool:
    """Determine if a message warrants the full pipeline vs simple agent loop."""
    lower = message.lower().strip()
    word_count = len(lower.split())

    if word_count < 4:
        return False

    pipeline_signals = [
        "implement", "build", "create", "add feature", "refactor",
        "fix the bug", "fix the", "change the", "update the", "modify",
        "write a", "set up", "configure", "integrate",
        "make it so", "i want", "can you", "please add",
        "convert", "migrate", "move the", "rename",
        "add a", "add the", "generate",
    ]
    return any(sig in lower for sig in pipeline_signals)


class PipelineOrchestrator:
    """
    Multi-model pipeline that routes tasks through understand → plan → implement.

    Each phase uses a different model optimized for its role:
    - Understand: Fast model with good comprehension (e.g., Gemini Flash, GPT-OSS)
    - Plan: Strong reasoning model (e.g., DeepSeek V3, Claude Sonnet via FreeLLM)
    - Implement: Best coding model (e.g., Qwen3-Coder, DeepSeek-Coder, Codestral)
    """

    def __init__(
        self,
        llm_client,
        registry: ToolRegistry | None = None,
        max_steps: int = 15,
        step_timeout: int = 90,
    ):
        self.llm_client = llm_client
        self.registry = registry or tool_registry
        self.max_steps = max_steps
        self.step_timeout = step_timeout

    async def run(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
        code_context: Optional[str] = None,
    ) -> AsyncIterator[PipelineStep]:
        """
        Run the full pipeline, yielding PipelineStep events.
        """
        context = context or {}

        # ── Phase 1: UNDERSTAND ──
        yield PipelineStep(
            phase=PipelinePhase.UNDERSTAND,
            type="phase_start",
            content="Analyzing your request...",
        )

        folder_context = context.get("folder_context", "")
        understanding = await self._run_understand(user_message, code_context, history, folder_context)

        yield PipelineStep(
            phase=PipelinePhase.UNDERSTAND,
            type="phase_result",
            content=json.dumps(understanding, indent=2) if isinstance(understanding, dict) else understanding,
            model_used=PHASE_MODEL_PREFERENCES[PipelinePhase.UNDERSTAND],
        )

        # If the task is just a question or very simple, skip plan+implement
        if isinstance(understanding, dict):
            intent = understanding.get("intent", "")
            complexity = understanding.get("complexity", "medium")
            questions = understanding.get("questions", [])

            if intent == "explain" or (complexity == "low" and not understanding.get("files_involved")):
                # Simple question — answer directly without plan/implement
                yield PipelineStep(
                    phase=PipelinePhase.UNDERSTAND,
                    type="final_answer",
                    content=understanding.get("summary", str(understanding)),
                )
                return

        # ── Phase 2: PLAN ──
        yield PipelineStep(
            phase=PipelinePhase.PLAN,
            type="phase_start",
            content="Designing implementation strategy...",
        )

        plan = await self._run_plan(user_message, understanding, code_context, folder_context)

        yield PipelineStep(
            phase=PipelinePhase.PLAN,
            type="phase_result",
            content=json.dumps(plan, indent=2) if isinstance(plan, dict) else plan,
            model_used=PHASE_MODEL_PREFERENCES[PipelinePhase.PLAN],
        )

        # ── Phase 3: IMPLEMENT ──
        yield PipelineStep(
            phase=PipelinePhase.IMPLEMENT,
            type="phase_start",
            content="Executing the plan...",
        )

        async for step in self._run_implement(user_message, plan, history, context):
            yield step

    async def _run_understand(
        self,
        user_message: str,
        code_context: Optional[str],
        history: list[dict[str, str]] | None,
        folder_context: str = "",
    ) -> dict | str:
        """Phase 1: Analyze the task with a fast comprehension model."""
        prompt_parts = [f"Task: {user_message}"]
        if folder_context:
            prompt_parts.append(f"\n{folder_context}")
        if code_context:
            prompt_parts.append(f"\nCode context:\n```\n{code_context}\n```")
        if history:
            recent = history[-4:]
            conv = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)
            prompt_parts.append(f"\nRecent conversation:\n{conv}")

        full_prompt = "\n".join(prompt_parts)
        messages = [{"role": "user", "content": full_prompt}]

        try:
            response = await asyncio.wait_for(
                self.llm_client.chat(
                    messages=messages,
                    system=UNDERSTAND_SYSTEM_PROMPT,
                    model=PHASE_MODEL_PREFERENCES[PipelinePhase.UNDERSTAND],
                ),
                timeout=self.step_timeout,
            )
            return self._parse_json_response(response)
        except Exception as e:
            logger.warning("Understand phase failed: %s", e)
            return {"summary": user_message, "intent": "modify", "complexity": "medium", "files_involved": [], "dependencies": [], "constraints": [], "questions": [], "context_needed": ""}

    async def _run_plan(
        self,
        user_message: str,
        understanding: dict | str,
        code_context: Optional[str],
        folder_context: str = "",
    ) -> dict | str:
        """Phase 2: Create implementation plan with a reasoning model."""
        prompt_parts = [
            f"Original request: {user_message}",
            f"\nTask analysis:\n{json.dumps(understanding, indent=2) if isinstance(understanding, dict) else understanding}",
        ]
        if folder_context:
            prompt_parts.append(f"\n{folder_context}")
        if code_context:
            prompt_parts.append(f"\nRelevant code:\n```\n{code_context[:4000]}\n```")

        full_prompt = "\n".join(prompt_parts)
        messages = [{"role": "user", "content": full_prompt}]

        try:
            response = await asyncio.wait_for(
                self.llm_client.chat(
                    messages=messages,
                    system=PLAN_SYSTEM_PROMPT,
                    model=PHASE_MODEL_PREFERENCES[PipelinePhase.PLAN],
                ),
                timeout=self.step_timeout,
            )
            return self._parse_json_response(response)
        except Exception as e:
            logger.warning("Plan phase failed: %s", e)
            return {
                "approach": "Direct implementation",
                "steps": [{"order": 1, "action": "modify_file", "target": "unknown", "description": user_message, "details": ""}],
                "validation": "Manual review",
                "risks": ["Plan generation failed, implementing directly"],
            }

    async def _run_implement(
        self,
        user_message: str,
        plan: dict | str,
        history: list[dict[str, str]] | None,
        context: dict[str, Any],
    ) -> AsyncIterator[PipelineStep]:
        """Phase 3: Execute the plan using the coding model with tools."""
        schemas = self.registry.get_schemas_for_llm()
        tools_json = json.dumps(schemas, indent=2)
        plan_json = json.dumps(plan, indent=2) if isinstance(plan, dict) else plan

        system_prompt = IMPLEMENT_SYSTEM_PROMPT.format(
            tools_json=tools_json,
            max_steps=self.max_steps,
            plan_json=plan_json,
        )

        messages = []
        if history:
            messages.extend(history[-6:])
        messages.append({"role": "user", "content": f"Execute this task: {user_message}\n\nFollow the plan above precisely."})

        for step_num in range(1, self.max_steps + 1):
            step_start = time.time()

            yield PipelineStep(
                phase=PipelinePhase.IMPLEMENT,
                type="thinking",
                content=f"Executing step {step_num}...",
            )

            try:
                response = await asyncio.wait_for(
                    self.llm_client.chat(
                        messages=messages,
                        system=system_prompt,
                        model=PHASE_MODEL_PREFERENCES[PipelinePhase.IMPLEMENT],
                    ),
                    timeout=self.step_timeout,
                )
            except asyncio.TimeoutError:
                yield PipelineStep(
                    phase=PipelinePhase.IMPLEMENT,
                    type="error",
                    content="Implementation step timed out",
                    duration_ms=int((time.time() - step_start) * 1000),
                )
                return
            except Exception as e:
                yield PipelineStep(
                    phase=PipelinePhase.IMPLEMENT,
                    type="error",
                    content=f"LLM error: {e}",
                    duration_ms=int((time.time() - step_start) * 1000),
                )
                return

            action_type, data = self._parse_action(response)

            if action_type == "final_answer":
                yield PipelineStep(
                    phase=PipelinePhase.IMPLEMENT,
                    type="final_answer",
                    content=data.get("answer", response),
                    model_used=PHASE_MODEL_PREFERENCES[PipelinePhase.IMPLEMENT],
                    duration_ms=int((time.time() - step_start) * 1000),
                )
                return

            if action_type == "tool_call":
                tool_name = data.get("tool", "")
                tool_args = data.get("args", {})

                yield PipelineStep(
                    phase=PipelinePhase.IMPLEMENT,
                    type="tool_call",
                    tool_name=tool_name,
                    tool_args=tool_args,
                )

                tool_result = await self._execute_tool(tool_name, tool_args, context)
                elapsed = int((time.time() - step_start) * 1000)

                yield PipelineStep(
                    phase=PipelinePhase.IMPLEMENT,
                    type="tool_result",
                    tool_name=tool_name,
                    tool_result=tool_result,
                    duration_ms=elapsed,
                )

                messages.append({"role": "assistant", "content": response})
                observation = json.dumps(tool_result, default=str, ensure_ascii=False)
                if len(observation) > 8000:
                    observation = observation[:8000] + "\n... (truncated)"
                messages.append({
                    "role": "user",
                    "content": f"Tool '{tool_name}' returned:\n{observation}\n\nContinue with the next step in the plan.",
                })
                continue

            # Fallback
            yield PipelineStep(
                phase=PipelinePhase.IMPLEMENT,
                type="final_answer",
                content=response,
                duration_ms=int((time.time() - step_start) * 1000),
            )
            return

        yield PipelineStep(
            phase=PipelinePhase.IMPLEMENT,
            type="error",
            content=f"Reached maximum of {self.max_steps} implementation steps.",
        )

    def _parse_json_response(self, text: str) -> dict | str:
        """Try to parse JSON from LLM response."""
        import re

        text = text.strip()

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        code_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except (json.JSONDecodeError, TypeError):
                pass

        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except (json.JSONDecodeError, TypeError):
                pass

        return text

    def _parse_action(self, text: str) -> tuple[str, dict]:
        """Parse LLM output into (action_type, data)."""
        import re

        text = text.strip()

        try:
            data = json.loads(text)
            action = data.get("action")
            if action in ("tool_call", "final_answer"):
                return action, data
        except (json.JSONDecodeError, TypeError):
            pass

        code_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if code_block:
            try:
                data = json.loads(code_block.group(1))
                action = data.get("action")
                if action in ("tool_call", "final_answer"):
                    return action, data
            except (json.JSONDecodeError, TypeError):
                pass

        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                action = data.get("action")
                if action in ("tool_call", "final_answer"):
                    return action, data
            except (json.JSONDecodeError, TypeError):
                pass

        return "final_answer", {"answer": text}

    async def _execute_tool(
        self, tool_name: str, tool_args: dict, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool and return structured result."""
        if not self.registry.has(tool_name):
            available = self.registry.list_tools()
            return {"status": "error", "error": f"Tool '{tool_name}' not found. Available: {available}"}

        tool = self.registry.get(tool_name)

        try:
            result = await asyncio.wait_for(
                tool.execute(tool_args),
                timeout=self.step_timeout,
            )
            return {
                "status": result.status,
                "output": result.output,
                "error": result.error,
            }
        except asyncio.TimeoutError:
            return {"status": "error", "error": f"Tool '{tool_name}' timed out after {self.step_timeout}s"}
        except Exception as e:
            logger.warning("Tool execution error: %s(%s) -> %s", tool_name, tool_args, e)
            return {"status": "error", "error": str(e)}


def should_use_pipeline(message: str) -> bool:
    """Public API: determine if a message warrants the full pipeline."""
    return _should_use_pipeline(message)


__all__ = ["PipelineOrchestrator", "PipelineStep", "PipelinePhase", "should_use_pipeline"]
