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


def _infer_home_dir(workspace_root: str) -> str | None:
    """Infer user home directory from a workspace path like C:\\Users\\Name\\... or /home/name/..."""
    import re
    # Windows: C:\Users\Username\...
    m = re.match(r"([A-Za-z]:\\Users\\[^\\]+)", workspace_root)
    if m:
        return m.group(1)
    # Linux/Mac: /home/username/... or /Users/username/...
    m = re.match(r"(/(?:home|Users)/[^/]+)", workspace_root)
    if m:
        return m.group(1)
    return None


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


REACT_SYSTEM_PROMPT = """You are JARVIS, an AI developer agent with full filesystem access. You MUST use tools to perform actions — NEVER claim you did something without calling the tool.

## Tools:
{tools_compact}

## JSON Response (ONLY valid JSON, nothing else):
Tool call: {{"action": "tool_call", "tool": "<name>", "args": {{...}}}}
Final answer: {{"action": "final_answer", "answer": "<text>"}}

## Critical Rules:
1. To read/write/list files → MUST call the tool. Never say "done" without tool_call first.
2. To run commands → MUST call run_command. Never fabricate output.
3. Use FULL ABSOLUTE paths (from workspace root below).
4. After tool_result, decide: need more → another tool_call, OR ready → final_answer.
5. Max {max_steps} tool calls.
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

    def _build_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        """Build system prompt with compact tool list and optional workspace context."""
        tools_compact = self._build_compact_tools()
        prompt = REACT_SYSTEM_PROMPT.format(
            tools_compact=tools_compact,
            max_steps=self.max_steps,
        )

        ctx = context or {}

        # Add execution environment info
        workspace_root = ctx.get("workspace_root")
        pairing_code = ctx.get("pairing_code")
        if workspace_root or pairing_code:
            prompt += "\n\n## Execution Environment:"
            if workspace_root:
                prompt += f"\n- Workspace root: {workspace_root}"
                # Infer user home and Desktop from workspace path
                home_dir = _infer_home_dir(workspace_root)
                if home_dir:
                    prompt += f"\n- User home directory: {home_dir}"
                    prompt += f"\n- Desktop path: {home_dir}\\Desktop" if "\\" in workspace_root else f"\n- Desktop path: {home_dir}/Desktop"
            if pairing_code:
                prompt += f"\n- Connected to paired laptop (use paired_* tools and run_paired_command)"
                try:
                    from jarvis.devices.agent_registry import get_agent_registry
                    agent_reg = get_agent_registry()
                    agent = agent_reg.agents.get(pairing_code)
                    if agent:
                        prompt += f"\n- Platform: {agent.platform}"
                        prompt += f"\n- Hostname: {agent.hostname}"
                except Exception:
                    pass
            else:
                import platform as _platform
                prompt += f"\n- Platform: {_platform.system()} ({_platform.node()})"
                import os as _os
                prompt += f"\n- Home directory: {_os.path.expanduser('~')}"

        # Inject workspace folder context so LLM knows the full project structure
        folder_context = ctx.get("folder_context")
        if folder_context:
            prompt += f"\n\n## Workspace Context (auto-gathered):\n{folder_context}\n\nUse this context to understand the project structure. You can read specific files for details."

        return prompt

    def _build_compact_tools(self) -> str:
        """Build compact tool descriptions for the system prompt."""
        TOOL_DESCRIPTIONS = {
            "read_file": "read_file(path, start_line?, max_lines?) — read file content",
            "write_file": "write_file(path, content, mode='write'|'append') — write/create file",
            "list_directory": "list_directory(path, recursive?, pattern?) — list files in dir",
            "run_command": "run_command(command, cwd?) — run shell command",
            "git": "git(operation='status'|'diff'|'log'|'commit'|'push'|'pull'|'branch'|'checkout', message?, branch?) — git operations",
            "paired_read_file": "paired_read_file(path) — read file on paired laptop",
            "paired_write_file": "paired_write_file(path, content) — write file on paired laptop",
            "paired_list_directory": "paired_list_directory(path) — list files on paired laptop",
            "run_paired_command": "run_paired_command(command) — run command on paired laptop",
            "vscode": "vscode(action='open_folder'|'open_file', path) — open in VS Code",
        }
        lines = []
        for name in self.registry.list_tools():
            if name in TOOL_DESCRIPTIONS:
                lines.append(f"- {TOOL_DESCRIPTIONS[name]}")
            else:
                tool = self.registry.get(name)
                desc = getattr(tool, 'description', name)[:60] if tool else name
                schema = self.registry.get_schemas_for_llm()
                params = ""
                for s in schema:
                    if s.get("name") == name:
                        props = s.get("parameters", {}).get("properties", {})
                        params = ", ".join(props.keys())
                        break
                lines.append(f"- {name}({params}) — {desc}")
        return "\n".join(lines)

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
        system_prompt = self._build_system_prompt(context)

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
                # Retry once if empty (some models in rotation return empty)
                if not response or not response.strip():
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

            # Skip empty responses (model rotation can return empty)
            if not response or not response.strip():
                continue

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
