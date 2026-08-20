"""Pydantic models for Working Memory and Semantic Memory."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

WORKING_MEMORY_TTL = timedelta(hours=48)


def now_utc() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        Timezone-aware ``datetime`` in UTC.
    """
    return datetime.now(UTC)


def assign_stable_id(doc: dict[str, Any]) -> dict[str, Any]:
    """Ensure a memory document has an application ``id`` (UUID v4).

    New writes already store ``id``. Legacy rows only have Mongo ``_id``;
    we surface that as ``id`` so reads stay addressable without minting a
    different UUID on every retrieve. Callers must ``pop`` ``_id`` after.
    """
    mongo_id = doc.get("_id")
    if not doc.get("id") and mongo_id is not None:
        doc["id"] = str(mongo_id)
    elif not doc.get("id"):
        doc["id"] = str(uuid4())
    return doc


class WorkingMemoryItem(BaseModel):
    """Single item stored in short-term Working Memory.

    Attributes:
        id: Server-generated UUID v4 string.
        user_id: Owner of the item.
        content: Text content.
        importance_score: Score in ``[0.0, 1.0]`` (default ``0.5``).
        created_at: Creation timestamp (UTC).
        last_accessed: Last access timestamp (UTC).
        correlation_id: Optional chat-turn id that produced this item.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
    expires_at: datetime = Field(default_factory=lambda: now_utc() + WORKING_MEMORY_TTL)
    correlation_id: str | None = None


class SemanticMemoryFact(BaseModel):
    """Long-term fact stored in Semantic Memory (with optional embedding).

    Attributes:
        id: Server-generated UUID v4 string.
        user_id: Owner of the fact.
        content: Text content of the fact.
        importance_score: Score in ``[0.0, 1.0]`` (default ``0.5``).
        entities_involved: Related entity names.
        created_at: Creation timestamp (UTC).
        last_accessed: Last access timestamp (UTC).
        embedding: Optional vector embedding for similarity search.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    content: str
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    entities_involved: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
    embedding: list[float] | None = None
    language: str | None = None
