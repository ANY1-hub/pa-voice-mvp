"""Working Memory – short-term context with TTL and importance scoring."""

from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorCollection

from src.db.mongodb import contains_regex, mongo_document
from src.models.memory import WorkingMemoryItem, assign_stable_id
from src.security.guardrails import validate_memory_write


class WorkingMemory:
    """Short-term memory store for the current session / recent interactions."""

    def __init__(
        self,
        user_id: str,
        collection: AsyncIOMotorCollection | None = None,
    ) -> None:
        """Initialize Working Memory for a specific user.

        Args:
            user_id: Owner of the memory items.
            collection: MongoDB collection to use. Pass ``None`` for unit tests
                that should not touch the database.
        """
        self.user_id = user_id
        self.collection = collection

    async def add(
        self,
        content: str,
        importance: float = 0.5,
        *,
        source: str = "user",
        correlation_id: str | None = None,
    ) -> WorkingMemoryItem:
        """Add a new item to Working Memory.

        Performs security validation before persisting.

        Args:
            content: Text content of the memory item.
            importance: Importance score in ``[0.0, 1.0]`` (default ``0.5``).
            source: Write origin. ``"system"`` skips the user injection
                blocklist so assistant replies can be stored.
            correlation_id: Optional chat-turn id shared by both sides of a turn.

        Returns:
            The created ``WorkingMemoryItem`` (also persisted when a collection
            is configured).

        Raises:
            InputValidationError / MemoryWritePolicyViolation: From guardrails
                when the content is rejected.
        """
        # 1. Security Check
        fact_dict = {"content": content}
        validate_memory_write(fact_dict, importance_score=importance, source=source)

        # 2. Model Validation
        item = WorkingMemoryItem(
            user_id=self.user_id,
            content=content,
            importance_score=importance,
            correlation_id=correlation_id,
        )

        # 3. Persistence
        if self.collection is not None:
            doc = mongo_document(item)
            # BSON Date so Mongo can TTL-expire the document.
            doc["expires_at"] = item.expires_at
            await self.collection.insert_one(doc)

        return item

    async def retrieve(
        self,
        query: str | None = None,
        limit: int = 20,
    ) -> list[WorkingMemoryItem]:
        """Retrieve recent Working Memory items for this user.

        Args:
            query: Optional case-insensitive substring filter on content.
            limit: Maximum number of items to return (default ``20``).

        Returns:
            List of ``WorkingMemoryItem``, ordered by ``last_accessed``
            descending. Empty list when no collection is configured.
        """
        if self.collection is None:
            return []

        now = datetime.now(UTC)
        filters: dict = {
            "user_id": self.user_id,
            "$or": [
                {"expires_at": {"$gt": now}},
                {"expires_at": {"$exists": False}},
            ],
        }
        if query:
            filters = {
                "$and": [
                    filters,
                    {"content": contains_regex(query)},
                ]
            }

        cursor = self.collection.find(filters).sort("last_accessed", -1).limit(limit)

        items: list[WorkingMemoryItem] = []
        async for doc in cursor:
            assign_stable_id(doc)
            doc.pop("_id", None)
            items.append(WorkingMemoryItem.model_validate(doc))
        return items
