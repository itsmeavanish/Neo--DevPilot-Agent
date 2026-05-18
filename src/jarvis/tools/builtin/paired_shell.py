"""
Execute shell commands on the WebSocket-paired laptop agent.
"""

from __future__ import annotations

from typing import Any, ClassVar

from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import tool_registry
from jarvis.core.constants import RiskLevel, DEFAULT_COMMAND_TIMEOUT
from jarvis.core.logging import get_logger
from jarvis.execution_context import get_pairing_code, get_capabilities
from jarvis.devices.agent_registry import get_agent_registry
from jarvis.security.policy import assess_shell_command
from jarvis.security.audit import audit_log

logger = get_logger("jarvis.tools.paired_shell")


@tool_registry.register
class RunPairedCommandTool(BaseTool):
    """Run a shell command on the paired remote machine (WebSocket agent)."""

    name: ClassVar[str] = "run_paired_command"
    description: ClassVar[str] = (
        "Execute a shell command on the laptop connected with the user's pairing code. "
        "Use this instead of run_command when operating a remote dev machine from the phone."
    )
    risk_level: ClassVar[RiskLevel] = RiskLevel.HIGH
    timeout: ClassVar[int] = DEFAULT_COMMAND_TIMEOUT

    schema: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run on paired laptop"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 600},
        },
        "required": ["command"],
    }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        command = (params.get("command") or "").strip()
        timeout = int(params.get("timeout") or self.timeout)
        code = get_pairing_code()
        if not code:
            return ToolResult.failure("No pairing context: open Autonomous/Mission flow with a pairing code.")

        caps = get_capabilities()
        assessment = assess_shell_command(command, caps)
        if not assessment.allowed:
            audit_log(
                "paired_shell_blocked",
                pairing_code=code,
                detail={"command": command, "reason": assessment.reason},
                success=False,
            )
            return ToolResult.failure(assessment.reason or "Command not allowed")

        registry = get_agent_registry()
        audit_log(
            "paired_shell_exec",
            pairing_code=code,
            detail={"command": command[:500], "risk": assessment.risk},
            success=None,
        )
        try:
            raw = await registry.send_command_to_agent(code, command, timeout=timeout)
        except Exception as e:
            logger.exception("Paired command failed")
            audit_log("paired_shell_exec", pairing_code=code, detail={"error": str(e)}, success=False)
            return ToolResult.failure(str(e))

        ok = bool(raw.get("success", True))
        out = {
            "stdout": raw.get("stdout", ""),
            "stderr": raw.get("stderr", ""),
            "exit_code": raw.get("exit_code", -1),
        }
        audit_log("paired_shell_exec", pairing_code=code, detail={"exit_code": out["exit_code"]}, success=ok)
        if ok:
            return ToolResult.success(out)
        err = raw.get("error") or raw.get("stderr") or "Command failed"
        return ToolResult.failure(f"{err} (exit {out['exit_code']})")


__all__ = ["RunPairedCommandTool"]
