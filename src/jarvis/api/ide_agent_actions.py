"""
Deterministic IDE agent actions (git / shell) for reliable demos.

Parses natural-language intents and runs commands on the paired laptop or API host.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.ide_agent")


def _extract_commit_message(intent: str) -> str:
    quoted = re.search(r'["\']([^"\']{3,120})["\']', intent)
    if quoted:
        return quoted.group(1)
    m = re.search(
        r"(?:commit|with message|message)\s+(?:as\s+)?(.{3,120}?)(?:\s+and\s+push|\s+to\s+|\s*$)",
        intent,
        re.I,
    )
    if m:
        return m.group(1).strip().strip('"').strip("'")[:120]
    return "Update from JARVIS"


def _extract_branch(intent: str) -> str:
    m = re.search(r"\b(?:to|on|branch)\s+(main|master|develop|dev|\S+)\b", intent, re.I)
    if m:
        b = m.group(1).lower()
        if b in ("main", "master", "develop", "dev"):
            return b
    if "main" in intent.lower():
        return "main"
    if "master" in intent.lower():
        return "master"
    return "main"


def _shell_prefix(workspace: Optional[str]) -> str:
    if not workspace or not str(workspace).strip():
        return ""
    w = str(workspace).strip().replace('"', "")
    # Windows vs Unix
    if len(w) > 1 and w[1] == ":":
        return f'cd /d "{w}" && '
    return f'cd "{w}" && '


def parse_agent_intent(intent: str) -> Optional[dict[str, Any]]:
    """
    Return action spec if intent is a known workflow, else None.
    """
    t = intent.lower().strip()
    if not t:
        return None

    # git status
    if re.search(r"\bgit\s+status\b", t) or t in ("status", "git status"):
        return {"kind": "git_commands", "commands": ["git status -sb"], "summary": "Git status"}

    # pull
    if "pull" in t and ("git" in t or "sync" in t or "update" in t):
        return {"kind": "git_commands", "commands": ["git pull"], "summary": "Git pull"}

    # add + commit + push patterns
    wants_add = any(x in t for x in ("add", "stage", "git add"))
    wants_commit = "commit" in t
    wants_push = "push" in t

    if wants_commit or (wants_add and wants_push) or (wants_add and wants_commit):
        cmds: list[str] = []
        if wants_add or wants_commit:
            cmds.append("git add -A")
        if wants_commit:
            msg = _extract_commit_message(intent).replace('"', '\\"')
            cmds.append(f'git commit -m "{msg}"')
        if wants_push:
            branch = _extract_branch(intent)
            cmds.append(f"git push -u origin {branch}")
        if cmds:
            return {
                "kind": "git_commands",
                "commands": cmds,
                "summary": " -> ".join(cmds),
            }

    # generic git command passthrough: "run git log"
    m = re.search(r"(?:run\s+)?git\s+(.+)", intent, re.I)
    if m and len(m.group(1)) < 200:
        sub = m.group(1).strip()
        if sub and sub.lower() not in ("add",):
            return {
                "kind": "git_commands",
                "commands": [f"git {sub}"],
                "summary": f"git {sub}",
            }

    return None


async def run_agent_action(
    intent: str,
    *,
    pairing_code: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute a parsed agent action. Returns structured result for the IDE UI.
    """
    spec = parse_agent_intent(intent)
    if not spec:
        return {
            "handled": False,
            "success": False,
            "message": "No built-in action matched. Try Agent mode with a clearer git request, or use chat.",
            "steps": [],
        }

    prefix = _shell_prefix(workspace_root)
    steps: list[dict[str, Any]] = []
    all_ok = True

    for cmd in spec["commands"]:
        full = f"{prefix}{cmd}" if prefix else cmd
        step_out: dict[str, Any] = {"command": full, "success": False}

        try:
            if pairing_code:
                from jarvis.devices.agent_registry import get_agent_registry

                reg = get_agent_registry()
                raw = await reg.send_command_to_agent(
                    pairing_code.strip().upper(),
                    full,
                    timeout=180,
                )
                step_out["stdout"] = raw.get("stdout", "")
                step_out["stderr"] = raw.get("stderr", "")
                step_out["exit_code"] = raw.get("exit_code", -1)
                step_out["success"] = bool(raw.get("success")) and int(raw.get("exit_code", -1)) == 0
            else:
                from jarvis.api.v1.mobile import run_command

                result = await run_command(full, timeout=180)
                step_out["stdout"] = result.stdout or ""
                step_out["stderr"] = result.stderr or ""
                step_out["exit_code"] = result.exit_code
                step_out["success"] = result.status == "success"
        except Exception as e:
            step_out["error"] = str(e)
            step_out["success"] = False

        if not step_out["success"]:
            all_ok = False
        steps.append(step_out)

    lines = [f"**{spec['summary']}**", ""]
    for s in steps:
        icon = "[ok]" if s.get("success") else "[fail]"
        lines.append(f"{icon} `{s['command']}`")
        if s.get("stdout"):
            lines.append(s["stdout"].strip()[:2000])
        if s.get("stderr"):
            lines.append(s["stderr"].strip()[:500])
        if s.get("error"):
            lines.append(str(s["error"]))

    return {
        "handled": True,
        "success": all_ok,
        "message": "\n".join(lines),
        "steps": steps,
        "summary": spec["summary"],
    }


__all__ = ["parse_agent_intent", "run_agent_action"]
