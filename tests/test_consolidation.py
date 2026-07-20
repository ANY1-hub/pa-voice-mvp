"""Tests for SemanticMemory consolidation (minimal scope)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.memory.semantic_memory import SemanticMemory


@pytest.fixture
def mock_collection():
    """Async mock of a MongoDB collection."""
    coll = AsyncMock()
    # delete_many returns a result object with deleted_count
    delete_result = MagicMock()
    delete_result.deleted_count = 0
    coll.delete_many.return_value = delete_result
    return coll


@pytest.mark.asyncio
async def test_consolidate_noop_when_no_collection():
    """consolidate() returns early if no DB collection is available."""
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")
    # collection is None by default in unit tests
    await mem.consolidate()  # must not raise


@pytest.mark.asyncio
async def test_cleanup_old_entries_deletes_matching(mock_collection):
    """_cleanup_old_entries issues the expected delete_many filter."""
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")
    mem.collection = mock_collection

    delete_result = MagicMock()
    delete_result.deleted_count = 2
    mock_collection.delete_many.return_value = delete_result

    await mem._cleanup_old_entries()

    mock_collection.delete_many.assert_awaited_once()
    call_args = mock_collection.delete_many.call_args[0][0]
    assert call_args["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert call_args["importance_score"] == {"$lt": 0.25}
    assert "$lt" in call_args["last_accessed"]


@pytest.mark.asyncio
async def test_deduplicate_removes_duplicates(mock_collection):
    """_deduplicate keeps the highest-importance fact and deletes the rest."""
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")
    mem.collection = mock_collection

    # Simulate two docs with same normalized content
    now = datetime.now(UTC).isoformat()
    older = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    docs = [
        {
            "_id": "id1",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "content": "I like dark mode",
            "importance_score": 0.6,
            "last_accessed": older,
        },
        {
            "_id": "id2",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "content": "I like dark mode",
            "importance_score": 0.9,
            "last_accessed": now,
        },
        {
            "_id": "id3",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "content": "Completely different fact",
            "importance_score": 0.7,
            "last_accessed": now,
        },
    ]

    async def fake_cursor():
        for d in docs:
            yield d

    mock_collection.find.return_value = fake_cursor()

    delete_result = MagicMock()
    delete_result.deleted_count = 1
    mock_collection.delete_many.return_value = delete_result

    await mem._deduplicate()

    # Should have called delete_many once for the lower-importance duplicate
    mock_collection.delete_many.assert_awaited()
    call_args = mock_collection.delete_many.call_args[0][0]
    assert "_id" in call_args
    assert "$in" in call_args["_id"]
    # The kept one is id2 (higher importance), so id1 should be deleted
    assert "id1" in call_args["_id"]["$in"]
    assert "id2" not in call_args["_id"]["$in"]


@pytest.mark.asyncio
async def test_deduplicate_no_action_on_unique(mock_collection):
    """No deletes when all contents are unique."""
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")
    mem.collection = mock_collection

    docs = [
        {
            "_id": "id1",
            "content": "Fact A",
            "importance_score": 0.8,
            "last_accessed": datetime.now(UTC).isoformat(),
        },
        {
            "_id": "id2",
            "content": "Fact B",
            "importance_score": 0.7,
            "last_accessed": datetime.now(UTC).isoformat(),
        },
    ]

    async def fake_cursor():
        for d in docs:
            yield d

    mock_collection.find.return_value = fake_cursor()

    await mem._deduplicate()

    # delete_many should not have been called (or only with empty, but we skip)
    # In implementation we only call when len > 1
    mock_collection.delete_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_and_drift_are_noop(mock_collection):
    """Extension points currently do nothing."""
    mem = SemanticMemory(user_id="550e8400-e29b-41d4-a716-446655440000")
    mem.collection = mock_collection

    await mem._link_entities()
    await mem._detect_drift()
    # no calls expected
    mock_collection.find.assert_not_called()
    mock_collection.delete_many.assert_not_called()
