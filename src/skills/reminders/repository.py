"""Repository for structured Reminders (own MongoDB collection)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorCollection

from src.models.reminder import Reminder
from src.security.guardrails import validate_memory_write

logger = logging.getLogger(__name__)


class ReminderRepository:
    """CRUD for user-scoped reminders stored in a dedicated collection."""

    def __init__(
        self,
        user_id: str,
        collection: AsyncIOMotorCollection | None = None,
    ) -> None:
        self.user_id = user_id
        self.collection = collection

    async def create(
        self,
        content: str,
        due_at: datetime | None = None,
    ) -> Reminder:
        """Create and persist a new reminder.

        Performs the same write guardrails used by Semantic Memory.
        """
        fact_dict = {"content": content}
        validate_memory_write(fact_dict, importance_score=0.65, source="user")

        reminder = Reminder(
            user_id=self.user_id,
            content=content.strip(),
            due_at=due_at,
        )

        if self.collection is not None:
            await self.collection.insert_one(reminder.model_dump(mode="json"))

        return reminder

    async def list_reminders(
        self,
        limit: int = 20,
        status: str | None = "pending",
    ) -> list[Reminder]:
        """Return recent reminders for the current user (newest first)."""
        if self.collection is None:
            return []

        filters: dict = {"user_id": self.user_id}
        if status:
            filters["status"] = status

        cursor = self.collection.find(filters).sort("created_at", -1).limit(limit)

        reminders: list[Reminder] = []
        async for doc in cursor:
            doc.pop("_id", None)
            reminders.append(Reminder.model_validate(doc))
        return reminders

    async def touch(self, reminder_id: str) -> None:
        """Update last_accessed for a reminder."""
        if self.collection is None:
            return
        await self.collection.update_one(
            {"id": reminder_id, "user_id": self.user_id},
            {"$set": {"last_accessed": datetime.now(UTC).isoformat()}},
        )
