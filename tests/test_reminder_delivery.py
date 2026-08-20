"""Due reminder delivery: claim, list fired, ack, HTTP + TTS."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from src.api.deps import get_llm_adapter, get_tts_adapter
from src.core.config import get_settings
from src.main import app
from src.models.reminder import Reminder
from src.skills.reminders.repository import ReminderRepository, claim_due_reminders
from src.skills.reminders.skill import fire_speech
from tests.conftest import wipe_users


@pytest.mark.asyncio
async def test_claim_due_marks_fired_at_once():
    """A due pending reminder must be claimed exactly once."""
    now = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
    due = now - timedelta(minutes=1)
    reminder = Reminder(user_id="u1", content="drink water", due_at=due, language="en")
    stored = reminder.model_dump()
    stored["_id"] = reminder.id
    stored["due_at"] = due
    stored["fired_at"] = now

    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(side_effect=[stored, None])

    claimed = await claim_due_reminders(collection, now, user_id="u1")
    assert len(claimed) == 1
    assert claimed[0].content == "drink water"
    assert claimed[0].fired_at == now
    assert collection.find_one_and_update.await_count == 2
    filt = collection.find_one_and_update.await_args_list[0].args[0]
    assert filt["status"] == "pending"
    assert filt["due_at"]["$lte"] == now
    assert filt["user_id"] == "u1"


@pytest.mark.asyncio
async def test_claim_due_skips_future_and_already_fired():
    """Future or already-fired reminders must not match the claim filter."""
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=None)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    assert await claim_due_reminders(collection, now) == []
    filt = collection.find_one_and_update.await_args.args[0]
    assert "$or" in filt


@pytest.mark.asyncio
async def test_acknowledge_sets_done():
    """Ack must set status=done for the owning user."""
    now = datetime.now(UTC)
    doc = {
        "id": "rid",
        "user_id": "u1",
        "content": "x",
        "status": "done",
        "due_at": now,
        "fired_at": now,
        "created_at": now,
        "last_accessed": now,
    }
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=doc)
    repo = ReminderRepository(user_id="u1", collection=collection)
    updated = await repo.acknowledge("rid")
    assert updated is not None
    assert updated.status == "done"
    filt = collection.find_one_and_update.await_args.args[0]
    assert filt["id"] == "rid"
    assert filt["user_id"] == "u1"


def test_fire_speech_uses_language():
    """Due speech must follow the reminder language."""
    assert "Reminder" in fire_speech("water", "en")
    assert "Erinnerung" in fire_speech("Wasser", "de")
    assert "Emlékeztető" in fire_speech("víz", "hu")


@pytest.fixture
def delivery_client():
    """HTTP client with stubbed LLM/TTS."""
    llm = AsyncMock()
    llm.generate_response.return_value = "{}"
    tts = AsyncMock()
    tts.synthesize.return_value = b"wav-bytes"
    app.dependency_overrides[get_llm_adapter] = lambda: llm
    app.dependency_overrides[get_tts_adapter] = lambda: tts
    with TestClient(app) as client:
        yield client, tts
    app.dependency_overrides.clear()


@pytest.fixture
def delivery_auth(delivery_client) -> tuple[dict, str]:
    client, _tts = delivery_client
    wipe_users()
    email = "due@example.com"
    password = "SecurePass123!"
    assert (
        client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        ).status_code
        == 201
    )
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    return headers, user_id


def test_due_endpoint_claims_and_returns_audio(delivery_client, delivery_auth):
    """GET /reminders/due must claim a past-due reminder and include TTS."""
    client, tts = delivery_client
    headers, user_id = delivery_auth
    create = client.post(
        "/api/v1/chat/text",
        headers=headers,
        json={"text": "remind me in 2 minutes to drink water", "language": "en"},
    )
    assert create.status_code == 200, create.text

    settings = get_settings()
    mongo = MongoClient(settings.mongodb_uri)
    try:
        mongo[settings.mongodb_db_name]["reminders"].update_many(
            {"user_id": user_id},
            {"$set": {"due_at": datetime(2020, 1, 1, tzinfo=UTC)}},
        )
    finally:
        mongo.close()

    res = client.get("/api/v1/reminders/due", headers=headers)
    assert res.status_code == 200, res.text
    items = res.json()["reminders"]
    assert len(items) == 1
    assert "water" in items[0]["content"].lower()
    assert items[0]["audio_base64"]
    UUID(items[0]["id"])
    tts.synthesize.assert_awaited()

    ack = client.post(f"/api/v1/reminders/{items[0]['id']}/ack", headers=headers)
    assert ack.status_code == 200
    again = client.get("/api/v1/reminders/due", headers=headers)
    assert again.json()["reminders"] == []


def test_ack_other_users_reminder_is_404(delivery_client, delivery_auth):
    """Ack must not succeed for another user's reminder id."""
    client, _tts = delivery_client
    headers, _uid = delivery_auth
    res = client.post(
        "/api/v1/reminders/00000000-0000-0000-0000-000000000000/ack",
        headers=headers,
    )
    assert res.status_code == 404


def test_due_requires_auth(delivery_client):
    """GET /reminders/due without JWT must be 401."""
    client, _tts = delivery_client
    assert client.get("/api/v1/reminders/due").status_code == 401
