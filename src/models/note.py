"""Pydantic model for Notes (Phase 4 Skills)."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        Timezone-aware ``datetime`` in UTC.
    """
    return datetime.now(UTC)


class Note(BaseModel):
    """Structured note stored in its own collection.

    Attributes:
        id: Server-generated UUID v4 string.
        user_id: Owner of the note.
        title: Optional short title.
        content: Main note body (required).
        tags: Optional free-form tags.
        created_at: Creation timestamp (UTC).
        last_accessed: Last access / update timestamp (UTC).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    title: str | None = None
    content: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
