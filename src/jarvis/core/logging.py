"""
Structured logging for JARVIS.

Provides consistent, JSON-formatted logging across all components.
"""

import logging
import sys
from datetime import datetime
from typing import Any
import json


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colors."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Truncate logger name for readability
        name = record.name
        if name.startswith("jarvis."):
            name = name[7:]  # Remove "jarvis." prefix
        if len(name) > 20:
            name = name[:17] + "..."

        msg = f"{color}[{timestamp}] {record.levelname:<8}{self.RESET} {name:<20} | {record.getMessage()}"

        # Add extra fields if present
        if hasattr(record, "extra") and record.extra:
            extras = " ".join(f"{k}={v}" for k, v in record.extra.items())
            msg += f" | {extras}"

        return msg


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds context to all log messages."""

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra

        # Store extra for formatters
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        return msg, kwargs


def get_logger(
    name: str,
    level: int = logging.INFO,
    context: dict[str, Any] | None = None,
) -> ContextLogger:
    """
    Get a configured logger for a component.

    Args:
        name: Logger name (usually module path like "jarvis.agent.planner")
        level: Logging level
        context: Additional context to include in all log messages

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(level)

        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ConsoleFormatter())
        logger.addHandler(console_handler)

        # Prevent propagation to root logger
        logger.propagate = False

    return ContextLogger(logger, context or {})


def setup_logging(
    level: str = "INFO",
    json_output: bool = False,
) -> None:
    """
    Setup global logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Use JSON formatting instead of console formatting
    """
    root_logger = logging.getLogger("jarvis")
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add appropriate handler
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(handler)
    root_logger.propagate = False


__all__ = ["get_logger", "setup_logging", "ContextLogger"]
