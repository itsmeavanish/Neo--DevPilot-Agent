"""
External agent endpoints — Claude Code and Jules.

Claude Code: Runs `claude -p <prompt>` on the paired laptop via WebSocket shell.
Jules: Creates a GitHub issue assigned to Jules via `gh issue create`.
"""

import json
import asyncio
import base64
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

    Strategy:
    1. Write the user prompt to a temp file on the laptop (avoids shell escaping)
    2. cd into workspace, then run `claude -p <prompt> --output-format stream-json`
    3. Parse the stream-json output and relay as SSE events
    """

    async def event_generator() -> AsyncIterator[str]:
        from jarvis.execution_context import set_pairing_context, clear_pairing_context
        from jarvis.devices.agent_registry import get_agent_registry
        from jarvis.security.policy import Capability

        pairing_tokens = None
        code = request.pairing_code

        if not code:
            yield _sse({"type": "error", "content": "No pairing code provided. Connect to your laptop first."})
            yield "data: [DONE]\n\n"
            return

        if not request.message.strip():
            yield _sse({"type": "error", "content": "Empty message. Please type a question or instruction."})
            yield "data: [DONE]\n\n"
            return

        try:
            all_caps = [c.value for c in Capability]
            pairing_tokens = set_pairing_context(code, capabilities=all_caps, workspace_root=request.workspace_root)

            registry = get_agent_registry()

            yield _sse({"type": "thinking", "content": "Connecting to Claude Code on your laptop..."})

            # Step 1: Check if Claude Code CLI is available
            check_result = await registry.send_command_to_agent(code, "claude --version", timeout=15)
            if not check_result.get("success") and check_result.get("exit_code", 1) != 0:
                stderr = check_result.get("stderr", "")
                if "not found" in stderr.lower() or "not recognized" in stderr.lower():
                    yield _sse({"type": "error", "content": "Claude Code CLI is not installed on your laptop. Install it with: npm install -g @anthropic-ai/claude-code"})
                    yield "data: [DONE]\n\n"
                    return

            yield _sse({"type": "thinking", "content": "Claude Code is ready. Preparing your request..."})

            # Step 2: Detect OS
            os_check = await registry.send_command_to_agent(code, "uname 2>nul || echo Windows", timeout=5)
            os_output = os_check.get("stdout", "").strip()
            is_windows = "Windows" in os_output or os_output == ""

            # Step 3: Build the claude command
            workspace = request.workspace_root or "."

            if is_windows:
                # Use the agent's native file_write to write a .ps1 script,
                # then execute it. This bypasses cmd.exe's 8191-char limit entirely.
                prompt_b64 = base64.b64encode(request.message.encode('utf-8')).decode('ascii')
                workspace_ps = workspace.replace("'", "''")
                script_content = "\n".join([
                    "$ErrorActionPreference = 'Stop'",
                    f"Set-Location -Path '{workspace_ps}'",
                    f"$bytes = [Convert]::FromBase64String('{prompt_b64}')",
                    "$prompt = [System.Text.Encoding]::UTF8.GetString($bytes)",
                    "claude -p $prompt --output-format stream-json --verbose",
                ])

                # Write script via WebSocket file_write (no cmd.exe involved)
                script_path = "~/_jarvis_claude_run.ps1"
                write_result = await registry.send_agent_request(
                    code,
                    {"type": "file_write", "path": script_path, "content": script_content},
                    wait_timeout=10,
                )
                if not write_result.get("success", False):
                    yield _sse({"type": "error", "content": f"Failed to prepare script: {write_result.get('error', 'unknown')}"})
                    yield "data: [DONE]\n\n"
                    return

                # Get the resolved path from the write result
                resolved_path = write_result.get("path", script_path)
                claude_cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{resolved_path}"'
                cleanup_cmd = f'del "{resolved_path}" 2>nul'
            else:
                prompt_b64 = base64.b64encode(request.message.encode('utf-8')).decode('ascii')
                tmp_file = "/tmp/.jarvis_claude_prompt.txt"
                write_cmd = f'printf "%s" "{prompt_b64}" | base64 -d > {tmp_file}'
                cleanup_cmd = f'rm -f {tmp_file}'

                write_result = await registry.send_command_to_agent(code, write_cmd, timeout=10)
                if write_result.get("exit_code", 0) != 0:
                    yield _sse({"type": "error", "content": "Failed to prepare prompt on laptop. Please try again."})
                    yield "data: [DONE]\n\n"
                    return

                claude_cmd = f'cd "{workspace}" && claude -p "$(cat {tmp_file})" --output-format stream-json --verbose'

            yield _sse({"type": "tool_call", "tool": "claude_code", "args": {"workspace": workspace, "prompt_preview": request.message[:100]}})

            # Run Claude Code (5 min timeout — it can take a while for complex tasks)
            try:
                raw = await registry.send_command_to_agent(code, claude_cmd, timeout=300)
            except asyncio.TimeoutError:
                yield _sse({"type": "error", "content": "Claude Code took too long (>5 min). Try breaking the task into smaller pieces."})
                yield "data: [DONE]\n\n"
                if cleanup_cmd:
                    await registry.send_command_to_agent(code, cleanup_cmd, timeout=5)
                return
            except Exception as e:
                logger.exception("Claude Code execution failed")
                yield _sse({"type": "error", "content": f"Failed to run Claude Code: {e}"})
                yield "data: [DONE]\n\n"
                if cleanup_cmd:
                    await registry.send_command_to_agent(code, cleanup_cmd, timeout=5)
                return

            # Cleanup temp file (fire and forget — only needed on Unix)
            if cleanup_cmd:
                asyncio.create_task(_cleanup_temp(registry, code, cleanup_cmd))

            stdout = raw.get("stdout", "")
            stderr = raw.get("stderr", "")
            exit_code = raw.get("exit_code", -1)

            yield _sse({"type": "tool_result", "tool": "claude_code", "result": {"status": "success" if exit_code == 0 else "error", "exit_code": exit_code}})

            if exit_code != 0 and not stdout:
                error_msg = stderr or f"Claude Code exited with code {exit_code}"
                if "ANTHROPIC_API_KEY" in error_msg or "api key" in error_msg.lower():
                    error_msg = "Claude Code needs an API key. Run `claude` on your laptop terminal to authenticate first."
                elif "rate limit" in error_msg.lower():
                    error_msg = "Rate limited by Anthropic. Please wait a moment and try again."
                elif "permission" in error_msg.lower() or "trust" in error_msg.lower():
                    error_msg = "Claude Code needs permissions. Run `claude` interactively on your laptop once to accept the trust prompt, then retry."
                yield _sse({"type": "error", "content": error_msg})
                yield "data: [DONE]\n\n"
                return

            # Step 5: Parse stream-json output from Claude Code CLI
            # Actual format (one JSON per line):
            #   {"type":"system","subtype":"init","tools":[...],...} — skip
            #   {"type":"system","subtype":"thinking_tokens","estimated_tokens":N,...} — thinking indicator
            #   {"type":"assistant","message":{"content":[{"type":"thinking","thinking":"..."},{"type":"text","text":"..."},{"type":"tool_use","name":"...","input":{}}]}} — content
            #   {"type":"result","subtype":"success","result":"final text","duration_ms":N,...} — done
            full_text = ""
            last_text = ""
            lines = stdout.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue

                evt_type = evt.get("type", "")
                evt_subtype = evt.get("subtype", "")

                if evt_type == "system":
                    if evt_subtype == "init":
                        model = evt.get("model", "claude")
                        yield _sse({"type": "thinking", "content": f"Claude Code ({model}) initialized in {evt.get('cwd', workspace)}"})
                    elif evt_subtype == "thinking_tokens":
                        tokens = evt.get("estimated_tokens", 0)
                        if tokens > 20:
                            yield _sse({"type": "thinking", "content": f"Thinking... ({tokens} tokens)"})

                elif evt_type == "assistant":
                    msg = evt.get("message", {})
                    for block in msg.get("content", []):
                        block_type = block.get("type", "")
                        if block_type == "thinking":
                            thinking_text = block.get("thinking", "")
                            if thinking_text:
                                yield _sse({"type": "thinking", "content": thinking_text[:500]})
                        elif block_type == "text":
                            text = block.get("text", "")
                            if text and text != last_text:
                                last_text = text
                                full_text = text
                                yield _sse({"type": "token", "content": text})
                        elif block_type == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_input = block.get("input", {})
                            yield _sse({"type": "tool_call", "tool": tool_name, "args": tool_input})
                        elif block_type == "tool_result":
                            content = block.get("content", "")
                            if isinstance(content, list):
                                content = "\n".join(
                                    c.get("text", "") for c in content if isinstance(c, dict)
                                )
                            yield _sse({"type": "tool_result", "tool": block.get("name", "tool"), "result": {"output": str(content)[:2000], "status": "success"}})

                elif evt_type == "result":
                    result_text = evt.get("result", "")
                    duration = evt.get("duration_ms", 0)
                    num_turns = evt.get("num_turns", 1)
                    if result_text and result_text != full_text:
                        full_text = result_text
                        yield _sse({"type": "token", "content": result_text})
                    info_parts = []
                    if duration:
                        info_parts.append(f"{duration/1000:.1f}s")
                    if num_turns and num_turns > 1:
                        info_parts.append(f"{num_turns} turns")
                    if info_parts:
                        yield _sse({"type": "thinking", "content": f"Completed in {' | '.join(info_parts)}"})

            # Fallback: if no structured text was parsed, emit raw stdout
            if not full_text and stdout.strip():
                full_text = stdout.strip()
                chunk_size = 120
                for i in range(0, len(full_text), chunk_size):
                    chunk = full_text[i:i + chunk_size]
                    yield _sse({"type": "token", "content": chunk})
                    await asyncio.sleep(0.01)

            if not full_text and stderr:
                full_text = f"Claude Code output:\n{stderr[:2000]}"
                yield _sse({"type": "token", "content": full_text})

            yield _sse({"type": "done", "content": full_text})
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("Claude Code stream error")
            yield _sse({"type": "error", "content": f"Unexpected error: {str(e)}"})
            yield "data: [DONE]\n\n"
        finally:
            if pairing_tokens:
                clear_pairing_context(pairing_tokens)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _cleanup_temp(registry, code: str, cmd: str):
    """Fire-and-forget cleanup of temp prompt file."""
    try:
        await registry.send_command_to_agent(code, cmd, timeout=5)
    except Exception:
        pass


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

        # Check if gh CLI is installed
        try:
            gh_check = await registry.send_command_to_agent(code, "gh --version", timeout=10)
            if gh_check.get("exit_code", 1) != 0:
                clear_pairing_context(tokens)
                return JulesResponse(
                    success=False,
                    message="GitHub CLI (gh) is not installed on your laptop. Install it from https://cli.github.com/"
                )
        except Exception:
            clear_pairing_context(tokens)
            return JulesResponse(
                success=False,
                message="Could not connect to laptop or GitHub CLI not found."
            )

        # Detect OS for command construction
        os_check = await registry.send_command_to_agent(code, "uname 2>nul || echo Windows", timeout=5)
        is_windows = "Windows" in os_check.get("stdout", "").strip() or os_check.get("stdout", "").strip() == ""

        # Detect repo from workspace or use provided
        repo = request.repo
        if not repo and request.workspace_root:
            try:
                if is_windows:
                    ws_escaped = request.workspace_root.replace("'", "''")
                    repo_cmd = f"powershell -Command \"cd '{ws_escaped}'; gh repo view --json nameWithOwner -q .nameWithOwner\""
                else:
                    repo_cmd = f'cd "{request.workspace_root}" && gh repo view --json nameWithOwner -q .nameWithOwner'

                result = await registry.send_command_to_agent(code, repo_cmd, timeout=15)
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

        # Use base64 encoding to avoid shell escaping issues
        title_b64 = base64.b64encode(title.encode('utf-8')).decode('ascii')
        body_b64 = base64.b64encode(body.encode('utf-8')).decode('ascii')

        # Build gh command based on OS
        # Jules is a GitHub bot - assignee should match the bot's GitHub username
        if is_windows:
            # On Windows, use PowerShell to decode base64 and pass to gh
            cmd = f'powershell -Command "$title = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(\'{title_b64}\')); $body = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(\'{body_b64}\')); gh issue create --repo \'{repo}\' --title $title --body $body --assignee \'jules\'"'
        else:
            # On Unix, use command substitution
            cmd = f'gh issue create --repo "{repo}" --title "$(echo {title_b64} | base64 -d)" --body "$(echo {body_b64} | base64 -d)" --assignee "jules"'

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
