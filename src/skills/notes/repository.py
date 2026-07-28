"""Repository for structured Notes (own MongoDB collection)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorCollection

from src.models.note import Note
from src.security.guardrails import validate_memory_write

logger = logging.getLogger(__name__)


class NoteRepository:
    """CRUD for user-scoped notes stored in a dedicated collection."""

    def __init__(
        self,
        user_id: str,
        collection: AsyncIOMotorCollection | None = None,
    ) -> None:
        """Initialize the repository for one user.

        Args:
            user_id: Owner of the notes.
            collection: MongoDB collection. Pass ``None`` for unit tests.
        """
        self.user_id = user_id
        self.collection = collection

    async def create(
        self,
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> Note:
        """Create and persist a new note.

        Performs the same write guardrails used by Semantic Memory.

        Args:
            content: Main note body (required).
            title: Optional short title.
            tags: Optional list of tags.

        Returns:
            The created ``Note``.

        Raises:
            InputValidationError / MemoryWritePolicyViolation: From guardrails.
        """
        # Re-use existing memory write policy (importance default for notes)
        fact_dict = {"content": content}
        validate_memory_write(fact_dict, importance_score=0.6, source="user")

        note = Note(
            user_id=self.user_id,
            content=content.strip(),
            title=title.strip() if title else None,
            tags=tags or [],
        )

        if self.collection is not None:
            await self.collection.insert_one(note.model_dump(mode="json"))

        return note

    async def list_notes(
        self,
        limit: int = 20,
        query: str | None = None,
    ) -> list[Note]:
        """Return recent notes for the current user.

        Args:
            limit: Maximum number of notes (default 20).
            query: Optional case-insensitive substring filter on content/title.

        Returns:
            List of ``Note``, newest first. Empty when no collection is set.
        """
        if self.collection is None:
            return []

        filters: dict = {"user_id": self.user_id}
        if query:
            # Simple OR on title or content
            filters["$or"] = [
                {"content": {"$regex": query, "$options": "i"}},
                {"title": {"$regex": query, "$options": "i"}},
            ]

        cursor = (
            self.collection.find(filters)
            .sort("created_at", -1)
            .limit(limit)
        )

        notes: list[Note] = []
        async for doc in cursor:
            doc.pop("_id", None)
            notes.append(Note.model_validate(doc))
        return notes

    async def touch(self, note_id: str) -> None:
        """Update last_accessed for a note (optional helper)."""
        if self.collection is None:
            return
        await self.collection.update_one(
            {"id": note_id, "user_id": self.user_id},
            {"$set": {"last_accessed": datetime.now(UTC).isoformat()}},
        )
