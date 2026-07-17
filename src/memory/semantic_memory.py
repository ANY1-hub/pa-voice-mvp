# Semantic Memory - long-term insights with Vector Search and Temporal Graph metadata
from __future__ import annotations

from src.models.memory import SemanticMemoryFact
from src.security.guardrails import validate_memory_write
from src.db.mongodb import db_client
from src.services.embeddings.base import EmbeddingsAdapter


class SemanticMemory:
    def __init__(
        self,
        user_id: str,
        embeddings_adapter: EmbeddingsAdapter | None = None,
    ):
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

    async def search(self, query: str):
        # Implementation for vector search placeholder
        pass

    async def consolidate(self):
        # Background job idea: find contradictions, link data, detect drift
        pass
