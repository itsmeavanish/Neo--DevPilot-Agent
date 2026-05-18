"""
Route natural-language intents to specialist personas (multi-agent light).
"""

from __future__ import annotations

SPECIALISTS = ("debug", "devops", "review", "git", "orchestrator")

_PREFIXES = {
    "debug": (
        "[Debug Agent] Focus on diagnostics, logs, repro steps, and minimal commands. "
    ),
    "devops": (
        "[DevOps Agent] Focus on services, ports, docker, deploy scripts, and health checks. "
    ),
    "review": (
        "[Code Review Agent] Focus on reading files, diffs, security and style issues; avoid destructive commands. "
    ),
    "git": (
        "[Git Agent] Focus on branch, status, diff, commit, and safe git workflows. "
    ),
    "orchestrator": (
        "[Orchestrator] Balance exploration and execution; prefer safe read-only steps first. "
    ),
}


def classify_specialist(intent: str) -> str:
    t = (intent or "").lower()
    if any(k in t for k in ("error", "bug", "fail", "crash", "exception", "trace", "stack", "502", "500")):
        return "debug"
    if any(k in t for k in ("docker", "deploy", "nginx", "kubernetes", "k8s", "compose", "systemctl", "port ")):
        return "devops"
    if any(k in t for k in ("review", "security", "lint", "smell", "quality")):
        return "review"
    if t.strip().startswith("git ") or t.strip() == "git status" or " git " in t:
        return "git"
    return "orchestrator"


def enhance_intent_for_specialist(intent: str, specialist: str | None = None) -> str:
    sp = specialist or classify_specialist(intent)
    if sp not in SPECIALISTS:
        sp = "orchestrator"
    return _PREFIXES[sp] + intent.strip()


__all__ = ["SPECIALISTS", "classify_specialist", "enhance_intent_for_specialist"]
