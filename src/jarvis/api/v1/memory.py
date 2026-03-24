"""
Memory API endpoints.

Endpoints for storing, searching, and managing memories.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.memory.service import MemoryService, get_memory_service
from jarvis.memory.models.memory_item import MemoryItem, SearchResult
from jarvis.core.constants import MemoryType

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class StoreMemoryRequest(BaseModel):
    """Request to store a memory."""
    content: str = Field(..., description="Text content to remember")
    type: str = Field(default="context", description="Memory type: context, error, error_fix, pattern, preference")
    project_id: str | None = Field(default=None, description="Associated project")
    file_path: str | None = Field(default=None, description="Associated file path")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance score")
    tags: list[str] | None = Field(default=None, description="Tags for categorization")


class SearchRequest(BaseModel):
    """Request to search memories."""
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    types: list[str] | None = Field(default=None, description="Filter by memory types")
    project_id: str | None = Field(default=None, description="Filter by project")
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum similarity")


class MemoryResponse(BaseModel):
    """Response containing a memory item."""
    id: str
    type: str
    content: str
    project_id: str | None
    file_path: str | None
    tags: list[str]
    importance: float
    created_at: str


class SearchResultResponse(BaseModel):
    """Response from a search."""
    item: MemoryResponse
    similarity: float


class StoreErrorRequest(BaseModel):
    """Request to store an error."""
    error: str = Field(..., description="Error message")
    context: dict | None = Field(default=None, description="Context when error occurred")
    fix: str | None = Field(default=None, description="How the error was fixed")
    project_id: str | None = Field(default=None, description="Project ID")


class StorePatternRequest(BaseModel):
    """Request to store a pattern."""
    description: str = Field(..., description="What this pattern does")
    steps: list[dict] = Field(..., description="Sequence of steps")
    project_id: str | None = Field(default=None, description="Project ID")
    tags: list[str] | None = Field(default=None, description="Pattern tags")


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def _item_to_response(item: MemoryItem) -> MemoryResponse:
    """Convert MemoryItem to response model."""
    return MemoryResponse(
        id=item.id,
        type=item.type.value,
        content=item.content[:500] + "..." if len(item.content) > 500 else item.content,
        project_id=item.project_id,
        file_path=item.file_path,
        tags=item.tags,
        importance=item.importance,
        created_at=item.created_at.isoformat(),
    )


def _parse_memory_type(type_str: str) -> MemoryType:
    """Parse memory type string."""
    try:
        return MemoryType(type_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memory type: {type_str}. Valid types: {[t.value for t in MemoryType]}"
        )


async def get_memory() -> MemoryService:
    """Dependency to get memory service."""
    service = get_memory_service()
    await service.initialize()
    return service


# ═══════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════

@router.post("/store", response_model=MemoryResponse)
async def store_memory(
    request: StoreMemoryRequest,
    memory: MemoryService = Depends(get_memory),
):
    """
    Store a new memory.

    Creates a long-term memory with semantic embedding for later retrieval.
    """
    memory_type = _parse_memory_type(request.type)

    item = await memory.remember(
        content=request.content,
        memory_type=memory_type,
        project_id=request.project_id,
        file_path=request.file_path,
        metadata=request.metadata,
        importance=request.importance,
        tags=request.tags,
    )

    return _item_to_response(item)


@router.post("/search", response_model=list[SearchResultResponse])
async def search_memories(
    request: SearchRequest,
    memory: MemoryService = Depends(get_memory),
):
    """
    Search memories by semantic similarity.

    Returns memories most similar to the query, sorted by relevance.
    """
    type_filter = None
    if request.types:
        type_filter = [_parse_memory_type(t) for t in request.types]

    results = await memory.search(
        query=request.query,
        limit=request.limit,
        types=type_filter,
        project_id=request.project_id,
        min_similarity=request.min_similarity,
    )

    return [
        SearchResultResponse(
            item=_item_to_response(r.item),
            similarity=round(r.similarity, 4),
        )
        for r in results
    ]


@router.post("/error", response_model=MemoryResponse)
async def store_error(
    request: StoreErrorRequest,
    memory: MemoryService = Depends(get_memory),
):
    """
    Store an error and optionally its fix.

    Useful for learning from past errors and their solutions.
    """
    item = await memory.remember_error(
        error=request.error,
        context=request.context,
        fix=request.fix,
        project_id=request.project_id,
    )

    return _item_to_response(item)


@router.post("/pattern", response_model=MemoryResponse)
async def store_pattern(
    request: StorePatternRequest,
    memory: MemoryService = Depends(get_memory),
):
    """
    Store a successful execution pattern.

    Patterns can be retrieved later to handle similar requests.
    """
    item = await memory.remember_pattern(
        description=request.description,
        steps=request.steps,
        project_id=request.project_id,
        tags=request.tags,
    )

    return _item_to_response(item)


@router.get("/similar-errors")
async def find_similar_errors(
    error: str = Query(..., description="Error to find matches for"),
    limit: int = Query(default=5, ge=1, le=20),
    project_id: str | None = Query(default=None),
    memory: MemoryService = Depends(get_memory),
):
    """
    Find similar past errors and their fixes.

    Useful for auto-diagnosing recurring issues.
    """
    results = await memory.find_similar_errors(
        error=error,
        limit=limit,
        project_id=project_id,
    )

    return [
        {
            "error": r.item.content,
            "fix": r.item.metadata.get("fix"),
            "context": {k: v for k, v in r.item.metadata.items() if k != "fix"},
            "similarity": round(r.similarity, 4),
        }
        for r in results
    ]


@router.get("/patterns")
async def find_patterns(
    intent: str = Query(..., description="What you want to do"),
    limit: int = Query(default=5, ge=1, le=20),
    project_id: str | None = Query(default=None),
    memory: MemoryService = Depends(get_memory),
):
    """
    Find execution patterns matching an intent.

    Returns past successful patterns that might help with the current task.
    """
    results = await memory.find_patterns(
        intent=intent,
        limit=limit,
        project_id=project_id,
    )

    return [
        {
            "description": r.item.content,
            "steps": r.item.metadata.get("steps", []),
            "tags": r.item.tags,
            "similarity": round(r.similarity, 4),
        }
        for r in results
    ]


@router.get("/{memory_id}")
async def get_memory_by_id(
    memory_id: str,
    memory: MemoryService = Depends(get_memory),
):
    """Get a specific memory by ID."""
    item = await memory.get_memory(memory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory not found")

    return item.to_dict()


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    memory: MemoryService = Depends(get_memory),
):
    """Delete a memory."""
    deleted = await memory.forget(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"deleted": True, "id": memory_id}


@router.get("/stats/overview")
async def get_memory_stats(
    memory: MemoryService = Depends(get_memory),
):
    """Get memory system statistics."""
    stats = await memory.get_stats()
    return stats.to_dict()


@router.get("/health/check")
async def check_memory_health(
    memory: MemoryService = Depends(get_memory),
):
    """Check health of memory services."""
    return await memory.is_healthy()


__all__ = ["router"]
