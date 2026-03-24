"""
Observability metrics models and collectors.

Provides metrics collection, aggregation, and export.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable
from threading import Lock

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.observability.metrics")


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"         # Monotonically increasing
    GAUGE = "gauge"             # Value that can go up/down
    HISTOGRAM = "histogram"     # Distribution of values
    SUMMARY = "summary"         # Similar to histogram with quantiles


@dataclass
class MetricLabel:
    """A label for a metric."""
    name: str
    value: str


@dataclass
class MetricValue:
    """A timestamped metric value."""
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class HistogramBucket:
    """A histogram bucket."""
    le: float  # Less than or equal
    count: int = 0


class Metric:
    """Base metric class."""

    def __init__(
        self,
        name: str,
        description: str = "",
        metric_type: MetricType = MetricType.GAUGE,
        labels: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.metric_type = metric_type
        self.label_names = labels or []
        self._lock = Lock()
        self._values: dict[tuple, MetricValue] = {}

    def _label_key(self, labels: dict[str, str]) -> tuple:
        """Create a hashable key from labels."""
        return tuple(sorted(labels.items()))

    def to_dict(self) -> dict[str, Any]:
        """Convert metric to dictionary."""
        with self._lock:
            return {
                "name": self.name,
                "description": self.description,
                "type": self.metric_type.value,
                "label_names": self.label_names,
                "values": [v.to_dict() for v in self._values.values()],
            }


class Counter(Metric):
    """A monotonically increasing counter."""

    def __init__(self, name: str, description: str = "", labels: list[str] | None = None):
        super().__init__(name, description, MetricType.COUNTER, labels)

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the counter."""
        if value < 0:
            raise ValueError("Counter can only be incremented")

        labels = labels or {}
        key = self._label_key(labels)

        with self._lock:
            if key not in self._values:
                self._values[key] = MetricValue(value=0, labels=labels)
            self._values[key].value += value
            self._values[key].timestamp = datetime.utcnow()

    def get(self, labels: dict[str, str] | None = None) -> float:
        """Get current counter value."""
        key = self._label_key(labels or {})
        with self._lock:
            if key in self._values:
                return self._values[key].value
        return 0.0


class Gauge(Metric):
    """A gauge that can go up and down."""

    def __init__(self, name: str, description: str = "", labels: list[str] | None = None):
        super().__init__(name, description, MetricType.GAUGE, labels)

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge value."""
        labels = labels or {}
        key = self._label_key(labels)

        with self._lock:
            self._values[key] = MetricValue(value=value, labels=labels)

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment the gauge."""
        labels = labels or {}
        key = self._label_key(labels)

        with self._lock:
            if key not in self._values:
                self._values[key] = MetricValue(value=0, labels=labels)
            self._values[key].value += value
            self._values[key].timestamp = datetime.utcnow()

    def dec(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement the gauge."""
        self.inc(-value, labels)

    def get(self, labels: dict[str, str] | None = None) -> float:
        """Get current gauge value."""
        key = self._label_key(labels or {})
        with self._lock:
            if key in self._values:
                return self._values[key].value
        return 0.0


class Histogram(Metric):
    """A histogram for measuring distributions."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

    def __init__(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ):
        super().__init__(name, description, MetricType.HISTOGRAM, labels)
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._bucket_counts: dict[tuple, dict[float, int]] = defaultdict(lambda: {b: 0 for b in self.buckets})
        self._sums: dict[tuple, float] = defaultdict(float)
        self._counts: dict[tuple, int] = defaultdict(int)

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a value."""
        labels = labels or {}
        key = self._label_key(labels)

        with self._lock:
            self._sums[key] += value
            self._counts[key] += 1

            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[key][bucket] += 1

    def get_count(self, labels: dict[str, str] | None = None) -> int:
        """Get observation count."""
        key = self._label_key(labels or {})
        with self._lock:
            return self._counts.get(key, 0)

    def get_sum(self, labels: dict[str, str] | None = None) -> float:
        """Get sum of observations."""
        key = self._label_key(labels or {})
        with self._lock:
            return self._sums.get(key, 0.0)

    def time(self, labels: dict[str, str] | None = None):
        """Context manager to time a block."""
        return _HistogramTimer(self, labels)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        with self._lock:
            result = super().to_dict()
            result["buckets"] = self.buckets
            result["bucket_counts"] = {
                str(k): v for k, v in self._bucket_counts.items()
            }
            result["sums"] = dict(self._sums)
            result["counts"] = dict(self._counts)
            return result


class _HistogramTimer:
    """Context manager for timing with histograms."""

    def __init__(self, histogram: Histogram, labels: dict[str, str] | None):
        self.histogram = histogram
        self.labels = labels
        self.start_time: float = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = time.perf_counter() - self.start_time
        self.histogram.observe(elapsed, self.labels)


class MetricsRegistry:
    """
    Central registry for all metrics.
    """

    def __init__(self):
        self._metrics: dict[str, Metric] = {}
        self._lock = Lock()

    def register(self, metric: Metric) -> Metric:
        """Register a metric."""
        with self._lock:
            self._metrics[metric.name] = metric
        return metric

    def get(self, name: str) -> Metric | None:
        """Get a metric by name."""
        return self._metrics.get(name)

    def counter(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Counter:
        """Create and register a counter."""
        metric = Counter(name, description, labels)
        return self.register(metric)

    def gauge(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Gauge:
        """Create and register a gauge."""
        metric = Gauge(name, description, labels)
        return self.register(metric)

    def histogram(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: tuple[float, ...] | None = None,
    ) -> Histogram:
        """Create and register a histogram."""
        metric = Histogram(name, description, labels, buckets)
        return self.register(metric)

    def collect(self) -> list[dict[str, Any]]:
        """Collect all metrics."""
        with self._lock:
            return [m.to_dict() for m in self._metrics.values()]

    def get_all(self) -> dict[str, Metric]:
        """Get all registered metrics."""
        return dict(self._metrics)


# ═══════════════════════════════════════════════════════════════
# Default Metrics
# ═══════════════════════════════════════════════════════════════

# Global registry
_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    return _registry


# Pre-defined metrics
request_count = _registry.counter(
    "jarvis_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

request_latency = _registry.histogram(
    "jarvis_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"],
)

active_tasks = _registry.gauge(
    "jarvis_active_tasks",
    "Number of active tasks",
    ["type"],
)

tool_executions = _registry.counter(
    "jarvis_tool_executions_total",
    "Total tool executions",
    ["tool", "status"],
)

tool_latency = _registry.histogram(
    "jarvis_tool_duration_seconds",
    "Tool execution duration",
    ["tool"],
)

memory_usage = _registry.gauge(
    "jarvis_memory_bytes",
    "Memory usage in bytes",
    ["type"],
)

llm_requests = _registry.counter(
    "jarvis_llm_requests_total",
    "Total LLM API requests",
    ["provider", "model", "status"],
)

llm_tokens = _registry.counter(
    "jarvis_llm_tokens_total",
    "Total LLM tokens used",
    ["provider", "model", "type"],
)

workflow_runs = _registry.counter(
    "jarvis_workflow_runs_total",
    "Total workflow runs",
    ["workflow", "status"],
)

device_tasks = _registry.counter(
    "jarvis_device_tasks_total",
    "Total device tasks",
    ["device", "status"],
)


__all__ = [
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
]
