"""
API Key Authentication Middleware.

Validates API key for protected endpoints.
"""

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from jarvis.config import get_settings
from jarvis.core.logging import get_logger

logger = get_logger("jarvis.api.auth")

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/system/health",
}


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Dependency to verify API key.

    Usage:
        @router.get("/protected")
        async def protected_route(api_key: str = Depends(verify_api_key)):
            ...
    """
    settings = get_settings()

    # Skip if no API key configured
    if not settings.api_key:
        return "no-auth"

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header.",
        )

    if api_key != settings.api_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return api_key


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate API key on all requests.

    Checks X-API-Key header against configured key.
    Public endpoints are exempted.
    """

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # Skip if no API key configured (development mode)
        if not settings.api_key:
            return await call_next(request)

        # Check if endpoint is public
        path = request.url.path
        if path in PUBLIC_ENDPOINTS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Missing API key. Provide X-API-Key header.",
                    "code": "MISSING_API_KEY",
                },
            )

        if api_key != settings.api_key:
            logger.warning(f"Invalid API key from {request.client.host}")
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Invalid API key",
                    "code": "INVALID_API_KEY",
                },
            )

        # Valid key, continue
        return await call_next(request)


__all__ = ["APIKeyMiddleware", "verify_api_key", "api_key_header"]
