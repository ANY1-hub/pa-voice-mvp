from unittest.mock import AsyncMock

import pytest

from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation
from src.services.embeddings.base import EmbeddingsAdapter


@pytest.mark.asyncio
async def test_semantic_memory_rejects_unsafe_write():
    # Attempt to write a fact that violates policy (e.g., extremely low importance < 0.2)
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")

    with pytest.raises(MemoryWritePolicyViolation):
        await mem.add_fact("Unimportant detail", importance=0.1)


@pytest.mark.asyncio
async def test_semantic_memory_valid_write():
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")
    # Will not raise, should create and return model
    fact = await mem.add_fact(
        "The user likes Python", importance=0.8, entities=["Python", "User"]
    )

    assert fact.user_id == "550e8400-e29b-41d4-a716-446655440000"
    assert fact.content == "The user likes Python"
    assert fact.importance_score == 0.8
    assert "Python" in fact.entities_involved
    assert fact.embedding is None  # no adapter → no embedding


@pytest.mark.asyncio
async def test_semantic_memory_with_embeddings_adapter():
    """When an embeddings adapter is provided, the fact gets an embedding."""
    mock_adapter = AsyncMock(spec=EmbeddingsAdapter)
    mock_adapter.get_embedding.return_value = [0.1, 0.2, 0.3, 0.4]

    mem = SemanticMemory(
        user_id="550e8400-e29b-41d4-a716-446655440000", embeddings_adapter=mock_adapter
    )
    fact = await mem.add_fact("I love hiking in the Alps", importance=0.9)

    mock_adapter.get_embedding.assert_awaited_once_with("I love hiking in the Alps")
    assert fact.embedding == [0.1, 0.2, 0.3, 0.4]
    assert fact.content == "I love hiking in the Alps"
    assert fact.user_id == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_working_memory_rejects_injection():
    mem = WorkingMemory(user_id="550e8400-e29b-41d4-a716-446655440000")

    # Empty content should be blocked by validate_memory_fact
    with pytest.raises(InputValidationError):
        await mem.add("", importance=0.8)
