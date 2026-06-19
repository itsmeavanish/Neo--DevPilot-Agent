"""
ReAct Agent Loop — Reasoning + Acting with tool calling.

Implements an iterative agent loop where the LLM decides at each step
whether to call a tool or produce a final answer. Streams steps as they
happen for real-time UI feedback.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from jarvis.core.logging import get_logger
from jarvis.tools.registry import ToolRegistry, tool_registry

logger = get_logger("jarvis.agent.react_loop")


@dataclass
class AgentStep:
    """One step in the ReAct loop."""

    step_number: int
    type: str  # thinking, tool_call, tool_result, final_answer, error
    content: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[Any] = None
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = {
            "step_number": self.step_number,
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.tool_name:
            d["tool_name"] = self.tool_name
        if self.tool_args is not None:
            d["tool_args"] = self.tool_args
        if self.tool_result is not None:
            d["tool_result"] = self.tool_result
        if self.duration_ms:
            d["duration_ms"] = self.duration_ms
        return d


REACT_SYSTEM_PROMPT = """You are JARVIS, an autonomous AI developer assistant with direct tool access.
You help developers by executing commands, reading/writing files, managing git, and answering questions.

## Available Tools:
{tools_json}

## Response Format:
You MUST respond in EXACTLY one of these JSON formats (no other text):

### When you need to use a tool:
{{"action": "tool_call", "tool": "<tool_name>", "args": {{"param1": "value1"}}}}

### When you have enough information to answer:
{{"action": "final_answer", "answer": "<your complete response to the user>"}}

## Rules:
1. Think step by step. If you need information, call a tool first.
2. After each tool result, decide if you need more info or can answer.
3. Never fabricate tool results. Always call the tool to get real data.
4. Maximum {max_steps} tool calls per turn.
5. If a tool fails, explain the error and try an alternative approach.
6. Keep answers concise and actionable.
7. For file operations, use the actual file paths from the workspace.
"""


class ReactAgentLoop:
    """
    ReAct agent loop with tool calling.

    Streams AgentStep events as the loop progresses, allowing real-time
    UI updates on the mobile app.
    """

    def __init__(
        self,
        llm_client,
        registry: ToolRegistry | None = None,
        max_steps: int = 10,
        step_timeout: int = 60,
    ):
        self.llm_client = llm_client
        self.registry = registry or tool_registry
        self.max_steps = max_steps
        self.step_timeout = step_timeout

    def _build_system_prompt(self) -> str:
        """Build system prompt with tool schemas."""
        schemas = self.registry.get_schemas_for_llm()
        tools_json = json.dumps(schemas, indent=2)
        return REACT_SYSTEM_PROMPT.format(
            tools_json=tools_json,
            max_steps=self.max_steps,
        )

    async def run(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentStep]:
        """
        Run the ReAct loop, yielding AgentStep events as they happen.

        Args:
            user_message: The user's request
            history: Prior conversation messages [{"role": "...", "content": "..."}]
            context: Execution context (workspace_root, pairing_code, etc.)
        """
        context = context or {}
        system_prompt = self._build_system_prompt()

        messages = []
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})

        for step_num in range(1, self.max_steps + 1):
            step_start = time.time()

            yield AgentStep(
                step_number=step_num,
                type="thinking",
                content=f"Reasoning about step {step_num}...",
            )

            try:
                response = await asyncio.wait_for(
                    self.llm_client.chat(messages=messages, system=system_prompt),
                    timeout=self.step_timeout,
                )
            except asyncio.TimeoutError:
                yield AgentStep(
                    step_number=step_num,
                    type="error",
                    content="LLM response timed out",
                    duration_ms=int((time.time() - step_start) * 1000),
                )
                return
            except Exception as e:
                yield AgentStep(
                    step_number=step_num,
                    type="error",
                    content=f"LLM error: {e}",
                    duration_ms=int((time.time() - step_start) * 1000),
                )
                return

            action_type, data = self._parse_llm_output(response)

            if action_type == "final_answer":
                answer = data.get("answer", response)
                yield AgentStep(
                    step_number=step_num,
                    type="final_answer",
                    content=answer,
                    duration_ms=int((time.time() - step_start) * 1000),
                )
                return

            if action_type == "tool_call":
                tool_name = data.get("tool", "")
                tool_args = data.get("args", {})

                yield AgentStep(
                    step_number=step_num,
                    type="tool_call",
                    tool_name=tool_name,
                    tool_args=tool_args,
                )

                tool_result = await self._execute_tool(tool_name, tool_args, context)
                elapsed = int((time.time() - step_start) * 1000)

                yield AgentStep(
                    step_number=step_num,
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
                    "content": f"Tool '{tool_name}' returned:\n{observation}",
                })
                continue

            # Fallback: treat as final answer if we can't parse
            yield AgentStep(
                step_number=step_num,
                type="final_answer",
                content=response,
                duration_ms=int((time.time() - step_start) * 1000),
            )
            return

        yield AgentStep(
            step_number=self.max_steps,
            type="error",
            content=f"Reached maximum of {self.max_steps} steps without a final answer. Here's what I found so far based on the tool results above.",
        )

    async def run_to_completion(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Non-streaming: runs the full loop and returns the final answer."""
        final = ""
        async for step in self.run(user_message, history=history, context=context):
            if step.type == "final_answer":
                final = step.content
            elif step.type == "error":
                final = f"Error: {step.content}"
        return final or "No response generated."

    def _parse_llm_output(self, text: str) -> tuple[str, dict]:
        """Parse LLM output into (action_type, data)."""
        text = text.strip()

        # Try direct JSON parse first
        try:
            data = json.loads(text)
            action = data.get("action")
            if action in ("tool_call", "final_answer"):
                return action, data
        except (json.JSONDecodeError, TypeError):
            pass

        # Extract JSON from markdown code blocks
        code_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if code_block:
            try:
                data = json.loads(code_block.group(1))
                action = data.get("action")
                if action in ("tool_call", "final_answer"):
                    return action, data
            except (json.JSONDecodeError, TypeError):
                pass

        # Try to find any JSON object in the text
        json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        if json_match:
            try:
                data = json.loads(json_match.group())
                action = data.get("action")
                if action in ("tool_call", "final_answer"):
                    return action, data
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: treat the whole text as a final answer
        return "final_answer", {"answer": text}

    async def _execute_tool(
        self, tool_name: str, tool_args: dict, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool and return structured result."""
        if not self.registry.has(tool_name):
            available = self.registry.list_tools()
            return {"status": "error", "error": f"Tool '{tool_name}' not found. Available tools: {available}"}

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


__all__ = ["ReactAgentLoop", "AgentStep"]
