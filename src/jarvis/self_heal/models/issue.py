"""
Self-heal issue models.

Defines the structure of detected issues and their resolutions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class IssueSeverity(str, Enum):
    """Severity level of detected issues."""
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Potential problem, monitor
    ERROR = "error"         # Problem detected, action recommended
    CRITICAL = "critical"   # Severe problem, immediate action


class IssueCategory(str, Enum):
    """Category of detected issues."""
    PROCESS = "process"           # Process crashed/hung
    PORT = "port"                 # Port conflict
    DEPENDENCY = "dependency"     # Missing/broken dependency
    DISK = "disk"                 # Low disk space
    MEMORY = "memory"             # High memory usage
    SERVICE = "service"           # Service unavailable
    NETWORK = "network"           # Network connectivity
    PERMISSION = "permission"     # Permission denied
    CONFIG = "config"             # Configuration error


class ResolutionStatus(str, Enum):
    """Status of a resolution attempt."""
    PENDING = "pending"           # Not yet attempted
    IN_PROGRESS = "in_progress"   # Currently executing
    SUCCESS = "success"           # Successfully resolved
    FAILED = "failed"             # Resolution failed
    SKIPPED = "skipped"           # Skipped (user declined)
    MANUAL = "manual"             # Requires manual intervention


@dataclass
class Issue:
    """
    A detected system issue.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    category: IssueCategory = IssueCategory.PROCESS
    severity: IssueSeverity = IssueSeverity.WARNING

    # Description
    title: str = ""
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    # Context
    source: str = ""              # Which monitor detected this
    affected_resource: str = ""   # What's affected (process name, port, etc.)

    # Suggested resolution
    suggested_resolution: str | None = None
    auto_resolvable: bool = False
    requires_approval: bool = True

    # Timestamps
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "details": self.details,
            "source": self.source,
            "affected_resource": self.affected_resource,
            "suggested_resolution": self.suggested_resolution,
            "auto_resolvable": self.auto_resolvable,
            "requires_approval": self.requires_approval,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @property
    def is_critical(self) -> bool:
        return self.severity == IssueSeverity.CRITICAL

    @property
    def needs_action(self) -> bool:
        return self.severity in (IssueSeverity.ERROR, IssueSeverity.CRITICAL)


@dataclass
class Resolution:
    """
    Record of a resolution attempt.
    """
    id: str = field(default_factory=lambda: str(uuid4())[:12])
    issue_id: str = ""
    status: ResolutionStatus = ResolutionStatus.PENDING

    # What was done
    resolver: str = ""            # Which resolver handled this
    action_taken: str = ""
    steps_executed: list[dict] = field(default_factory=list)

    # Result
    success: bool = False
    error: str | None = None
    output: str | None = None

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Approval
    approved_by: str | None = None
    approved_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "status": self.status.value,
            "resolver": self.resolver,
            "action_taken": self.action_taken,
            "steps_executed": self.steps_executed,
            "success": self.success,
            "error": self.error,
            "output": self.output,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
        }

    @property
    def duration_ms(self) -> int | None:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None


@dataclass
class HealthStatus:
    """Overall system health status."""
    healthy: bool = True
    issues: list[Issue] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0
    critical: int = 0
    last_check: datetime = field(default_factory=datetime.utcnow)
    checks_performed: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "issues": [i.to_dict() for i in self.issues],
            "summary": {
                "warnings": self.warnings,
                "errors": self.errors,
                "critical": self.critical,
                "total": len(self.issues),
            },
            "last_check": self.last_check.isoformat(),
            "checks_performed": self.checks_performed,
        }


__all__ = [
    "IssueSeverity",
    "IssueCategory",
    "ResolutionStatus",
    "Issue",
    "Resolution",
    "HealthStatus",
]
