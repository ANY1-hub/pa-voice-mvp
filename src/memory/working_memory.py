"""Working Memory – short-term context with TTL and importance scoring."""

from src.db.mongodb import db_client
from src.models.memory import WorkingMemoryItem
from src.security.guardrails import validate_memory_write


class WorkingMemory:
    """Short-term memory store for the current session / recent interactions."""

    def __init__(self, user_id: str) -> None:
        """Initialize Working Memory for a specific user."""
        self.user_id = user_id
        self.collection = (
            db_client.db["working_memory"] if db_client.db is not None else None
        )

    async def add(self, content: str, importance: float = 0.5) -> WorkingMemoryItem:
        """
        Add a new item to Working Memory.

        Performs security validation before persisting.
        """
        # 1. Security Check
        fact_dict = {"content": content}
        validate_memory_write(fact_dict, importance_score=importance, source="user")

        # 2. Model Validation
        item = WorkingMemoryItem(
            user_id=self.user_id,
            content=content,
            importance_score=importance,
        )

        # 3. Persistence
        if self.collection is not None:
            await self.collection.insert_one(item.model_dump(mode="json"))

        return item

    async def retrieve(
        self,
        query: str | None = None,
        limit: int = 20,
    ) -> list[WorkingMemoryItem]:
        """
        Retrieve recent Working Memory items for this user.

        Optional `query` filters by case-insensitive substring match on content.
        Results are ordered by last_accessed descending.
        """
        if self.collection is None:
            return []

        filters: dict = {"user_id": self.user_id}
        if query:
            filters["content"] = {"$regex": query, "$options": "i"}

        cursor = (
            self.collection.find(filters)
            .sort("last_accessed", -1)
            .limit(limit)
        )

        items: list[WorkingMemoryItem] = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(WorkingMemoryItem.model_validate(doc))
        return items
