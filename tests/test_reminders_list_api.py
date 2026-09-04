"""GET /api/v1/reminders lists only the current user's reminders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.skills.reminders.repository import ReminderRepository
from tests.isolation_users import mongo_collection, run_async, two_ready_users

CONTENT_A = "call the bank"
CONTENT_B = "pick up bread"


def test_list_reminders_requires_auth(client: TestClient):
    """GET /reminders without a JWT must be 401."""
    assert client.get("/api/v1/reminders").status_code == 401


def test_list_reminders_is_isolated_between_two_real_users(client: TestClient):
    """A's GET /reminders must omit B's item; B's list must omit A's."""
    user_a, user_b = two_ready_users(client)
    due = datetime.now(UTC) + timedelta(hours=2)

    async def _seed() -> None:
        async with mongo_collection("reminders") as coll:
            await ReminderRepository(user_id=user_a.user_id, collection=coll).create(
                content=CONTENT_A, due_at=due
            )
            await ReminderRepository(user_id=user_b.user_id, collection=coll).create(
                content=CONTENT_B, due_at=due
            )

    run_async(_seed())

    listed_a = client.get("/api/v1/reminders", headers=user_a.headers)
    listed_b = client.get("/api/v1/reminders", headers=user_b.headers)
    assert listed_a.status_code == 200, listed_a.text
    assert listed_b.status_code == 200, listed_b.text

    contents_a = [item["content"] for item in listed_a.json()["reminders"]]
    contents_b = [item["content"] for item in listed_b.json()["reminders"]]
    assert CONTENT_A in contents_a
    assert CONTENT_B not in contents_a
    assert CONTENT_B in contents_b
    assert CONTENT_A not in contents_b
    assert listed_a.json()["reminders"][0]["status"] == "pending"
