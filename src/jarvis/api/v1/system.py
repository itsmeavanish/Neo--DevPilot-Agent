"""
System API endpoints.

Health checks, configuration, and system information.
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from jarvis.config import get_settings, Settings
from jarvis.tools import ToolRegistry
from jarvis.api.deps import get_tool_registry
from jarvis import __version__

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    checks: dict[str, dict]


class SystemInfo(BaseModel):
    """System information."""
    version: str
    tools_count: int
    llm_configured: bool
    debug: bool


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse)
async def health_check(
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    Health check endpoint.

    Verifies that all services are operational.
    """
    settings = get_settings()
    checks = {}

    # Check tools
    checks["tools"] = {
        "status": "ok" if len(registry) > 0 else "warning",
        "count": len(registry),
    }

    # Check LLM (if configured)
    if settings.ollama_host:
        try:
            from jarvis.llm.providers.ollama import OllamaClient
            client = OllamaClient(host=settings.ollama_host)
            llm_available = await client.is_available()
            checks["llm"] = {
                "status": "ok" if llm_available else "error",
                "provider": "ollama",
                "host": settings.ollama_host,
                "message": "Connected" if llm_available else "Ollama not running",
            }
        except Exception as e:
            checks["llm"] = {
                "status": "error",
                "provider": "ollama",
                "host": settings.ollama_host,
                "message": str(e),
            }
    else:
        checks["llm"] = {
            "status": "not_configured",
            "message": "Set JARVIS_OLLAMA_HOST to enable",
        }

    # Check Redis
    try:
        from jarvis.memory.short_term import get_short_term_memory
        stm = get_short_term_memory()
        redis_available = await stm.is_available()
        checks["redis"] = {
            "status": "ok" if redis_available else "warning",
            "message": "Connected" if redis_available else "Using in-memory fallback",
        }
    except Exception as e:
        checks["redis"] = {
            "status": "warning",
            "message": f"Fallback mode: {str(e)}",
        }

    # Check Kafka (if enabled)
    if getattr(settings, 'kafka_enabled', True):
        try:
            from jarvis.events.kafka_client import get_event_bus
            event_bus = get_event_bus()
            checks["kafka"] = {
                "status": "ok" if event_bus.is_connected else "warning",
                "message": "Connected" if event_bus.is_connected else "Using in-memory fallback",
                "bootstrap_servers": getattr(settings, 'kafka_bootstrap_servers', 'localhost:9092'),
            }
        except Exception as e:
            checks["kafka"] = {
                "status": "warning",
                "message": f"Fallback mode: {str(e)}",
            }
    else:
        checks["kafka"] = {
            "status": "disabled",
            "message": "Kafka disabled in settings",
        }

    # Overall status
    all_ok = all(c.get("status") == "ok" for c in checks.values())
    has_error = any(c.get("status") == "error" for c in checks.values())

    if has_error:
        overall_status = "unhealthy"
    elif all_ok:
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        timestamp=datetime.utcnow().isoformat() + "Z",
        checks=checks,
    )


@router.get("/info", response_model=SystemInfo)
async def system_info(
    registry: ToolRegistry = Depends(get_tool_registry),
):
    """
    Get system information.
    """
    settings = get_settings()

    return SystemInfo(
        version=__version__,
        tools_count=len(registry),
        llm_configured=bool(settings.ollama_host),
        debug=settings.debug,
    )


@router.get("/config")
async def get_config():
    """
    Get current configuration (safe values only).
    """
    settings = get_settings()

    return {
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "debug": settings.debug,
        "ollama_host": settings.ollama_host,
        "ollama_model": settings.ollama_model,
        "command_timeout": settings.command_timeout,
        "max_plan_steps": settings.max_plan_steps,
        "sandbox_enabled": settings.sandbox_enabled,
        "approval_required": settings.approval_required,
        "log_level": settings.log_level,
    }


__all__ = ["router"]
