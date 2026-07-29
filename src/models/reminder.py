"""Pydantic model for Reminders (Phase 4 Skills)."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class Reminder(BaseModel):
    """Structured reminder stored in its own collection.

    Attributes:
        id: Server-generated UUID v4 string.
        user_id: Owner of the reminder.
        content: Main reminder text (required).
        due_at: Optional due datetime (UTC). None = no specific time.
        status: pending | done | cancelled.
        created_at: Creation timestamp (UTC).
        last_accessed: Last access / update timestamp (UTC).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    content: str
    due_at: datetime | None = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed: datetime = Field(default_factory=now_utc)
