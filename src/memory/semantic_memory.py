"""Semantic Memory – long-term insights with Vector Search and temporal metadata."""

import logging
import math
from datetime import UTC, datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorCollection

from src.models.memory import SemanticMemoryFact
from src.security.guardrails import validate_memory_write
from src.services.embeddings.base import EmbeddingsAdapter

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Similarity in ``[-1.0, 1.0]``, or ``0.0`` if vectors are invalid.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticMemory:
    """Long-term memory store backed by MongoDB + optional vector embeddings."""

    def __init__(
        self,
        user_id: str,
        collection: AsyncIOMotorCollection | None = None,
        embeddings_adapter: EmbeddingsAdapter | None = None,
    ) -> None:
        """Initialize Semantic Memory for a specific user.

        Args:
            user_id: Owner of the memory facts.
            collection: MongoDB collection to use. Pass ``None`` for unit tests
                that should not touch the database.
            embeddings_adapter: Optional adapter for vector embeddings.
        """
        self.user_id = user_id
        self.collection = collection
        self.embeddings = embeddings_adapter

    async def add_fact(
        self,
        fact: str,
        importance: float = 0.7,
        entities: list[str] | None = None,
    ) -> SemanticMemoryFact:
        """Store a new long-term fact.

        Performs security validation and optionally creates an embedding.

        Args:
            fact: Text content of the fact.
            importance: Importance score in ``[0.0, 1.0]`` (default ``0.7``).
            entities: Optional list of entity names involved in the fact.

        Returns:
            The created ``SemanticMemoryFact`` (also persisted when a collection
            is configured).

        Raises:
            InputValidationError / MemoryWritePolicyViolation: From guardrails
                when the content is rejected.
        """
        # 1. Security Check
        fact_dict = {"content": fact}
        validate_memory_write(fact_dict, importance_score=importance, source="user")

        # 2. Embedding creation (optional – never block the write)
        embedding = None
        if self.embeddings is not None:
            try:
                embedding = await self.embeddings.get_embedding(fact)
            except Exception:
                logger.exception("Embedding failed for fact – storing without vector")
                embedding = None

        # 3. Model validation
        memory_fact = SemanticMemoryFact(
            user_id=self.user_id,
            content=fact,
            importance_score=importance,
            entities_involved=entities or [],
            embedding=embedding,
        )

        # 4. Persistence
        if self.collection is not None:
            await self.collection.insert_one(memory_fact.model_dump(mode="json"))

        return memory_fact

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[SemanticMemoryFact]:
        """Search Semantic Memory for this user.

        Strategy:
        1. If an embeddings adapter is available → embed the query and rank
           stored facts by cosine similarity (in-memory, fine for MVP scale).
           On embedding failure → fall back to text search.
        2. Otherwise → case-insensitive text substring match on content.

        On every successful hit the fact is "touched":
        - last_accessed is set to now
        - importance_score is increased by 0.05 (capped at 1.0)

        Args:
            query: Free-text search query.
            limit: Maximum number of facts to return (default ``10``).

        Returns:
            Ranked list of ``SemanticMemoryFact``. Empty list when no collection
            is configured.
        """
        if self.collection is None:
            return []

        # --- Vector path (in-memory cosine) ---
        if self.embeddings is not None:
            try:
                query_embedding = await self.embeddings.get_embedding(query)
            except Exception:
                logger.exception("Query embedding failed – falling back to text search")
            else:
                cursor = self.collection.find(
                    {
                        "user_id": self.user_id,
                        "embedding": {"$ne": None},
                    }
                )
                scored: list[tuple[float, SemanticMemoryFact, object]] = []
                async for doc in cursor:
                    doc_id = doc.pop("_id", None)
                    fact = SemanticMemoryFact.model_validate(doc)
                    if fact.embedding:
                        score = _cosine_similarity(query_embedding, fact.embedding)
                        scored.append((score, fact, doc_id))

                scored.sort(key=lambda pair: pair[0], reverse=True)
                selected = scored[:limit]
                await self._touch_facts(
                    [(fact, doc_id) for _, fact, doc_id in selected]
                )
                return [fact for _, fact, _ in selected]

        # --- Text fallback ---
        cursor = (
            self.collection.find(
                {
                    "user_id": self.user_id,
                    "content": {"$regex": query, "$options": "i"},
                }
            )
            .sort("importance_score", -1)
            .limit(limit)
        )
        results: list[tuple[SemanticMemoryFact, object]] = []
        async for doc in cursor:
            doc_id = doc.pop("_id", None)
            fact = SemanticMemoryFact.model_validate(doc)
            results.append((fact, doc_id))

        await self._touch_facts(results)
        return [fact for fact, _ in results]

    async def _touch_facts(
        self, items: list[tuple[SemanticMemoryFact, object]]
    ) -> None:
        """Update last_accessed and apply a small importance boost for accessed facts."""
        if self.collection is None or not items:
            return

        now_iso = datetime.now(UTC).isoformat()
        for fact, doc_id in items:
            if doc_id is None:
                continue
            new_importance = min(1.0, fact.importance_score + 0.05)
            await self.collection.update_one(
                {"_id": doc_id, "user_id": self.user_id},
                {
                    "$set": {
                        "last_accessed": now_iso,
                        "importance_score": new_importance,
                    }
                },
            )

    async def consolidate(self) -> None:
        """Run background consolidation for this user's semantic facts.

        Minimal Scope (MVP):
        - Cleanup of very old + low-importance facts
        - Exact-content deduplication (keep highest importance)

        Prepared for later:
        - Entity linking
        - Preference drift detection
        """
        if self.collection is None:
            return

        await self._cleanup_old_entries()
        await self._deduplicate()
        await self._link_entities()
        await self._detect_drift()

    async def _cleanup_old_entries(self) -> None:
        """Remove facts that are very old and have very low importance."""
        if self.collection is None:
            return

        # Thresholds for MVP (conservative for long-term memory)
        importance_threshold = 0.25
        days_threshold = 30
        threshold_date = datetime.now(UTC) - timedelta(days=days_threshold)
        # Stored as ISO strings via model_dump(mode="json")
        threshold_iso = threshold_date.isoformat()

        result = await self.collection.delete_many(
            {
                "user_id": self.user_id,
                "importance_score": {"$lt": importance_threshold},
                "last_accessed": {"$lt": threshold_iso},
            }
        )
        if result.deleted_count > 0:
            logger.info(
                "Cleaned up %s old low-importance facts for user %s",
                result.deleted_count,
                self.user_id,
            )

    async def _deduplicate(self) -> None:
        """Remove exact duplicate facts (normalized content); keep highest importance."""
        if self.collection is None:
            return

        cursor = self.collection.find({"user_id": self.user_id})
        groups: dict[str, list[dict]] = {}

        async for doc in cursor:
            # Normalize for comparison
            key = doc.get("content", "").strip().lower()
            if not key:
                continue
            groups.setdefault(key, []).append(doc)

        deleted_total = 0
        for _key, docs in groups.items():
            if len(docs) <= 1:
                continue

            # Sort: highest importance first, then most recent last_accessed
            def sort_key(d: dict) -> tuple:
                imp = d.get("importance_score", 0.0)
                accessed = d.get("last_accessed") or ""
                return (imp, accessed)

            docs.sort(key=sort_key, reverse=True)
            # Keep first, delete the rest
            to_delete_ids = [d["_id"] for d in docs[1:]]
            if to_delete_ids:
                result = await self.collection.delete_many(
                    {"_id": {"$in": to_delete_ids}}
                )
                deleted_total += result.deleted_count

        if deleted_total > 0:
            logger.info(
                "Deduplicated %s facts for user %s",
                deleted_total,
                self.user_id,
            )

    async def _link_entities(self) -> None:
        """Prepared for later: build relationships between entities."""
        # Intentionally empty in MVP – extension point for ambitious consolidation
        pass

    async def _detect_drift(self) -> None:
        """Prepared for later: detect preference drift over time."""
        # Intentionally empty in MVP – extension point for ambitious consolidation
        pass
