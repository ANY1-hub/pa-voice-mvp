"""API routes for Working Memory and Semantic Memory."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.deps import get_current_user_id
from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation
from src.services.embeddings.openai import OpenAIEmbeddingsAdapter

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


def _get_embeddings_adapter() -> OpenAIEmbeddingsAdapter | None:
    """
    Create the embeddings adapter.

    Returns None if no API key is configured so the system can still run
    without embeddings during local development.
    """
    try:
        return OpenAIEmbeddingsAdapter()
    except Exception:
        return None


@router.post("/working")
async def add_working_memory(
    request: WorkingMemoryRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Add a new item to the user's Working Memory."""
    mem = WorkingMemory(user_id=user_id)
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


@router.post("/semantic")
async def add_semantic_memory(
    request: SemanticMemoryRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Add a new long-term fact to the user's Semantic Memory."""
    embeddings = _get_embeddings_adapter()
    mem = SemanticMemory(user_id=user_id, embeddings_adapter=embeddings)
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
