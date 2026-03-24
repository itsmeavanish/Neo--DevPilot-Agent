"""
Distributed tracing for JARVIS.

Provides span-based tracing compatible with OpenTelemetry concepts.
"""

import time
import contextvars
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Iterator
from uuid import uuid4
from contextlib import contextmanager

from jarvis.core.logging import get_logger

logger = get_logger("jarvis.observability.tracing")


# Context variable for current span
_current_span: contextvars.ContextVar["Span | None"] = contextvars.ContextVar(
    "current_span", default=None
)


class SpanKind(Enum):
    """Type of span."""
    INTERNAL = "internal"   # Internal operation
    SERVER = "server"       # Handling incoming request
    CLIENT = "client"       # Making outgoing request
    PRODUCER = "producer"   # Message producer
    CONSUMER = "consumer"   # Message consumer


class SpanStatus(Enum):
    """Span completion status."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanEvent:
    """An event within a span."""
    name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class SpanLink:
    """A link to another span."""
    trace_id: str
    span_id: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "attributes": self.attributes,
        }


@dataclass
class Span:
    """
    A span represents a single operation within a trace.
    """
    name: str
    trace_id: str = field(default_factory=lambda: str(uuid4()).replace("-", ""))
    span_id: str = field(default_factory=lambda: str(uuid4())[:16])
    parent_span_id: str | None = None

    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.UNSET
    status_message: str | None = None

    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None

    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    links: list[SpanLink] = field(default_factory=list)

    # For timing
    _start_perf: float = field(default_factory=time.perf_counter)

    @property
    def duration_ms(self) -> float | None:
        """Get span duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @property
    def is_recording(self) -> bool:
        """Check if span is still recording."""
        return self.end_time is None

    def set_attribute(self, key: str, value: Any) -> "Span":
        """Set an attribute on the span."""
        self.attributes[key] = value
        return self

    def set_attributes(self, attributes: dict[str, Any]) -> "Span":
        """Set multiple attributes."""
        self.attributes.update(attributes)
        return self

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> "Span":
        """Add an event to the span."""
        self.events.append(SpanEvent(
            name=name,
            attributes=attributes or {},
        ))
        return self

    def add_link(
        self,
        trace_id: str,
        span_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> "Span":
        """Add a link to another span."""
        self.links.append(SpanLink(
            trace_id=trace_id,
            span_id=span_id,
            attributes=attributes or {},
        ))
        return self

    def set_status(
        self,
        status: SpanStatus,
        message: str | None = None,
    ) -> "Span":
        """Set the span status."""
        self.status = status
        self.status_message = message
        return self

    def record_exception(
        self,
        exception: Exception,
        attributes: dict[str, Any] | None = None,
    ) -> "Span":
        """Record an exception in the span."""
        attrs = attributes or {}
        attrs.update({
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
        })
        self.add_event("exception", attrs)
        self.set_status(SpanStatus.ERROR, str(exception))
        return self

    def end(self) -> "Span":
        """End the span."""
        if self.end_time is None:
            self.end_time = datetime.utcnow()
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert span to dictionary."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "status_message": self.status_message,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "links": [l.to_dict() for l in self.links],
        }


class Tracer:
    """
    Creates and manages spans.
    """

    def __init__(self, name: str = "jarvis"):
        self.name = name
        self.logger = get_logger(f"jarvis.observability.tracing.{name}")
        self._spans: list[Span] = []
        self._max_spans = 1000
        self._exporters: list[Callable[[Span], None]] = []

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
        links: list[SpanLink] | None = None,
    ) -> Span:
        """
        Start a new span.

        Args:
            name: Span name
            kind: Span kind
            attributes: Initial attributes
            links: Links to other spans

        Returns:
            New span
        """
        parent = _current_span.get()

        span = Span(
            name=name,
            kind=kind,
            trace_id=parent.trace_id if parent else str(uuid4()).replace("-", ""),
            parent_span_id=parent.span_id if parent else None,
            attributes=attributes or {},
            links=links or [],
        )

        return span

    @contextmanager
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """
        Context manager for creating a span.

        Usage:
            with tracer.span("operation") as span:
                span.set_attribute("key", "value")
                # do work
        """
        span = self.start_span(name, kind, attributes)
        token = _current_span.set(span)

        try:
            yield span
            if span.status == SpanStatus.UNSET:
                span.set_status(SpanStatus.OK)
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.end()
            _current_span.reset(token)
            self._record_span(span)

    def _record_span(self, span: Span) -> None:
        """Record a completed span."""
        # Store span
        self._spans.append(span)
        if len(self._spans) > self._max_spans:
            self._spans = self._spans[-self._max_spans:]

        # Export
        for exporter in self._exporters:
            try:
                exporter(span)
            except Exception as e:
                self.logger.error(f"Span export failed: {e}")

    def add_exporter(self, exporter: Callable[[Span], None]) -> None:
        """Add a span exporter."""
        self._exporters.append(exporter)

    def get_spans(self, limit: int = 100) -> list[Span]:
        """Get recent spans."""
        return self._spans[-limit:]

    def get_trace(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace."""
        return [s for s in self._spans if s.trace_id == trace_id]

    def clear(self) -> None:
        """Clear all recorded spans."""
        self._spans.clear()


def get_current_span() -> Span | None:
    """Get the current span from context."""
    return _current_span.get()


def trace(
    name: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
):
    """
    Decorator to trace a function.

    Usage:
        @trace("my_operation")
        async def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                with _default_tracer.span(span_name, kind, attributes) as span:
                    span.set_attribute("function", func.__name__)
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with _default_tracer.span(span_name, kind, attributes) as span:
                    span.set_attribute("function", func.__name__)
                    return func(*args, **kwargs)
            return sync_wrapper

    return decorator


# Import asyncio for decorator
import asyncio

# Default tracer
_default_tracer = Tracer()


def get_tracer(name: str = "jarvis") -> Tracer:
    """Get or create a tracer."""
    if name == "jarvis":
        return _default_tracer
    return Tracer(name)


__all__ = [
    "SpanKind",
    "SpanStatus",
    "SpanEvent",
    "SpanLink",
    "Span",
    "Tracer",
    "get_tracer",
    "get_current_span",
    "trace",
]
