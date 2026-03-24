"""
Security Middleware for JARVIS.

Implements multiple security layers:
1. API Key Authentication
2. Device Token Validation
3. Rate Limiting
4. IP Whitelisting (optional)
"""

import time
import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from jarvis.config import get_settings
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.security")

# Security headers
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
DEVICE_TOKEN_HEADER = APIKeyHeader(name="X-Device-Token", auto_error=False)


class RateLimiter:
    """
    Token bucket rate limiter.

    Limits requests per IP address to prevent abuse.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size

        # Track requests per IP
        self.minute_requests: dict[str, list[float]] = defaultdict(list)
        self.hour_requests: dict[str, list[float]] = defaultdict(list)

    def _clean_old_requests(self, ip: str):
        """Remove expired request timestamps."""
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        self.minute_requests[ip] = [
            t for t in self.minute_requests[ip] if t > minute_ago
        ]
        self.hour_requests[ip] = [
            t for t in self.hour_requests[ip] if t > hour_ago
        ]

    def is_allowed(self, ip: str) -> tuple[bool, Optional[str]]:
        """
        Check if a request from this IP is allowed.

        Returns:
            (allowed, error_message)
        """
        self._clean_old_requests(ip)
        now = time.time()

        # Check minute limit
        if len(self.minute_requests[ip]) >= self.requests_per_minute:
            return False, f"Rate limit exceeded. Max {self.requests_per_minute} requests per minute."

        # Check hour limit
        if len(self.hour_requests[ip]) >= self.requests_per_hour:
            return False, f"Rate limit exceeded. Max {self.requests_per_hour} requests per hour."

        # Allow and record
        self.minute_requests[ip].append(now)
        self.hour_requests[ip].append(now)
        return True, None

    def get_remaining(self, ip: str) -> dict:
        """Get remaining requests for an IP."""
        self._clean_old_requests(ip)
        return {
            "minute_remaining": self.requests_per_minute - len(self.minute_requests[ip]),
            "hour_remaining": self.requests_per_hour - len(self.hour_requests[ip]),
        }


class IPWhitelist:
    """
    IP Whitelist manager.

    When enabled, only allows requests from whitelisted IPs.
    """

    def __init__(self, enabled: bool = False, whitelist: list[str] = None):
        self.enabled = enabled
        self.whitelist = set(whitelist or [])

        # Always allow localhost
        self.whitelist.update(["127.0.0.1", "::1", "localhost"])

    def add(self, ip: str):
        """Add an IP to the whitelist."""
        self.whitelist.add(ip)

    def remove(self, ip: str):
        """Remove an IP from the whitelist."""
        self.whitelist.discard(ip)

    def is_allowed(self, ip: str) -> bool:
        """Check if an IP is allowed."""
        if not self.enabled:
            return True
        return ip in self.whitelist


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Main security middleware.

    Applies rate limiting and logs security events.
    """

    def __init__(self, app, rate_limiter: RateLimiter = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Skip rate limiting for health checks
        if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Apply rate limiting
        allowed, error_message = self.rate_limiter.is_allowed(client_ip)
        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": error_message},
                headers={"Retry-After": "60"},
            )

        # Add security headers to response
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP from request."""
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


# Dependency functions for FastAPI

async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Depends(API_KEY_HEADER),
) -> bool:
    """
    Verify the API key from request header.

    Usage:
        @app.get("/secure")
        async def secure_endpoint(verified: bool = Depends(verify_api_key)):
            ...
    """
    settings = get_settings()

    # If no API key configured, allow all (development mode)
    if not settings.api_key:
        return True

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Set X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.api_key):
        logger.warning(f"Invalid API key attempt from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return True


async def verify_device_token(
    request: Request,
    device_token: Optional[str] = Depends(DEVICE_TOKEN_HEADER),
):
    """
    Verify device token and return the device.

    Usage:
        @app.get("/device/command")
        async def device_command(device = Depends(verify_device_token)):
            ...
    """
    if not device_token:
        raise HTTPException(
            status_code=401,
            detail="Device token required. Set X-Device-Token header.",
        )

    from jarvis.devices.multi_device import get_device_registry

    registry = get_device_registry()
    device = registry.get_device_by_token(device_token)

    if not device:
        logger.warning(f"Invalid device token attempt from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid device token.",
        )

    return device


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging (don't log raw tokens)."""
    return hashlib.sha256(data.encode()).hexdigest()[:16]


# Global instances
_rate_limiter: Optional[RateLimiter] = None
_ip_whitelist: Optional[IPWhitelist] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            requests_per_minute=60,
            requests_per_hour=1000,
        )
    return _rate_limiter


def get_ip_whitelist() -> IPWhitelist:
    """Get the global IP whitelist."""
    global _ip_whitelist
    if _ip_whitelist is None:
        _ip_whitelist = IPWhitelist(enabled=False)
    return _ip_whitelist


__all__ = [
    "SecurityMiddleware",
    "RateLimiter",
    "IPWhitelist",
    "verify_api_key",
    "verify_device_token",
    "get_rate_limiter",
    "get_ip_whitelist",
]
