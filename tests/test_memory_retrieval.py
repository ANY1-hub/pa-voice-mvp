from unittest.mock import AsyncMock

import pytest

from src.memory.semantic_memory import SemanticMemory, _cosine_similarity
from src.memory.working_memory import WorkingMemory
from src.services.embeddings.base import EmbeddingsAdapter


def test_cosine_similarity_identical_vectors():
    vec = [1.0, 0.0, 0.0]
    assert _cosine_similarity(vec, vec) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_empty_or_mismatch():
    assert _cosine_similarity([], [1.0]) == 0.0
    assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0


@pytest.mark.asyncio
async def test_working_memory_retrieve_without_db():
    """Without a DB connection retrieve returns an empty list."""
    wm = WorkingMemory("user_1")
    assert wm.collection is None
    result = await wm.retrieve(query="anything")
    assert result == []


@pytest.mark.asyncio
async def test_semantic_memory_search_without_db():
    """Without a DB connection search returns an empty list."""
    mem = SemanticMemory("user_1")
    assert mem.collection is None
    result = await mem.search("python")
    assert result == []


@pytest.mark.asyncio
async def test_semantic_memory_search_skips_embeddings_without_db():
    """Without a DB connection we must not call the embeddings API."""
    mock_adapter = AsyncMock(spec=EmbeddingsAdapter)
    mock_adapter.get_embedding.return_value = [1.0, 0.0, 0.0]

    mem = SemanticMemory("user_1", embeddings_adapter=mock_adapter)
    result = await mem.search("hiking")

    assert result == []
    mock_adapter.get_embedding.assert_not_awaited()
