"""
Self-heal API endpoints.

Endpoints for health checking and issue resolution.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from jarvis.self_heal.engine import SelfHealEngine, get_self_heal_engine
from jarvis.self_heal.models.issue import ResolutionStatus

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class HealthCheckResponse(BaseModel):
    """Health check response."""
    healthy: bool
    summary: dict[str, int]
    issues: list[dict]
    last_check: str
    checks_performed: dict[str, bool]


class IssueResponse(BaseModel):
    """Issue details response."""
    id: str
    category: str
    severity: str
    title: str
    description: str
    details: dict[str, Any]
    source: str
    affected_resource: str
    suggested_resolution: str | None
    auto_resolvable: bool
    requires_approval: bool
    detected_at: str


class ResolutionRequest(BaseModel):
    """Request to resolve an issue."""
    issue_id: str = Field(..., description="ID of issue to resolve")
    approved: bool = Field(default=True, description="Whether resolution is approved")


class ResolutionResponse(BaseModel):
    """Resolution result response."""
    id: str
    issue_id: str
    status: str
    resolver: str
    action_taken: str
    success: bool
    error: str | None
    output: str | None
    steps_executed: list[dict]
    duration_ms: int | None


class ConfigureRequest(BaseModel):
    """Request to configure self-heal engine."""
    project_root: str | None = Field(default=None, description="Project root path")
    ports: list[int] | None = Field(default=None, description="Ports to monitor")
    auto_resolve: bool | None = Field(default=None, description="Enable auto-resolve")
    require_approval: bool | None = Field(default=None, description="Require approval")
    monitor_interval: float | None = Field(default=None, description="Monitor interval (seconds)")


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def get_engine() -> SelfHealEngine:
    """Get self-heal engine instance."""
    return get_self_heal_engine()


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthCheckResponse)
async def check_health():
    """
    Run health check on all monitors.

    Returns system health status including any detected issues.
    """
    engine = get_engine()
    status = await engine.check_health()
    return status.to_dict()


@router.get("/issues", response_model=list[IssueResponse])
async def list_issues(
    severity: str | None = Query(default=None, description="Filter by severity"),
    category: str | None = Query(default=None, description="Filter by category"),
    resolvable_only: bool = Query(default=False, description="Only auto-resolvable issues"),
):
    """
    List all active issues.

    Returns issues detected by health monitoring.
    """
    engine = get_engine()
    issues = engine.get_active_issues()

    # Apply filters
    if severity:
        issues = [i for i in issues if i.severity.value == severity]
    if category:
        issues = [i for i in issues if i.category.value == category]
    if resolvable_only:
        issues = [i for i in issues if i.auto_resolvable]

    return [i.to_dict() for i in issues]


@router.get("/issues/{issue_id}", response_model=IssueResponse)
async def get_issue(issue_id: str):
    """Get details of a specific issue."""
    engine = get_engine()

    if issue_id not in engine.active_issues:
        raise HTTPException(status_code=404, detail="Issue not found")

    return engine.active_issues[issue_id].to_dict()


@router.post("/resolve", response_model=ResolutionResponse)
async def resolve_issue(request: ResolutionRequest):
    """
    Resolve a specific issue.

    Requires approval if the issue has requires_approval=True.
    """
    engine = get_engine()

    if request.issue_id not in engine.active_issues:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue = engine.active_issues[request.issue_id]
    resolution = await engine.resolve_issue(issue, approved=request.approved)

    return resolution.to_dict()


@router.post("/resolve-all", response_model=list[ResolutionResponse])
async def resolve_all_issues(
    approved: bool = Query(default=True, description="Pre-approve all resolutions"),
    max_issues: int = Query(default=10, ge=1, le=50, description="Maximum issues to resolve"),
):
    """
    Attempt to resolve all auto-resolvable issues.

    Will process issues in order of severity (critical first).
    """
    engine = get_engine()

    async def auto_approve(issue, action):
        return approved

    resolutions = await engine.auto_resolve(
        approval_callback=auto_approve if approved else None,
        max_issues=max_issues,
    )

    return [r.to_dict() for r in resolutions]


@router.get("/history", response_model=list[ResolutionResponse])
async def get_resolution_history(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
    status: str | None = Query(default=None, description="Filter by status"),
):
    """
    Get history of resolution attempts.
    """
    engine = get_engine()
    history = engine.get_resolution_history(limit=limit)

    if status:
        try:
            status_enum = ResolutionStatus(status)
            history = [r for r in history if r.status == status_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    return [r.to_dict() for r in history]


@router.post("/configure")
async def configure_engine(request: ConfigureRequest):
    """
    Configure the self-heal engine.

    Allows setting project root, monitored ports, and behavior options.
    """
    engine = get_engine()

    if request.project_root:
        engine.set_project_root(request.project_root)

    if request.ports:
        engine.set_ports_to_monitor(request.ports)

    if request.auto_resolve is not None:
        engine.auto_resolve_enabled = request.auto_resolve

    if request.require_approval is not None:
        engine.require_approval = request.require_approval

    return {
        "configured": True,
        "project_root": str(engine.project_root) if engine.project_root else None,
        "auto_resolve_enabled": engine.auto_resolve_enabled,
        "require_approval": engine.require_approval,
    }


@router.post("/monitoring/start")
async def start_monitoring(
    background_tasks: BackgroundTasks,
    interval: float = Query(default=60.0, ge=10.0, le=3600.0, description="Check interval (seconds)"),
):
    """
    Start background health monitoring.

    The engine will periodically check health and optionally auto-resolve issues.
    """
    engine = get_engine()
    background_tasks.add_task(engine.start_monitoring, interval)

    return {
        "started": True,
        "interval_seconds": interval,
    }


@router.post("/monitoring/stop")
async def stop_monitoring():
    """
    Stop background health monitoring.
    """
    engine = get_engine()
    await engine.stop_monitoring()

    return {"stopped": True}


@router.delete("/issues/clear")
async def clear_resolved_issues():
    """
    Clear all resolved issues from tracking.
    """
    engine = get_engine()
    cleared = engine.clear_resolved_issues()

    return {
        "cleared": cleared,
        "remaining": len(engine.active_issues),
    }


@router.get("/resolvers")
async def list_resolvers():
    """
    List available auto-resolvers.
    """
    engine = get_engine()

    return [
        {
            "name": r.name,
            "description": r.description,
            "enabled": r.enabled,
            "handles": [c.value for c in r.handles],
        }
        for r in engine.resolvers
    ]


@router.get("/monitors")
async def list_monitors():
    """
    List available health monitors.
    """
    engine = get_engine()

    return [
        {
            "name": m.name,
            "description": m.description,
            "enabled": m.enabled,
        }
        for m in engine.monitors
    ]


__all__ = ["router"]
