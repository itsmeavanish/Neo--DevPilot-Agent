"""
Workflow API endpoints.

Endpoints for workflow management, execution, and monitoring.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from jarvis.workflows.engine import get_workflow_engine
from jarvis.workflows.models.workflow import TriggerType

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class WorkflowCreate(BaseModel):
    """Request to create a workflow."""
    definition: dict = Field(..., description="Workflow definition")


class WorkflowUpdate(BaseModel):
    """Request to update a workflow."""
    name: str | None = Field(default=None, description="Workflow name")
    description: str | None = Field(default=None, description="Description")
    enabled: bool | None = Field(default=None, description="Whether enabled")
    variables: dict | None = Field(default=None, description="Default variables")
    tags: list[str] | None = Field(default=None, description="Tags")


class WorkflowRun(BaseModel):
    """Request to run a workflow."""
    variables: dict[str, Any] | None = Field(default=None, description="Runtime variables")
    trigger_data: dict[str, Any] | None = Field(default=None, description="Trigger data")


class WorkflowResponse(BaseModel):
    """Workflow information response."""
    id: str
    name: str
    description: str | None
    enabled: bool
    status: str
    step_count: int
    trigger_count: int
    run_count: int
    success_count: int
    failure_count: int
    last_run_at: str | None
    tags: list[str]


class RunResponse(BaseModel):
    """Run information response."""
    id: str
    workflow_id: str
    status: str
    current_step_id: str | None
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None
    trigger_type: str
    error: str | None


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def get_engine():
    return get_workflow_engine()


def workflow_to_response(workflow) -> dict:
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "enabled": workflow.enabled,
        "status": workflow.status.value,
        "step_count": len(workflow.steps),
        "trigger_count": len(workflow.triggers),
        "run_count": workflow.run_count,
        "success_count": workflow.success_count,
        "failure_count": workflow.failure_count,
        "last_run_at": workflow.last_run_at.isoformat() if workflow.last_run_at else None,
        "tags": workflow.tags,
    }


# ═══════════════════════════════════════════════════════════════
# Workflow CRUD Endpoints
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=list[WorkflowResponse])
async def list_workflows(
    enabled_only: bool = Query(default=False, description="Only enabled workflows"),
    tag: str | None = Query(default=None, description="Filter by tag"),
):
    """
    List all workflows.
    """
    engine = get_engine()
    tags = [tag] if tag else None
    workflows = engine.list(enabled_only=enabled_only, tags=tags)
    return [workflow_to_response(w) for w in workflows]


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(request: WorkflowCreate):
    """
    Create a new workflow from definition.
    """
    engine = get_engine()

    try:
        workflow = engine.create(request.definition)
        return workflow_to_response(workflow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, include_steps: bool = Query(default=False)):
    """
    Get workflow details.
    """
    engine = get_engine()
    workflow = engine.get(workflow_id)

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    response = workflow_to_response(workflow)

    if include_steps:
        response["steps"] = [s.to_dict() for s in workflow.steps]
        response["triggers"] = [t.to_dict() for t in workflow.triggers]

    return response


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, request: WorkflowUpdate):
    """
    Update a workflow.
    """
    engine = get_engine()

    updates = {k: v for k, v in request.dict().items() if v is not None}

    try:
        workflow = engine.update(workflow_id, updates)
        return workflow_to_response(workflow)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """
    Delete a workflow.
    """
    engine = get_engine()

    if not engine.delete(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")

    return {"deleted": workflow_id}


# ═══════════════════════════════════════════════════════════════
# Workflow Execution Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/{workflow_id}/run", response_model=RunResponse)
async def run_workflow(
    workflow_id: str,
    request: WorkflowRun | None = None,
    background_tasks: BackgroundTasks = None,
    async_run: bool = Query(default=False, description="Run asynchronously"),
):
    """
    Run a workflow.

    Use async_run=true to run in background and return immediately.
    """
    engine = get_engine()

    workflow = engine.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    variables = request.variables if request else None
    trigger_data = request.trigger_data if request else None

    if async_run and background_tasks:
        # Run in background
        async def run_async():
            await engine.run(
                workflow_id,
                trigger_type=TriggerType.MANUAL,
                trigger_data=trigger_data,
                variables=variables,
            )

        background_tasks.add_task(run_async)

        return {
            "id": "pending",
            "workflow_id": workflow_id,
            "status": "queued",
            "current_step_id": None,
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "trigger_type": "manual",
            "error": None,
        }

    try:
        run = await engine.run(
            workflow_id,
            trigger_type=TriggerType.MANUAL,
            trigger_data=trigger_data,
            variables=variables,
        )
        return run.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, run_id: str = Query(...)):
    """
    Cancel a running workflow.
    """
    engine = get_engine()

    if await engine.cancel(run_id):
        return {"cancelled": run_id}

    raise HTTPException(status_code=404, detail="Run not found or not running")


@router.get("/{workflow_id}/runs", response_model=list[RunResponse])
async def get_workflow_runs(
    workflow_id: str,
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get run history for a workflow.
    """
    engine = get_engine()

    workflow = engine.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    runs = engine.get_run_history(workflow_id=workflow_id, limit=limit)
    return [r.to_dict() for r in runs]


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """
    Get details of a specific run.
    """
    engine = get_engine()

    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run.to_dict()


# ═══════════════════════════════════════════════════════════════
# Trigger Management Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/{workflow_id}/triggers/enable")
async def enable_triggers(workflow_id: str):
    """
    Enable all triggers for a workflow.
    """
    engine = get_engine()

    try:
        count = await engine.enable_triggers(workflow_id)
        return {"enabled": count}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{workflow_id}/triggers/disable")
async def disable_triggers(workflow_id: str):
    """
    Disable all triggers for a workflow.
    """
    engine = get_engine()

    if await engine.disable_triggers(workflow_id):
        return {"disabled": True}

    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/triggers/webhook/{workflow_id}")
async def webhook_trigger(
    workflow_id: str,
    payload: dict = {},
):
    """
    Webhook endpoint to trigger a workflow.
    """
    engine = get_engine()

    workflow = engine.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Check for webhook trigger
    webhook_trigger = None
    for trigger in workflow.triggers:
        if trigger.trigger_type == TriggerType.WEBHOOK and trigger.enabled:
            webhook_trigger = trigger
            break

    if not webhook_trigger:
        raise HTTPException(status_code=400, detail="No webhook trigger configured")

    try:
        run = await engine.run(
            workflow_id,
            trigger_type=TriggerType.WEBHOOK,
            trigger_data=payload,
        )
        return {"run_id": run.id, "status": run.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Utility Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/validate")
async def validate_workflow(definition: dict):
    """
    Validate a workflow definition without creating it.
    """
    from jarvis.workflows.parser import parse_workflow, WorkflowParseError

    try:
        workflow = parse_workflow(definition)
        errors = workflow.validate()
        return {
            "valid": not errors,
            "errors": errors,
            "step_count": len(workflow.steps),
            "trigger_count": len(workflow.triggers),
        }
    except WorkflowParseError as e:
        return {
            "valid": False,
            "errors": [str(e)],
        }


@router.get("/templates")
async def get_templates():
    """
    Get example workflow templates.
    """
    return {
        "templates": [
            {
                "name": "Simple Build",
                "description": "Run build and test",
                "definition": {
                    "name": "Simple Build",
                    "steps": [
                        {"name": "Install", "tool": "shell", "params": {"command": "npm install"}},
                        {"name": "Build", "tool": "shell", "params": {"command": "npm run build"}},
                        {"name": "Test", "tool": "shell", "params": {"command": "npm test"}},
                    ],
                },
            },
            {
                "name": "Git Commit Workflow",
                "description": "Stage, commit, and push changes",
                "definition": {
                    "name": "Git Commit Workflow",
                    "variables": {"message": "Update"},
                    "steps": [
                        {"name": "Stage", "tool": "git", "params": {"action": "add", "files": ["."]}},
                        {"name": "Commit", "tool": "git", "params": {"action": "commit", "message": "${message}"}},
                        {"name": "Push", "tool": "git", "params": {"action": "push"}},
                    ],
                },
            },
            {
                "name": "File Watch Deploy",
                "description": "Deploy on file changes",
                "definition": {
                    "name": "File Watch Deploy",
                    "triggers": [
                        {"type": "file_watch", "paths": ["./src"], "patterns": ["*.ts", "*.tsx"]},
                    ],
                    "steps": [
                        {"name": "Build", "tool": "shell", "params": {"command": "npm run build"}},
                        {"name": "Deploy", "tool": "shell", "params": {"command": "npm run deploy"}},
                    ],
                },
            },
        ],
    }



# ═══════════════════════════════════════════════════════════════
# AI Workflow Generation
# ═══════════════════════════════════════════════════════════════

_WORKFLOW_SYSTEM = """You are an expert at creating JARVIS automation workflows.
Given a plain-English description, generate a complete workflow definition as a JSON object.

The JSON schema is:
{
  "name": "<short name>",
  "description": "<brief description>",
  "version": "1.0",
  "triggers": [   // optional
    {
      "type": "manual|schedule|file_watch|webhook",
      // for schedule: "cron": "*/5 * * * *"
      // for file_watch: "path": "./src", "patterns": ["*.py"]
    }
  ],
  "variables": { "key": "default_value" },  // optional
  "steps": [
    {
      "id": "<unique_id>",
      "name": "<step name>",
      "type": "tool",
      "tool": "shell_execute",
      "params": { "command": "..." },
      "depends_on": [],   // optional list of step ids
      "on_error": "stop|continue|retry"
    }
  ]
}

Available tools: shell_execute, git, file_read, file_write, system_info, docker_ps, docker_build, log_tail.

Return ONLY valid JSON with no extra text or markdown fences."""


class WorkflowGenerateRequest(BaseModel):
    description: str = Field(
        ...,
        description="Natural-language description of the workflow you want to create",
        examples=["Run pytest, then build a Docker image, then deploy to staging"],
    )
    create: bool = Field(
        default=False,
        description="If true, automatically register the generated workflow",
    )


class WorkflowGenerateResponse(BaseModel):
    definition: dict
    workflow_id: str | None = None
    message: str


@router.post("/generate", response_model=WorkflowGenerateResponse)
async def generate_workflow(request: WorkflowGenerateRequest):
    """
    Describe a workflow in plain English and let the AI generate it.

    Set ``create=true`` to immediately register the generated workflow.
    """
    from jarvis.api.v1.chat import _get_llm_client
    import json, re

    llm = await _get_llm_client()
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider available. Configure Ollama or set JARVIS_OPENAI_API_KEY.",
        )

    try:
        raw = await llm.chat(
            messages=[{"role": "user", "content": request.description}],
            system=_WORKFLOW_SYSTEM,
        )

        # Extract JSON
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            raise HTTPException(status_code=500, detail=f"LLM did not return valid JSON: {raw[:200]}")

        definition = json.loads(json_match.group())

    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Could not parse generated workflow: {exc}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    workflow_id = None
    if request.create:
        try:
            engine = get_engine()
            workflow = engine.create(definition)
            workflow_id = workflow.id
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Generated workflow is invalid: {exc}")

    return WorkflowGenerateResponse(
        definition=definition,
        workflow_id=workflow_id,
        message="Workflow generated" + (" and registered" if workflow_id else ""),
    )


__all__ = ["router"]
