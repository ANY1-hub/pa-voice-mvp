"""API routes for Working Memory and Semantic Memory."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.deps import get_semantic_memory, get_working_memory
from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation

router = APIRouter()


class WorkingMemoryRequest(BaseModel):
    """Request body for adding an item to Working Memory."""

    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)


class SemanticMemoryRequest(BaseModel):
    """Request body for adding a fact to Semantic Memory."""

    content: str
    importance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    entities_involved: list[str] = Field(default_factory=list)


@router.post("/working")
async def add_working_memory(
    request: WorkingMemoryRequest,
    mem: WorkingMemory = Depends(get_working_memory),  # noqa: B008
):
    """Add a new item to the user's Working Memory."""
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
    """Retrieve recent Working Memory items for the current user."""
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
    """Add a new long-term fact to the user's Semantic Memory."""
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
    """Search Semantic Memory for the current user (vector or text)."""
    try:
        facts = await mem.search(query=query, limit=limit)
        return {"status": "success", "data": facts}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {e.__class__.__name__}"
        ) from e
