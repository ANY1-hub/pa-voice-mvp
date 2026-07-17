import pytest

from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.security.exceptions import InputValidationError, MemoryWritePolicyViolation


@pytest.mark.asyncio
async def test_semantic_memory_rejects_unsafe_write():
    # Attempt to write a fact that violates policy (e.g., extremely low importance < 0.2)
    mem = SemanticMemory(user_id="test_user")

    with pytest.raises(MemoryWritePolicyViolation):
        await mem.add_fact("Unimportant detail", importance=0.1)


@pytest.mark.asyncio
async def test_semantic_memory_valid_write():
    mem = SemanticMemory(user_id="test_user")
    # Will not raise, should create and return model
    fact = await mem.add_fact(
        "The user likes Python", importance=0.8, entities=["Python", "User"]
    )

    assert fact.user_id == "test_user"
    assert fact.content == "The user likes Python"
    assert fact.importance_score == 0.8
    assert "Python" in fact.entities_involved


@pytest.mark.asyncio
async def test_working_memory_rejects_injection():
    mem = WorkingMemory(user_id="test_user")

    # Empty content should be blocked by validate_memory_fact
    with pytest.raises(InputValidationError):
        await mem.add("", importance=0.8)
