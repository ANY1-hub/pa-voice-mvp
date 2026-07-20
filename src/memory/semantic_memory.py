"""Semantic Memory – long-term insights with Vector Search and temporal metadata."""

import math

from src.db.mongodb import db_client
from src.models.memory import SemanticMemoryFact
from src.security.guardrails import validate_memory_write
from src.services.embeddings.base import EmbeddingsAdapter


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
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
        embeddings_adapter: EmbeddingsAdapter | None = None,
    ) -> None:
        """Initialize Semantic Memory for a specific user."""
        self.user_id = user_id
        self.collection = (
            db_client.db["semantic_memory"] if db_client.db is not None else None
        )
        self.embeddings = embeddings_adapter

    async def add_fact(
        self,
        fact: str,
        importance: float = 0.7,
        entities: list[str] | None = None,
    ) -> SemanticMemoryFact:
        """
        Store a new long-term fact.

        Performs security validation and optionally creates an embedding.
        """
        # 1. Security Check
        fact_dict = {"content": fact}
        validate_memory_write(fact_dict, importance_score=importance, source="user")

        # 2. Embedding creation
        embedding = None
        if self.embeddings is not None:
            embedding = await self.embeddings.get_embedding(fact)

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
        """
        Search Semantic Memory for this user.

        Strategy:
        1. If an embeddings adapter is available → embed the query and rank
           stored facts by cosine similarity (in-memory, fine for MVP scale).
        2. Otherwise → case-insensitive text substring match on content.
        """
        if self.collection is None:
            return []

        # --- Vector path ---
        if self.embeddings is not None:
            query_embedding = await self.embeddings.get_embedding(query)
            cursor = self.collection.find(
                {
                    "user_id": self.user_id,
                    "embedding": {"$ne": None},
                }
            )
            scored: list[tuple[float, SemanticMemoryFact]] = []
            async for doc in cursor:
                doc.pop("_id", None)
                fact = SemanticMemoryFact.model_validate(doc)
                if fact.embedding:
                    score = _cosine_similarity(query_embedding, fact.embedding)
                    scored.append((score, fact))

            scored.sort(key=lambda pair: pair[0], reverse=True)
            return [fact for _, fact in scored[:limit]]

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
        results: list[SemanticMemoryFact] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(SemanticMemoryFact.model_validate(doc))
        return results

    async def consolidate(self) -> None:
        """
        Background consolidation job.
        Minimal Scope: Cleanup and deduplication.
        Prepared for Ambitioniert: Entity linking, drift detection.
        """
        if self.collection is None:
            return

        await self._cleanup_old_entries()
        await self._deduplicate()
        await self._link_entities()
        await self._detect_drift()

    async def _cleanup_old_entries(self) -> None:
        """Remove facts that are very old and have very low importance."""
        # Minimal implementation: Just a stub for now.
        # In a real scenario: self.collection.delete_many({"importance_score": {"$lt": 0.3}, "last_accessed": {"$lt": thirty_days_ago}})
        pass

    async def _deduplicate(self) -> None:
        """Detect and merge duplicate facts."""
        # Minimal implementation: Stub
        pass

    async def _link_entities(self) -> None:
        """Phase 2: Build graph relationships between entities."""
        pass

    async def _detect_drift(self) -> None:
        """Phase 2: Detect preference drift over time."""
        pass
