"""
Observability API endpoints.

Endpoints for metrics, tracing, health checks, and dashboard data.
"""

from typing import Any
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from jarvis.observability.metrics import get_registry
from jarvis.observability.tracing import get_tracer
from jarvis.observability.dashboard import get_dashboard_aggregator

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Metrics Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/metrics")
async def get_metrics():
    """
    Get all metrics in JSON format.
    """
    registry = get_registry()
    return {"metrics": registry.collect()}


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
@router.get("/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """
    Get metrics in Prometheus format.
    """
    registry = get_registry()
    lines = []

    for metric_data in registry.collect():
        name = metric_data["name"]
        metric_type = metric_data["type"]
        description = metric_data.get("description", "")

        # Add HELP and TYPE comments
        lines.append(f"# HELP {name} {description}")
        lines.append(f"# TYPE {name} {metric_type}")

        # Add values
        for value_data in metric_data.get("values", []):
            labels = value_data.get("labels", {})
            value = value_data.get("value", 0)

            if labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                lines.append(f"{name}{{{label_str}}} {value}")
            else:
                lines.append(f"{name} {value}")

        lines.append("")

    return "\n".join(lines)


@router.get("/metrics/{metric_name}")
async def get_metric(metric_name: str):
    """
    Get a specific metric.
    """
    registry = get_registry()
    metric = registry.get(metric_name)

    if not metric:
        return {"error": f"Metric not found: {metric_name}"}

    return metric.to_dict()


# ═══════════════════════════════════════════════════════════════
# Tracing Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/traces")
async def get_traces(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum traces to return"),
):
    """
    Get recent traces.
    """
    tracer = get_tracer()
    spans = tracer.get_spans(limit)
    return {
        "spans": [s.to_dict() for s in spans],
        "count": len(spans),
    }


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """
    Get all spans for a specific trace.
    """
    tracer = get_tracer()
    spans = tracer.get_trace(trace_id)

    if not spans:
        return {"error": f"Trace not found: {trace_id}"}

    return {
        "trace_id": trace_id,
        "spans": [s.to_dict() for s in spans],
        "count": len(spans),
    }


@router.delete("/traces")
async def clear_traces():
    """
    Clear all recorded traces.
    """
    tracer = get_tracer()
    tracer.clear()
    return {"cleared": True}


# ═══════════════════════════════════════════════════════════════
# Health Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {"status": "healthy", "service": "jarvis"}


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check with component status.
    """
    aggregator = get_dashboard_aggregator()
    health = await aggregator.get_all_health()

    all_healthy = all(c.healthy for c in health.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": {name: h.to_dict() for name, h in health.items()},
    }


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes-style readiness check.
    """
    aggregator = get_dashboard_aggregator()
    health = await aggregator.get_all_health()

    # Check critical components
    critical = ["database", "llm"]
    for comp in critical:
        if comp in health and not health[comp].healthy:
            return {"ready": False, "reason": f"{comp} not ready"}

    return {"ready": True}


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes-style liveness check.
    """
    # Simple check - if we can respond, we're alive
    return {"alive": True}


# ═══════════════════════════════════════════════════════════════
# Dashboard Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_dashboard():
    """
    Get complete dashboard data.
    """
    aggregator = get_dashboard_aggregator()
    return await aggregator.get_dashboard_data()


@router.get("/dashboard/overview")
async def get_overview():
    """
    Get service overview.
    """
    aggregator = get_dashboard_aggregator()
    return aggregator.get_overview()


@router.get("/dashboard/system")
async def get_system_stats():
    """
    Get system resource statistics.
    """
    aggregator = get_dashboard_aggregator()
    stats = await aggregator.get_system_stats()
    return stats.to_dict()


@router.get("/dashboard/activity")
async def get_activity():
    """
    Get activity summary.
    """
    aggregator = get_dashboard_aggregator()
    activity = await aggregator.get_activity_summary()
    return activity.to_dict()


@router.get("/dashboard/quick")
async def get_quick_stats():
    """
    Get quick stats (no async operations).
    """
    aggregator = get_dashboard_aggregator()
    return aggregator.get_quick_stats()


__all__ = ["router"]
