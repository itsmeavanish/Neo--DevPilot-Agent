"""
Short-lived opaque session tokens bound to a pairing code (HMAC).

Not JWT — compact signed payload: base64url(exp|pairing)|sig
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from jarvis.config import get_settings


def _signing_key() -> bytes:
    s = get_settings()
    raw = (s.api_key or "jarvis-dev-insecure-change-me") + ":jarvis-session"
    return hashlib.sha256(raw.encode()).digest()


def mint_session_token(pairing_code: str, ttl_seconds: int = 3600) -> str:
    """Issue a token valid for ttl_seconds (default 1h)."""
    code = pairing_code.strip().upper()
    exp = int(time.time()) + max(60, min(ttl_seconds, 86400))
    payload = json.dumps({"p": code, "exp": exp}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    sig = hmac.new(_signing_key(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def verify_session_token(token: str) -> dict[str, Any] | None:
    """Return {"pairing_code": str} if valid and not expired; else None."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expect = hmac.new(_signing_key(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expect, sig):
        return None
    pad = "=" * (-len(body) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(body + pad))
    except Exception:
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    code = data.get("p")
    if not code or not isinstance(code, str):
        return None
    return {"pairing_code": code.strip().upper()}


__all__ = ["mint_session_token", "verify_session_token"]
