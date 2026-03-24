"""
Self-healing system for JARVIS.

Automatically detects and resolves common development issues.
"""

from jarvis.self_heal.engine import SelfHealEngine, get_self_heal_engine
from jarvis.self_heal.models.issue import (
    Issue, Resolution, HealthStatus,
    IssueSeverity, IssueCategory, ResolutionStatus,
)

__all__ = [
    "SelfHealEngine",
    "get_self_heal_engine",
    "Issue",
    "Resolution",
    "HealthStatus",
    "IssueSeverity",
    "IssueCategory",
    "ResolutionStatus",
]
