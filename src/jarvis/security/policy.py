"""
Scoped permissions and shell risk assessment for paired execution.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import NamedTuple

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.security.policy")


class Capability(str, Enum):
    SHELL = "shell"
    READ_FS = "read_fs"
    WRITE_FS = "write_fs"
    GIT = "git"
    NETWORK = "network"


class CommandAssessment(NamedTuple):
    allowed: bool
    risk: str  # low | medium | high | critical
    reason: str | None


_BLOCKED_SUBSTRINGS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf .",
    "del /s /q c:\\",
    "format c:",
    ":(){:|:&};:",
    "> /dev/sda",
    "mkfs.",
    "dd if=",
    "powershell -enc",
    "certutil",
]

_WRITE_HINTS = re.compile(
    r"\b(rm|del|remove-item|rd\s+/s|format|mkfs|chmod\s+.*777|>\\s+/etc|setx|reg\s+add)\b",
    re.I,
)


def assess_shell_command(command: str, capabilities: frozenset[str]) -> CommandAssessment:
    """
    Decide if a shell command may run on the paired agent.

    - Blocks known-destructive patterns.
    - Requires write_fs for obviously mutating one-liners (heuristic).
    """
    raw = (command or "").strip()
    if not raw:
        return CommandAssessment(False, "low", "Empty command")

    lower = raw.lower()
    for bad in _BLOCKED_SUBSTRINGS:
        if bad.lower() in lower:
            logger.warning("Blocked command pattern: %s", bad)
            return CommandAssessment(False, "critical", f"Blocked pattern: {bad.strip()}")

    if Capability.SHELL.value not in capabilities and Capability.GIT.value not in capabilities:
        return CommandAssessment(False, "high", "Capability 'shell' or 'git' not granted")

    if _WRITE_HINTS.search(raw) and Capability.WRITE_FS.value not in capabilities:
        return CommandAssessment(False, "high", "Write-capable command requires write_fs capability")

    if any(x in lower for x in ("curl", "wget", "invoke-webrequest")) and Capability.NETWORK.value not in capabilities:
        return CommandAssessment(False, "high", "Network commands require network capability")

    risk = "medium" if _WRITE_HINTS.search(raw) else "low"
    return CommandAssessment(True, risk, None)


__all__ = ["Capability", "CommandAssessment", "assess_shell_command"]
