"""
External agent endpoints — Claude Code and Jules.

Claude Code: Runs `claude -p <prompt>` on the paired laptop via WebSocket shell.
Jules: Creates a GitHub issue assigned to Jules via `gh issue create`.
"""

import json
import asyncio
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from jarvis.core.logging import get_logger

router = APIRouter()
logger = get_logger("jarvis.api.mobile.external_agents")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


class ClaudeCodeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    workspace_root: Optional[str] = None
    pairing_code: Optional[str] = None


class JulesRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=4000)
    repo: Optional[str] = None
    pairing_code: Optional[str] = None
    workspace_root: Optional[str] = None


class JulesResponse(BaseModel):
    success: bool
    message: str
    issue_url: Optional[str] = None


@router.post("/project/ai/claude-code-stream")
async def claude_code_stream(request: ClaudeCodeRequest):
    """
    Run Claude Code CLI on paired laptop, stream output back via SSE.
    Uses `claude -p "<prompt>" --output-format stream-json` for structured streaming.
    """

    async def event_generator() -> AsyncIterator[str]:
        from jarvis.execution_context import set_pairing_context, clear_pairing_context, get_pairing_code
        from jarvis.devices.agent_registry import get_agent_registry
        from jarvis.security.policy import Capability

        pairing_tokens = None
        code = request.pairing_code

        if not code:
            yield _sse({"type": "error", "content": "No pairing code provided. Connect to your laptop first."})
            yield "data: [DONE]\n\n"
            return

        try:
            all_caps = [c.value for c in Capability]
            pairing_tokens = set_pairing_context(code, capabilities=all_caps, workspace_root=request.workspace_root)

            yield _sse({"type": "thinking", "content": "Starting Claude Code on paired laptop..."})

            registry = get_agent_registry()

            prompt_escaped = request.message.replace('"', '\\"').replace('`', '\\`')
            workspace_flag = f' --cwd "{request.workspace_root}"' if request.workspace_root else ''
            cmd = f'claude -p "{prompt_escaped}"{workspace_flag} --output-format stream-json'

            yield _sse({"type": "tool_call", "tool": "claude_code", "args": {"command": cmd[:200]}})

            try:
                raw = await registry.send_command_to_agent(code, cmd, timeout=300)
            except Exception as e:
                logger.exception("Claude Code execution failed")
                yield _sse({"type": "error", "content": f"Failed to run Claude Code: {e}"})
                yield "data: [DONE]\n\n"
                return

            stdout = raw.get("stdout", "")
            stderr = raw.get("stderr", "")
            exit_code = raw.get("exit_code", -1)

            if exit_code != 0 and not stdout:
                error_msg = stderr or f"Claude Code exited with code {exit_code}"
                yield _sse({"type": "error", "content": error_msg})
                yield "data: [DONE]\n\n"
                return

            # Parse stream-json output — each line is a JSON event from Claude
            full_text = ""
            for line in stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    evt_type = evt.get("type", "")

                    if evt_type == "assistant" and "message" in evt:
                        pass
                    elif evt_type == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            full_text += text
                            yield _sse({"type": "token", "content": text})
                    elif evt_type == "tool_use":
                        tool_name = evt.get("name", "unknown")
                        tool_input = evt.get("input", {})
                        yield _sse({"type": "tool_call", "tool": tool_name, "args": tool_input})
                    elif evt_type == "tool_result":
                        yield _sse({"type": "tool_result", "tool": evt.get("name", ""), "result": {"output": evt.get("output", "")[:500], "status": "success"}})
                    elif evt_type == "result":
                        result_text = evt.get("result", "")
                        if result_text and not full_text:
                            full_text = result_text
                            yield _sse({"type": "token", "content": result_text})
                except json.JSONDecodeError:
                    if line and not full_text:
                        full_text += line + "\n"

            if not full_text and stdout:
                full_text = stdout[:4000]
                yield _sse({"type": "token", "content": full_text})

            yield _sse({"type": "done", "content": full_text})
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("Claude Code stream error")
            yield _sse({"type": "error", "content": str(e)})
            yield "data: [DONE]\n\n"
        finally:
            if pairing_tokens:
                clear_pairing_context(pairing_tokens)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/project/ai/jules", response_model=JulesResponse)
async def run_jules_agent(request: JulesRequest):
    """
    Dispatch a task to Jules by creating a GitHub issue in the repo.
    Jules picks up issues assigned to it and works autonomously.
    """
    from jarvis.execution_context import set_pairing_context, clear_pairing_context
    from jarvis.devices.agent_registry import get_agent_registry
    from jarvis.security.policy import Capability

    code = request.pairing_code
    if not code:
        return JulesResponse(success=False, message="No pairing code. Connect to your laptop first.")

    try:
        all_caps = [c.value for c in Capability]
        tokens = set_pairing_context(code, capabilities=all_caps, workspace_root=request.workspace_root)

        registry = get_agent_registry()

        # Detect repo from workspace or use provided
        repo = request.repo
        if not repo and request.workspace_root:
            try:
                result = await registry.send_command_to_agent(
                    code,
                    f'cd "{request.workspace_root}" && gh repo view --json nameWithOwner -q .nameWithOwner',
                    timeout=15,
                )
                if result.get("stdout", "").strip():
                    repo = result["stdout"].strip()
            except Exception:
                pass

        if not repo:
            clear_pairing_context(tokens)
            return JulesResponse(success=False, message="Could not detect GitHub repo. Ensure the workspace is a git repo with a remote.")

        # Create issue assigned to Jules
        title = request.intent[:80]
        body = f"## Task\n\n{request.intent}\n\n---\n*Created from DevPilot mobile app*"
        body_escaped = body.replace('"', '\\"').replace('`', '\\`')
        title_escaped = title.replace('"', '\\"')

        cmd = f'gh issue create --repo "{repo}" --title "{title_escaped}" --body "{body_escaped}" --assignee "@Jules"'

        try:
            result = await registry.send_command_to_agent(code, cmd, timeout=30)
        except Exception as e:
            clear_pairing_context(tokens)
            return JulesResponse(success=False, message=f"Failed to create issue: {e}")

        clear_pairing_context(tokens)

        stdout = result.get("stdout", "").strip()
        stderr = result.get("stderr", "").strip()

        if result.get("exit_code", 1) != 0:
            return JulesResponse(success=False, message=stderr or "Failed to create GitHub issue for Jules")

        issue_url = ""
        for line in stdout.split('\n'):
            if 'github.com' in line and '/issues/' in line:
                issue_url = line.strip()
                break

        if not issue_url:
            issue_url = stdout

        return JulesResponse(
            success=True,
            message=f"Task dispatched to Jules",
            issue_url=issue_url,
        )

    except Exception as e:
        logger.exception("Jules agent error")
        return JulesResponse(success=False, message=str(e))
