"""Pydantic models for Working Memory and Semantic Memory."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        Timezone-aware ``datetime`` in UTC.
    """
    return datetime.now(UTC)


class WorkingMemoryItem(BaseModel):
    """Single item stored in short-term Working Memory.

    Attributes:
        user_id: Owner of the item.
        content: Text content.
        importance_score: Score in ``[0.0, 1.0]`` (default ``0.5``).
        created_at: Creation timestamp (UTC).
        last_accessed: Last access timestamp (UTC).
    """

    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)


class SemanticMemoryFact(BaseModel):
    """Long-term fact stored in Semantic Memory (with optional embedding).

    Attributes:
        user_id: Owner of the fact.
        content: Text content of the fact.
        importance_score: Score in ``[0.0, 1.0]`` (default ``0.5``).
        entities_involved: Related entity names.
        created_at: Creation timestamp (UTC).
        last_accessed: Last access timestamp (UTC).
        embedding: Optional vector embedding for similarity search.
    """

    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    entities_involved: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
    embedding: list[float] | None = None
