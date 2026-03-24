"""
Tests for the observability system.
"""

import pytest
import time


class TestObservabilityImports:
    """Test observability module imports."""

    def test_import_metrics(self):
        from jarvis.observability.metrics import (
            Metric,
            Counter,
            Gauge,
            Histogram,
            MetricsRegistry,
        )
        assert Counter is not None
        assert Gauge is not None
        assert Histogram is not None

    def test_import_tracing(self):
        from jarvis.observability.tracing import (
            SpanKind,
            SpanStatus,
            Span,
            Tracer,
            trace,
        )
        assert Span is not None
        assert Tracer is not None
        assert trace is not None

    def test_import_dashboard(self):
        from jarvis.observability.dashboard import DashboardAggregator
        assert DashboardAggregator is not None


class TestMetrics:
    """Test metrics functionality."""

    def test_counter(self):
        from jarvis.observability.metrics import Counter

        counter = Counter(
            name="test_counter",
            description="A test counter",
        )

        assert counter.get() == 0.0
        counter.inc()
        assert counter.get() == 1.0
        counter.inc(5)
        assert counter.get() == 6.0

    def test_gauge(self):
        from jarvis.observability.metrics import Gauge

        gauge = Gauge(
            name="test_gauge",
            description="A test gauge",
        )

        gauge.set(10)
        assert gauge.get() == 10.0
        gauge.inc(5)
        assert gauge.get() == 15.0
        gauge.dec(3)
        assert gauge.get() == 12.0

    def test_histogram(self):
        from jarvis.observability.metrics import Histogram

        histogram = Histogram(
            name="test_histogram",
            description="A test histogram",
            buckets=(0.1, 0.5, 1.0, 5.0),
        )

        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(2.0)

        # Check count
        assert histogram.get_count() == 3
        # Check sum
        assert histogram.get_sum() == pytest.approx(2.35, 0.01)

    def test_metrics_registry(self):
        from jarvis.observability.metrics import MetricsRegistry

        registry = MetricsRegistry()

        counter = registry.counter(
            name="registry_test_counter",
            description="Test counter",
        )

        assert counter is not None
        counter.inc()

        # Get the same counter
        same_counter = registry.get("registry_test_counter")
        assert same_counter is counter

    def test_collect_metrics(self):
        from jarvis.observability.metrics import MetricsRegistry

        registry = MetricsRegistry()
        counter = registry.counter("collect_test", "Test")
        counter.inc(5)

        collected = registry.collect()
        assert isinstance(collected, list)
        assert len(collected) > 0


class TestTracing:
    """Test distributed tracing functionality."""

    def test_span_creation(self):
        from jarvis.observability.tracing import Span, SpanKind, SpanStatus

        span = Span(
            name="test_span",
            kind=SpanKind.INTERNAL,
        )

        assert span.name == "test_span"
        assert span.trace_id is not None
        assert span.span_id is not None
        assert span.status == SpanStatus.UNSET

    def test_span_attributes(self):
        from jarvis.observability.tracing import Span, SpanKind

        span = Span(name="test", kind=SpanKind.INTERNAL)
        span.set_attribute("key", "value")
        span.set_attribute("number", 42)

        assert span.attributes["key"] == "value"
        assert span.attributes["number"] == 42

    def test_span_events(self):
        from jarvis.observability.tracing import Span, SpanKind

        span = Span(name="test", kind=SpanKind.INTERNAL)
        span.add_event("event_occurred", {"detail": "info"})

        assert len(span.events) == 1
        assert span.events[0]["name"] == "event_occurred"

    def test_tracer(self):
        from jarvis.observability.tracing import Tracer

        tracer = Tracer(service_name="test_service")

        span = tracer.start_span("operation")
        assert span is not None
        span.end()

        assert span.end_time is not None
        assert span.duration_ms >= 0

    def test_trace_decorator(self):
        from jarvis.observability.tracing import trace

        @trace("decorated_operation")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    @pytest.mark.asyncio
    async def test_async_trace_decorator(self):
        from jarvis.observability.tracing import trace

        @trace("async_operation")
        async def my_async_function():
            return "async_result"

        result = await my_async_function()
        assert result == "async_result"


class TestDashboard:
    """Test dashboard aggregation."""

    def test_dashboard_creation(self):
        from jarvis.observability.dashboard import DashboardAggregator

        dashboard = DashboardAggregator()
        assert dashboard is not None

    @pytest.mark.asyncio
    async def test_get_system_stats(self):
        from jarvis.observability.dashboard import DashboardAggregator

        dashboard = DashboardAggregator()
        stats = await dashboard.get_system_stats()

        assert stats is not None
        assert hasattr(stats, "cpu_percent")
        assert hasattr(stats, "memory_percent")

    @pytest.mark.asyncio
    async def test_get_dashboard_data(self):
        from jarvis.observability.dashboard import DashboardAggregator

        dashboard = DashboardAggregator()
        data = await dashboard.get_dashboard_data()

        assert isinstance(data, dict)
        assert "system" in data
        assert "timestamp" in data
