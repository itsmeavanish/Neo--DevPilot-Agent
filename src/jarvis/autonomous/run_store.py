"""
In-memory store for autonomous runs waiting on human approval (TTL).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from jarvis.agent.models.plan import Plan
from jarvis.core.constants import ApprovalMode

TTL_SECONDS = 3600

_lock = asyncio.Lock()
_pending: dict[str, "PendingAutonomousRun"] = {}


@dataclass
class PendingAutonomousRun:
    task_id: str
    plan: Plan
    intent: str
    exec_context: dict[str, Any]
    approval_mode: ApprovalMode
    pairing_code: str
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


def _expired(p: PendingAutonomousRun) -> bool:
    return (time.time() - p.created_at) > TTL_SECONDS


async def put_pending(run: PendingAutonomousRun) -> None:
    async with _lock:
        _prune_locked()
        _pending[run.task_id] = run


async def get_pending(task_id: str) -> PendingAutonomousRun | None:
    async with _lock:
        _prune_locked()
        p = _pending.get(task_id)
        if p and _expired(p):
            _pending.pop(task_id, None)
            return None
        return p


async def pop_pending(task_id: str) -> PendingAutonomousRun | None:
    async with _lock:
        _prune_locked()
        p = _pending.pop(task_id, None)
        if p and _expired(p):
            return None
        return p


def _prune_locked() -> None:
    dead = [tid for tid, p in _pending.items() if _expired(p)]
    for tid in dead:
        _pending.pop(tid, None)


__all__ = ["PendingAutonomousRun", "put_pending", "get_pending", "pop_pending", "TTL_SECONDS"]
