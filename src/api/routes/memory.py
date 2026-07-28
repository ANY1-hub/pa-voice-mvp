"""API routes for Working Memory and Semantic Memory."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.deps import get_semantic_memory, get_working_memory
from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation

router = APIRouter()


class WorkingMemoryRequest(BaseModel):
    """Request body for adding an item to Working Memory.

    Attributes:
        content: Text content of the memory item.
        importance_score: Score in ``[0.0, 1.0]`` (default ``0.5``).
    """

    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)


class SemanticMemoryRequest(BaseModel):
    """Request body for adding a fact to Semantic Memory.

    Attributes:
        content: Text content of the fact.
        importance_score: Score in ``[0.0, 1.0]`` (default ``0.7``).
        entities_involved: Optional list of related entity names.
    """

    content: str
    importance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    entities_involved: list[str] = Field(default_factory=list)


@router.post("/working")
async def add_working_memory(
    request: WorkingMemoryRequest,
    mem: WorkingMemory = Depends(get_working_memory),  # noqa: B008
):
    """Add a new item to the user's Working Memory.

    Args:
        request: Content and importance for the new item.
        mem: Injected WorkingMemory for the current user.

    Returns:
        Dict with ``status`` and the created item under ``data``.
    """
    try:
        item = await mem.add(
            content=request.content,
            importance=request.importance_score,
        )
        return {"status": "success", "data": item}
    except (InputValidationError, MemoryWritePolicyViolation) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {e.__class__.__name__}"
        ) from e


@router.get("/working")
async def retrieve_working_memory(
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    mem: WorkingMemory = Depends(get_working_memory),  # noqa: B008
):
    """Retrieve recent Working Memory items for the current user.

    Args:
        query: Optional case-insensitive substring filter.
        limit: Max items to return (1–100, default 20).
        mem: Injected WorkingMemory for the current user.

    Returns:
        Dict with ``status`` and the list of items under ``data``.
    """
    try:
        items = await mem.retrieve(query=query, limit=limit)
        return {"status": "success", "data": items}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {e.__class__.__name__}"
        ) from e


@router.post("/semantic")
async def add_semantic_memory(
    request: SemanticMemoryRequest,
    mem: SemanticMemory = Depends(get_semantic_memory),  # noqa: B008
):
    """Add a new long-term fact to the user's Semantic Memory.

    Args:
        request: Content, importance and optional entities.
        mem: Injected SemanticMemory for the current user.

    Returns:
        Dict with ``status`` and the created fact under ``data``.
    """
    try:
        fact = await mem.add_fact(
            fact=request.content,
            importance=request.importance_score,
            entities=request.entities_involved,
        )
        return {"status": "success", "data": fact}
    except (InputValidationError, MemoryWritePolicyViolation) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {e.__class__.__name__}"
        ) from e


@router.get("/semantic")
async def search_semantic_memory(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    mem: SemanticMemory = Depends(get_semantic_memory),  # noqa: B008
):
    """Search Semantic Memory for the current user (vector or text).

    Args:
        query: Free-text search query (required).
        limit: Max facts to return (1–50, default 10).
        mem: Injected SemanticMemory for the current user.

    Returns:
        Dict with ``status`` and the ranked facts under ``data``.
    """
    try:
        facts = await mem.search(query=query, limit=limit)
        return {"status": "success", "data": facts}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {e.__class__.__name__}"
        ) from e
