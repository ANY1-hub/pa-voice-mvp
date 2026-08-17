"""Unit tests for background scheduler / consolidation job."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks import scheduler as sched_mod
from src.tasks.scheduler import consolidation_job, start_scheduler, stop_scheduler


class AsyncCursor:
    """Minimal async iterator mimicking a Motor cursor."""

    def __init__(self, items: list):
        self._items = items

    def __aiter__(self):
        return self._aiter()

    async def _aiter(self):
        for item in self._items:
            yield item


# ---------------------------------------------------------------------------
# consolidation_job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidation_skips_when_db_none():
    """Job must no-op safely when DB is not connected."""
    with patch.object(sched_mod.db_client, "db", None):
        await consolidation_job()  # must not raise


@pytest.mark.asyncio
async def test_consolidation_promotes_high_importance_items():
    """High-importance working-memory items must be promoted to Semantic Memory and deleted."""
    working_coll = MagicMock()
    semantic_coll = MagicMock()

    working_coll.distinct = AsyncMock(return_value=["user-1"])
    working_coll.find = MagicMock(
        return_value=AsyncCursor(
            [
                {
                    "_id": "wm-1",
                    "content": "Important fact",
                    "importance_score": 0.9,
                }
            ]
        )
    )
    working_coll.delete_one = AsyncMock()

    db = MagicMock()
    db.__getitem__ = MagicMock(
        side_effect=lambda name: {
            "working_memory": working_coll,
            "semantic_memory": semantic_coll,
        }[name]
    )

    mock_sm = MagicMock()
    mock_sm.add_fact = AsyncMock()
    mock_sm.consolidate = AsyncMock()

    with (
        patch.object(sched_mod.db_client, "db", db),
        patch.object(sched_mod, "SemanticMemory", return_value=mock_sm) as sm_cls,
    ):
        await consolidation_job()

    sm_cls.assert_called_once_with(user_id="user-1", collection=semantic_coll)
    mock_sm.add_fact.assert_awaited_once_with(fact="Important fact", importance=0.9)
    working_coll.delete_one.assert_awaited_once_with({"_id": "wm-1"})
    mock_sm.consolidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidation_continues_on_item_error():
    """A failing item must not abort the job; successful items still promote."""
    working_coll = MagicMock()
    semantic_coll = MagicMock()

    working_coll.distinct = AsyncMock(return_value=["user-1"])
    working_coll.find = MagicMock(
        return_value=AsyncCursor(
            [
                {"_id": "bad", "content": "x", "importance_score": 0.8},
                {"_id": "good", "content": "y", "importance_score": 0.9},
            ]
        )
    )
    working_coll.delete_one = AsyncMock()

    db = MagicMock()
    db.__getitem__ = MagicMock(
        side_effect=lambda name: {
            "working_memory": working_coll,
            "semantic_memory": semantic_coll,
        }[name]
    )

    mock_sm = MagicMock()
    mock_sm.add_fact = AsyncMock(side_effect=[RuntimeError("boom"), None])
    mock_sm.consolidate = AsyncMock()

    with (
        patch.object(sched_mod.db_client, "db", db),
        patch.object(sched_mod, "SemanticMemory", return_value=mock_sm),
    ):
        await consolidation_job()  # must not raise

    assert mock_sm.add_fact.await_count == 2
    # only the successful item is deleted
    working_coll.delete_one.assert_awaited_once_with({"_id": "good"})
    mock_sm.consolidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_consolidation_no_users():
    """No users in working memory must skip SemanticMemory entirely."""
    working_coll = MagicMock()
    semantic_coll = MagicMock()
    working_coll.distinct = AsyncMock(return_value=[])

    db = MagicMock()
    db.__getitem__ = MagicMock(
        side_effect=lambda name: {
            "working_memory": working_coll,
            "semantic_memory": semantic_coll,
        }[name]
    )

    with (
        patch.object(sched_mod.db_client, "db", db),
        patch.object(sched_mod, "SemanticMemory") as sm_cls,
    ):
        await consolidation_job()

    sm_cls.assert_not_called()


# ---------------------------------------------------------------------------
# start / stop idempotent
# ---------------------------------------------------------------------------


def test_start_scheduler_idempotent():
    """start_scheduler must not add/start twice while already running."""
    fake = MagicMock()
    fake.running = False

    with patch.object(sched_mod, "scheduler", fake):
        start_scheduler()
        fake.add_job.assert_called_once()
        fake.start.assert_called_once()

        # second call while "running"
        fake.running = True
        start_scheduler()
        assert fake.add_job.call_count == 1
        assert fake.start.call_count == 1


def test_stop_scheduler_idempotent():
    """stop_scheduler must not shut down twice when already stopped."""
    fake = MagicMock()
    fake.running = True

    with patch.object(sched_mod, "scheduler", fake):
        stop_scheduler()
        fake.shutdown.assert_called_once_with(wait=False)

        fake.running = False
        stop_scheduler()
        assert fake.shutdown.call_count == 1


def test_start_scheduler_registers_stable_job():
    """Consolidation job must use a stable id, replace_existing, max_instances=1, coalesce."""
    fake = MagicMock()
    fake.running = False

    with patch.object(sched_mod, "scheduler", fake):
        start_scheduler()

    kwargs = fake.add_job.call_args.kwargs
    assert kwargs.get("id") == "memory_consolidation"
    assert kwargs.get("replace_existing") is True
    assert kwargs.get("max_instances") == 1
    assert kwargs.get("coalesce") is True


@pytest.mark.asyncio
async def test_consolidation_continues_on_user_error():
    """A failing user must not prevent consolidation for subsequent users."""
    working_coll = MagicMock()
    semantic_coll = MagicMock()

    working_coll.distinct = AsyncMock(return_value=["user-bad", "user-good"])
    working_coll.find = MagicMock(return_value=AsyncCursor([]))

    db = MagicMock()
    db.__getitem__ = MagicMock(
        side_effect=lambda name: {
            "working_memory": working_coll,
            "semantic_memory": semantic_coll,
        }[name]
    )

    bad_sm = MagicMock()
    bad_sm.consolidate = AsyncMock(side_effect=RuntimeError("boom"))
    good_sm = MagicMock()
    good_sm.consolidate = AsyncMock()

    def sm_factory(*, user_id, collection):
        return bad_sm if user_id == "user-bad" else good_sm

    with (
        patch.object(sched_mod.db_client, "db", db),
        patch.object(sched_mod, "SemanticMemory", side_effect=sm_factory),
    ):
        await consolidation_job()  # must not raise

    bad_sm.consolidate.assert_awaited_once()
    good_sm.consolidate.assert_awaited_once()
