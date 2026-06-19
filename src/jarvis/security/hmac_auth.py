"""
HMAC-SHA256 message authentication for WebSocket agent communication.

Provides signing and verification for all messages between the server
and desktop agents to prevent tampering and replay attacks.
"""

import hashlib
import hmac
import json
import secrets
import time
from typing import Optional


HMAC_TIMESTAMP_TOLERANCE_SECONDS = 30


def generate_shared_secret() -> str:
    """Generate a 32-byte hex shared secret for HMAC signing."""
    return secrets.token_hex(32)


def sign_message(payload: dict, shared_secret: str) -> dict:
    """
    Sign a message payload with HMAC-SHA256.

    Adds _hmac_signature and _hmac_timestamp fields to the payload.
    """
    timestamp = str(int(time.time()))
    canonical = _canonical_json(payload)
    sign_input = f"{timestamp}.{canonical}"
    signature = hmac.new(
        shared_secret.encode(), sign_input.encode(), hashlib.sha256
    ).hexdigest()
    return {**payload, "_hmac_timestamp": timestamp, "_hmac_signature": signature}


def verify_message(
    payload: dict, shared_secret: str, tolerance: int = HMAC_TIMESTAMP_TOLERANCE_SECONDS
) -> tuple[bool, Optional[str]]:
    """
    Verify HMAC signature on a message.

    Returns (valid, error_reason). error_reason is None on success.
    """
    signature = payload.get("_hmac_signature")
    timestamp_str = payload.get("_hmac_timestamp")

    if not signature or not timestamp_str:
        return False, "missing_hmac_fields"

    try:
        msg_time = int(timestamp_str)
    except (ValueError, TypeError):
        return False, "invalid_timestamp"

    now = int(time.time())
    if abs(now - msg_time) > tolerance:
        return False, "timestamp_expired"

    canonical = _canonical_json(payload)
    sign_input = f"{timestamp_str}.{canonical}"
    expected = hmac.new(
        shared_secret.encode(), sign_input.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return False, "signature_mismatch"

    return True, None


def _canonical_json(payload: dict) -> str:
    """Produce a deterministic JSON string for signing (excludes HMAC fields)."""
    filtered = {k: v for k, v in payload.items() if not k.startswith("_hmac_")}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":"))


__all__ = ["generate_shared_secret", "sign_message", "verify_message"]
