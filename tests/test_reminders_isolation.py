"""Two-user tenant isolation for reminders (chat list/delete + due/ack HTTP)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_llm_adapter, get_stt_adapter, get_tts_adapter
from src.main import app
from src.skills.reminders.repository import ReminderRepository
from tests.isolation_users import mongo_collection, run_async, two_ready_users


def _quiet_tts() -> None:
    app.dependency_overrides[get_tts_adapter] = lambda: None


def _restore_tts() -> None:
    app.dependency_overrides.pop(get_tts_adapter, None)


@pytest.fixture
def reminders_chat_client(client: TestClient):
    """Real orchestrator; stub only STT/TTS/LLM so text reminders do not load voice models."""
    app.dependency_overrides[get_stt_adapter] = lambda: MagicMock()
    app.dependency_overrides[get_tts_adapter] = lambda: None
    app.dependency_overrides[get_llm_adapter] = lambda: None
    yield client
    for dep in (get_stt_adapter, get_tts_adapter, get_llm_adapter):
        app.dependency_overrides.pop(dep, None)


def _due_contents(body: dict) -> list[str]:
    return [item["content"] for item in body["reminders"]]


def _seed_due_pair(user_a_id: str, user_b_id: str, secret_a: str, secret_b: str):
    due_at = datetime.now(UTC) - timedelta(minutes=5)

    async def _go():
        async with mongo_collection("reminders") as coll:
            repo_a = ReminderRepository(user_id=user_a_id, collection=coll)
            repo_b = ReminderRepository(user_id=user_b_id, collection=coll)
            a_item = await repo_a.create(content=secret_a, due_at=due_at, language="en")
            b_item = await repo_b.create(content=secret_b, due_at=due_at, language="en")
            return a_item.id, b_item.id

    return run_async(_go())


def test_due_list_does_not_include_other_user_reminder(client: TestClient):
    """B GET /reminders/due must omit A's due reminder; A GET /due must include A's, not B's."""
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-REM-A-{token}"
    secret_b = f"BRAVO-SECRET-REM-B-{token}"
    _seed_due_pair(user_a.user_id, user_b.user_id, secret_a, secret_b)

    _quiet_tts()
    try:
        listed_b = client.get("/api/v1/reminders/due", headers=user_b.headers)
        assert listed_b.status_code == 200, listed_b.text
        contents_b = _due_contents(listed_b.json())
        assert secret_b in contents_b
        assert secret_a not in contents_b

        listed_a = client.get("/api/v1/reminders/due", headers=user_a.headers)
        assert listed_a.status_code == 200, listed_a.text
        contents_a = _due_contents(listed_a.json())
        assert secret_a in contents_a
        assert secret_b not in contents_a
    finally:
        _restore_tts()


def test_ack_other_user_and_unknown_id_are_both_404(client: TestClient):
    """B ack of A's id is 404; unknown UUID is also 404; A's reminder stays pending until A acks."""
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-ACK-A-{token}"
    secret_b = f"BRAVO-SECRET-ACK-B-{token}"
    a_id, _b_id = _seed_due_pair(user_a.user_id, user_b.user_id, secret_a, secret_b)
    unknown_id = str(uuid.uuid4())
    assert unknown_id != a_id

    _quiet_tts()
    try:
        fired = client.get("/api/v1/reminders/due", headers=user_a.headers)
        assert fired.status_code == 200, fired.text
        assert secret_a in _due_contents(fired.json())

        other = client.post(
            f"/api/v1/reminders/{a_id}/ack",
            headers=user_b.headers,
        )
        assert other.status_code == 404, other.text

        unknown = client.post(
            f"/api/v1/reminders/{unknown_id}/ack",
            headers=user_b.headers,
        )
        assert unknown.status_code == 404, unknown.text

        still_pending = client.get("/api/v1/reminders/due", headers=user_a.headers)
        assert still_pending.status_code == 200, still_pending.text
        assert secret_a in _due_contents(still_pending.json())

        own = client.post(
            f"/api/v1/reminders/{a_id}/ack",
            headers=user_a.headers,
        )
        assert own.status_code == 200, own.text
        assert own.json()["id"] == a_id

        after = client.get("/api/v1/reminders/due", headers=user_a.headers)
        assert after.status_code == 200, after.text
        assert secret_a not in _due_contents(after.json())
    finally:
        _restore_tts()


def test_cancel_other_user_returns_none_owner_can_cancel(client: TestClient):
    """ReminderRepository.cancel as B on A's id returns None; A can cancel their own reminder."""
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-CANCEL-A-{token}"
    due_at = datetime.now(UTC) + timedelta(hours=1)

    async def _create() -> str:
        async with mongo_collection("reminders") as coll:
            repo_a = ReminderRepository(user_id=user_a.user_id, collection=coll)
            item = await repo_a.create(content=secret_a, due_at=due_at, language="en")
            return item.id

    reminder_id = run_async(_create())

    async def _cancel_as(user_id: str) -> str | None:
        async with mongo_collection("reminders") as coll:
            repo = ReminderRepository(user_id=user_id, collection=coll)
            updated = await repo.cancel(reminder_id)
            return None if updated is None else updated.status

    assert run_async(_cancel_as(user_b.user_id)) is None
    assert run_async(_cancel_as(user_a.user_id)) == "cancelled"
    assert run_async(_cancel_as(user_a.user_id)) is None


def test_reminder_repository_list_does_not_return_other_user_documents(
    client: TestClient,
):
    """ReminderRepository.list/search bound to B's real user_id must omit A's documents."""
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-LIST-A-{token}"
    secret_b = f"BRAVO-SECRET-LIST-B-{token}"
    due_at = datetime.now(UTC) + timedelta(hours=2)

    async def _seed_and_list() -> tuple[list[str], list[str], list[str]]:
        async with mongo_collection("reminders") as coll:
            repo_a = ReminderRepository(user_id=user_a.user_id, collection=coll)
            repo_b = ReminderRepository(user_id=user_b.user_id, collection=coll)
            await repo_a.create(content=secret_a, due_at=due_at, language="en")
            await repo_b.create(content=secret_b, due_at=due_at, language="en")
            listed_b = await repo_b.list_reminders(limit=50)
            listed_a = await repo_a.list_reminders(limit=50)
            search_b = await repo_b.search_by_content(secret_a, limit=10)
            return (
                [r.content for r in listed_b],
                [r.content for r in listed_a],
                [r.content for r in search_b],
            )

    contents_b, contents_a, search_b = run_async(_seed_and_list())
    assert secret_b in contents_b
    assert secret_a not in contents_b
    assert secret_a in contents_a
    assert secret_b not in contents_a
    assert secret_a not in search_b
    assert search_b == []


def test_chat_reminder_list_is_isolated_between_two_real_users(
    reminders_chat_client: TestClient,
):
    """B's chat list contains B's secret not A's; A's list contains A's not B's (control twin)."""
    client = reminders_chat_client
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-CHAT-LIST-A-{token}"
    secret_b = f"BRAVO-SECRET-CHAT-LIST-B-{token}"

    created_a = client.post(
        "/api/v1/chat/text",
        headers=user_a.headers,
        json={"text": f"remind me tomorrow to {secret_a}", "language": "en"},
    )
    created_b = client.post(
        "/api/v1/chat/text",
        headers=user_b.headers,
        json={"text": f"remind me tomorrow to {secret_b}", "language": "en"},
    )
    assert created_a.status_code == 200, created_a.text
    assert created_b.status_code == 200, created_b.text
    assert secret_a in created_a.json()["response"]
    assert secret_b in created_b.json()["response"]

    listed_b = client.post(
        "/api/v1/chat/text",
        headers=user_b.headers,
        json={"text": "show my reminders", "language": "en"},
    )
    assert listed_b.status_code == 200, listed_b.text
    response_b = listed_b.json()["response"]
    assert secret_b in response_b
    assert secret_a not in response_b

    listed_a = client.post(
        "/api/v1/chat/text",
        headers=user_a.headers,
        json={"text": "show my reminders", "language": "en"},
    )
    assert listed_a.status_code == 200, listed_a.text
    response_a = listed_a.json()["response"]
    assert secret_a in response_a
    assert secret_b not in response_a


def _chat_list(client: TestClient, headers: dict) -> str:
    listed = client.post(
        "/api/v1/chat/text",
        headers=headers,
        json={"text": "show my reminders", "language": "en"},
    )
    assert listed.status_code == 200, listed.text
    return listed.json()["response"]


def test_chat_delete_other_user_and_unknown_target_do_not_cancel(
    reminders_chat_client: TestClient,
):
    """After B deletes A's content and an unknown id, both lists still hold their own rows; A can then delete own."""
    client = reminders_chat_client
    user_a, user_b = two_ready_users(client)
    content_a = "water the balcony tomatoes"
    content_b = "pick up dry cleaning downtown"
    unknown_id = str(uuid.uuid4())

    for user, content in ((user_a, content_a), (user_b, content_b)):
        created = client.post(
            "/api/v1/chat/text",
            headers=user.headers,
            json={"text": f"remind me tomorrow to {content}", "language": "en"},
        )
        assert created.status_code == 200, created.text
        assert content in created.json()["response"]

    other = client.post(
        "/api/v1/chat/text",
        headers=user_b.headers,
        json={"text": f"delete the reminder {content_a}", "language": "en"},
    )
    assert other.status_code == 200, other.text
    assert "removed" not in other.json()["response"].lower()

    unknown = client.post(
        "/api/v1/chat/text",
        headers=user_b.headers,
        json={"text": f"delete the reminder {unknown_id}", "language": "en"},
    )
    assert unknown.status_code == 200, unknown.text
    assert "removed" not in unknown.json()["response"].lower()

    listed_a = _chat_list(client, user_a.headers)
    listed_b = _chat_list(client, user_b.headers)
    assert content_a in listed_a
    assert content_b not in listed_a
    assert content_b in listed_b
    assert content_a not in listed_b

    own = client.post(
        "/api/v1/chat/text",
        headers=user_a.headers,
        json={"text": f"delete the reminder {content_a}", "language": "en"},
    )
    assert own.status_code == 200, own.text

    after_a = _chat_list(client, user_a.headers)
    after_b = _chat_list(client, user_b.headers)
    assert content_a not in after_a
    assert content_b in after_b
