"""
Observability for JARVIS.

Provides metrics, tracing, logging, and health monitoring.
"""

from jarvis.observability.metrics import (
    MetricType,
    MetricValue,
    Metric,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_registry,
    # Pre-defined metrics
    request_count,
    request_latency,
    active_tasks,
    tool_executions,
    tool_latency,
    memory_usage,
    llm_requests,
    llm_tokens,
    workflow_runs,
    device_tasks,
)
from jarvis.observability.tracing import (
    SpanKind,
    SpanStatus,
    SpanEvent,
    SpanLink,
    Span,
    Tracer,
    get_tracer,
    get_current_span,
    trace,
)
from jarvis.observability.dashboard import (
    SystemStats,
    ComponentHealth,
    ActivitySummary,
    DashboardAggregator,
    get_dashboard_aggregator,
)

__all__ = [
    # Metrics
    "MetricType",
    "MetricValue",
    "Metric",
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "get_registry",
    # Pre-defined metrics
    "request_count",
    "request_latency",
    "active_tasks",
    "tool_executions",
    "tool_latency",
    "memory_usage",
    "llm_requests",
    "llm_tokens",
    "workflow_runs",
    "device_tasks",
    # Tracing
    "SpanKind",
    "SpanStatus",
    "SpanEvent",
    "SpanLink",
    "Span",
    "Tracer",
    "get_tracer",
    "get_current_span",
    "trace",
    # Dashboard
    "SystemStats",
    "ComponentHealth",
    "ActivitySummary",
    "DashboardAggregator",
    "get_dashboard_aggregator",
]
