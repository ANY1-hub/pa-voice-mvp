from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Optional
from src.memory.working_memory import WorkingMemory
from src.memory.semantic_memory import SemanticMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation

router = APIRouter()

class WorkingMemoryRequest(BaseModel):
    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)

class SemanticMemoryRequest(BaseModel):
    user_id: str
    content: str
    importance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    entities_involved: Optional[List[str]] = Field(default_factory=list)

@router.post("/working")
async def add_working_memory(request: WorkingMemoryRequest):
    mem = WorkingMemory(user_id=request.user_id)
    try:
        item = await mem.add(content=request.content, importance=request.importance_score)
        return {"status": "success", "data": item}
    except (InputValidationError, MemoryWritePolicyViolation) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/semantic")
async def add_semantic_memory(request: SemanticMemoryRequest):
    mem = SemanticMemory(user_id=request.user_id)
    try:
        fact = await mem.add_fact(
            fact=request.content, 
            importance=request.importance_score,
            entities=request.entities_involved
        )
        return {"status": "success", "data": fact}
    except (InputValidationError, MemoryWritePolicyViolation) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
