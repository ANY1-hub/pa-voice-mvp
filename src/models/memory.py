from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc)

class WorkingMemoryItem(BaseModel):
    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)

class SemanticMemoryFact(BaseModel):
    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    entities_involved: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
    embedding: Optional[List[float]] = None
