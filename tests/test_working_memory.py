import pytest

from src.memory.working_memory import WorkingMemory


def test_working_memory_init():
    wm = WorkingMemory("12345678-1234-5678-1234-567812345678")
    assert wm.user_id == "12345678-1234-5678-1234-567812345678"
    # collection is None when no DB connection is available (normal in unit tests)
    assert wm.collection is None or hasattr(wm.collection, "insert_one")


@pytest.mark.asyncio
async def test_working_memory_add_success():
    """Successful write to Working Memory returns a valid item."""
    wm = WorkingMemory("12345678-1234-5678-1234-567812345678")
    item = await wm.add("I prefer dark mode", importance=0.6)

    assert item.user_id == "12345678-1234-5678-1234-567812345678"
    assert item.content == "I prefer dark mode"
    assert item.importance_score == 0.6
    assert item.created_at is not None
    assert item.last_accessed is not None
