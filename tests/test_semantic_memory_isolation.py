"""Two-user tenant isolation for SemanticMemory search/find.

Production already filters ``user_id``. These tests use an in-memory collection
that honours the Mongo filter, so they fail if ``user_id`` is omitted from
``find`` (including the hybrid/vector path).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.memory.semantic_memory import SemanticMemory

USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_NOW = datetime(2026, 9, 1, tzinfo=UTC).isoformat()


def _fact(
    user_id: str,
    content: str,
    *,
    fact_id: str,
    embedding: list[float] | None = None,
    importance: float = 0.8,
) -> dict:
    return {
        "_id": fact_id,
        "id": fact_id,
        "user_id": user_id,
        "content": content,
        "importance_score": importance,
        "entities_involved": [],
        "created_at": _NOW,
        "last_accessed": _NOW,
        "embedding": embedding,
        "language": None,
    }


def _doc_matches(doc: dict, query: dict) -> bool:
    """Apply a subset of Mongo equality / $regex matching used by search."""
    for key, value in query.items():
        if isinstance(value, dict) and "$regex" in value:
            flags = re.IGNORECASE if "i" in str(value.get("$options", "")) else 0
            if re.search(value["$regex"], str(doc.get(key, "")), flags) is None:
                return False
        elif doc.get(key) != value:
            return False
    return True


class _FakeCursor:
    def __init__(self, items: list[dict]):
        self._items = [dict(item) for item in items]

    def sort(self, *args, **kwargs):
        return self

    def limit(self, n: int):
        self._items = self._items[:n]
        return self

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for item in self._items:
            yield dict(item)


class IsolatingCollection:
    """In-memory collection: omitting user_id from find returns every tenant."""

    def __init__(self, docs: list[dict]):
        self._docs = [dict(d) for d in docs]
        self.find_queries: list[dict] = []
        self.update_one = AsyncMock()

    def find(self, query: dict | None = None):
        query = dict(query or {})
        self.find_queries.append(query)
        matched = [d for d in self._docs if _doc_matches(d, query)]
        return _FakeCursor(matched)


def _seeded_collection() -> IsolatingCollection:
    return IsolatingCollection(
        [
            _fact(
                USER_A,
                "User A private fact ALPHA-SECRET",
                fact_id="a1",
                embedding=[1.0, 0.0, 0.0],
            ),
            _fact(
                USER_B,
                "User B private fact BRAVO-SECRET",
                fact_id="b1",
                embedding=[1.0, 0.0, 0.0],
            ),
        ]
    )


def _assert_find_scoped_to(collection: IsolatingCollection, user_id: str) -> None:
    assert collection.find_queries, "search must call collection.find"
    for query in collection.find_queries:
        assert "user_id" in query, "find must include user_id (tenant isolation)"
        assert query["user_id"] == user_id


@pytest.mark.asyncio
async def test_text_search_does_not_return_other_user_facts():
    """A's text search must not surface B's facts; fails if find omits user_id."""
    collection = _seeded_collection()
    mem = SemanticMemory(user_id=USER_A, collection=collection, embeddings_adapter=None)

    results = await mem.search("SECRET", limit=10)

    _assert_find_scoped_to(collection, USER_A)
    contents = [r.content for r in results]
    assert any("ALPHA-SECRET" in c for c in contents)
    assert all("BRAVO-SECRET" not in c for c in contents)
    assert all(r.user_id == USER_A for r in results)


@pytest.mark.asyncio
async def test_hybrid_vector_search_does_not_return_other_user_facts():
    """Vector/hybrid path must still be tenant-scoped even when cosine matches B."""
    collection = _seeded_collection()
    embeddings = AsyncMock()
    embeddings.get_embedding.return_value = [1.0, 0.0, 0.0]
    mem = SemanticMemory(
        user_id=USER_A,
        collection=collection,
        embeddings_adapter=embeddings,
    )

    results = await mem.search("SECRET", limit=10)

    _assert_find_scoped_to(collection, USER_A)
    contents = [r.content for r in results]
    assert any("ALPHA-SECRET" in c for c in contents)
    assert all("BRAVO-SECRET" not in c for c in contents)
    assert all(r.user_id == USER_A for r in results)


@pytest.mark.asyncio
async def test_top_facts_empty_query_does_not_return_other_user():
    """Blank query uses importance ranking and must still filter user_id."""
    collection = _seeded_collection()
    mem = SemanticMemory(user_id=USER_A, collection=collection, embeddings_adapter=None)

    results = await mem.search("   ", limit=10)

    _assert_find_scoped_to(collection, USER_A)
    assert all(r.user_id == USER_A for r in results)
    assert all("BRAVO-SECRET" not in r.content for r in results)
