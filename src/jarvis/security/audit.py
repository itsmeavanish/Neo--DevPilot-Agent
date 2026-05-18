"""
Append-only audit log for security-sensitive actions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.config import get_settings
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.security.audit")


def _audit_path() -> Path:
    settings = get_settings()
    base = Path(settings.data_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "audit.log"


def audit_log(
    action: str,
    *,
    pairing_code: str | None = None,
    detail: dict[str, Any] | None = None,
    success: bool | None = None,
) -> None:
    """Append one JSON line to the audit log (best-effort)."""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "pairing_code": pairing_code,
        "success": success,
        "detail": detail or {},
    }
    try:
        path = _audit_path()
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception as e:
        logger.warning("audit_log write failed: %s", e)


__all__ = ["audit_log"]
