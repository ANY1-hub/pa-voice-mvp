"""Repository for structured Reminders (own MongoDB collection)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorCollection

from src.db.mongodb import contains_regex, mongo_document
from src.models.reminder import Reminder
from src.security.guardrails import validate_memory_write

logger = logging.getLogger(__name__)


def _persist_doc(reminder: Reminder) -> dict:
    """Insert document: UUID ``_id``, BSON dates for due/fired/created."""
    doc = mongo_document(reminder)
    for key in ("due_at", "fired_at", "created_at", "last_accessed"):
        value = getattr(reminder, key)
        if value is not None:
            doc[key] = value
    return doc


def _from_doc(doc: dict) -> Reminder:
    """Map a Mongo document to Reminder, dropping ``_id``."""
    doc.pop("_id", None)
    return Reminder.model_validate(doc)


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
        language: str | None = None,
    ) -> Reminder:
        """Create and persist a new reminder.

        Performs the same write guardrails used by Semantic Memory.
        ``due_at`` / ``fired_at`` are stored as BSON Date for comparisons.
        """
        fact_dict = {"content": content}
        validate_memory_write(fact_dict, importance_score=0.65, source="user")

        reminder = Reminder(
            user_id=self.user_id,
            content=content.strip(),
            due_at=due_at,
            language=language,
        )

        if self.collection is not None:
            await self.collection.insert_one(_persist_doc(reminder))

        return reminder

    async def list_reminders(
        self,
        limit: int = 20,
        status: str | None = "pending",
        due_from: datetime | None = None,
        due_to: datetime | None = None,
    ) -> list[Reminder]:
        """Return reminders for the current user, optionally filtered by due range.

        Args:
            limit: Max number of results.
            status: Filter by status (default "pending"). Pass None for any.
            due_from: Inclusive lower bound on due_at (UTC).
            due_to: Inclusive upper bound on due_at (UTC).
        """
        if self.collection is None:
            return []

        filters: dict = {"user_id": self.user_id}
        if status:
            filters["status"] = status

        if due_from is not None or due_to is not None:
            due_filter: dict = {}
            if due_from is not None:
                due_filter["$gte"] = due_from
            if due_to is not None:
                due_filter["$lte"] = due_to
            filters["due_at"] = due_filter

        cursor = self.collection.find(filters).sort("due_at", 1).limit(limit)

        reminders: list[Reminder] = []
        async for doc in cursor:
            reminders.append(_from_doc(doc))
        return reminders

    async def search_by_content(
        self,
        query: str,
        limit: int = 10,
        status: str | None = "pending",
    ) -> list[Reminder]:
        """Return reminders whose content contains the query (case-insensitive).

        Args:
            query: Free-text keyword to search for.
            limit: Max number of results.
            status: Filter by status (default "pending").
        """
        if self.collection is None:
            return []

        filters: dict = {
            "user_id": self.user_id,
            "content": contains_regex(query),
        }
        if status:
            filters["status"] = status

        cursor = self.collection.find(filters).sort("due_at", 1).limit(limit)

        reminders: list[Reminder] = []
        async for doc in cursor:
            reminders.append(_from_doc(doc))
        return reminders

    async def list_fired_unacked(self, limit: int = 20) -> list[Reminder]:
        """Return pending reminders that have already fired for this user."""
        if self.collection is None:
            return []
        cursor = (
            self.collection.find(
                {
                    "user_id": self.user_id,
                    "status": "pending",
                    "fired_at": {"$ne": None},
                }
            )
            .sort("due_at", 1)
            .limit(limit)
        )
        reminders: list[Reminder] = []
        async for doc in cursor:
            reminders.append(_from_doc(doc))
        return reminders

    async def acknowledge(self, reminder_id: str) -> Reminder | None:
        """Mark a fired reminder as done. Returns None if not found."""
        if self.collection is None:
            return None
        doc = await self.collection.find_one_and_update(
            {
                "id": reminder_id,
                "user_id": self.user_id,
                "status": "pending",
            },
            {"$set": {"status": "done", "last_accessed": datetime.now(UTC)}},
            return_document=True,
        )
        if doc is None:
            return None
        return _from_doc(doc)

    async def claim_due_for_user(
        self, now: datetime, *, limit: int = 20
    ) -> list[Reminder]:
        """Atomically mark this user's due reminders as fired."""
        if self.collection is None:
            return []
        return await claim_due_reminders(
            self.collection, now, user_id=self.user_id, limit=limit
        )

    async def touch(self, reminder_id: str) -> None:
        """Update last_accessed for a reminder."""
        if self.collection is None:
            return
        await self.collection.update_one(
            {"id": reminder_id, "user_id": self.user_id},
            {"$set": {"last_accessed": datetime.now(UTC)}},
        )


async def claim_due_reminders(
    collection: AsyncIOMotorCollection,
    now: datetime,
    *,
    user_id: str | None = None,
    limit: int = 50,
) -> list[Reminder]:
    """Atomically set ``fired_at`` on due pending reminders.

    Safe under concurrent scheduler + request polls: each document is
    claimed at most once via find_one_and_update.
    """
    claimed: list[Reminder] = []
    filters: dict = {
        "status": "pending",
        "due_at": {"$lte": now},
        "$or": [{"fired_at": None}, {"fired_at": {"$exists": False}}],
    }
    if user_id:
        filters["user_id"] = user_id

    for _ in range(limit):
        doc = await collection.find_one_and_update(
            filters,
            {"$set": {"fired_at": now, "last_accessed": now}},
            return_document=True,
        )
        if doc is None:
            break
        claimed.append(_from_doc(doc))
    return claimed
