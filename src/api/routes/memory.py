"""API routes for Working Memory and Semantic Memory."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation

router = APIRouter()


class WorkingMemoryRequest(BaseModel):
    """Request body for adding an item to Working Memory."""

    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)


class SemanticMemoryRequest(BaseModel):
    """Request body for adding a fact to Semantic Memory."""

    user_id: str
    content: str
    importance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    entities_involved: list[str] = Field(default_factory=list)


@router.post("/working")
async def add_working_memory(request: WorkingMemoryRequest):
    """Add a new item to the user's Working Memory."""
    mem = WorkingMemory(user_id=request.user_id)
    try:
        item = await mem.add(
            content=request.content,
            importance=request.importance_score,
        )
        return {"status": "success", "data": item}
    except (InputValidationError, MemoryWritePolicyViolation) as e:
        err_msg = (
            f"[LLM_ERR: Validation pipeline failed: {e.__class__.__name__} - {str(e)}] "
            "[HUMAN_ERR: The system rejected this input due to security rules.]"
        )
        raise HTTPException(status_code=400, detail=err_msg) from e
    except Exception as e:
        err_msg = (
            f"[LLM_ERR: Unhandled exception in /working endpoint: {e.__class__.__name__} - {str(e)}] "
            "[HUMAN_ERR: An unexpected internal error occurred.]"
        )
        raise HTTPException(status_code=500, detail=err_msg) from e


@router.post("/semantic")
async def add_semantic_memory(request: SemanticMemoryRequest):
    """Add a new long-term fact to the user's Semantic Memory."""
    mem = SemanticMemory(user_id=request.user_id)
    try:
        fact = await mem.add_fact(
            fact=request.content,
            importance=request.importance_score,
            entities=request.entities_involved,
        )
        return {"status": "success", "data": fact}
    except (InputValidationError, MemoryWritePolicyViolation) as e:
        err_msg = (
            f"[LLM_ERR: Validation pipeline failed: {e.__class__.__name__} - {str(e)}] "
            "[HUMAN_ERR: The system rejected this input due to security rules.]"
        )
        raise HTTPException(status_code=400, detail=err_msg) from e
    except Exception as e:
        err_msg = (
            f"[LLM_ERR: Unhandled exception in /semantic endpoint: {e.__class__.__name__} - {str(e)}] "
            "[HUMAN_ERR: An unexpected internal error occurred.]"
        )
        raise HTTPException(status_code=500, detail=err_msg) from e
