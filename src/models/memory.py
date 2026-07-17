"""Pydantic models for Working Memory and Semantic Memory."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class WorkingMemoryItem(BaseModel):
    """Single item stored in short-term Working Memory."""

    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)


class SemanticMemoryFact(BaseModel):
    """Long-term fact stored in Semantic Memory (with optional embedding)."""

    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    entities_involved: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
    embedding: list[float] | None = None
