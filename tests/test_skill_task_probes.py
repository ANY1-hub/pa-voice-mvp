"""Black-box skill probes: chat turn must persist the expected Mongo side effect."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from src.api.deps import get_llm_adapter, get_tts_adapter
from src.core.config import get_settings
from src.main import app
from tests.conftest import wipe_users


@pytest.fixture
def probe_client():
    """HTTP client with real skills/Mongo; LLM/TTS stubbed so CI stays offline."""
    llm = AsyncMock()
    llm.generate_response.return_value = "llm-fallback-should-not-run"
    app.dependency_overrides[get_llm_adapter] = lambda: llm
    app.dependency_overrides[get_tts_adapter] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def probe_auth(probe_client: TestClient) -> tuple[dict, str]:
    """Bootstrap one user; return (headers, user_id)."""
    wipe_users()
    email = "probe@example.com"
    password = "SecurePass123!"
    assert (
        probe_client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        ).status_code
        == 201
    )
    token = probe_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = probe_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    return headers, user_id


def _mongo():
    settings = get_settings()
    return MongoClient(settings.mongodb_uri), settings.mongodb_db_name


def test_probe_notes_create_persists(probe_client: TestClient, probe_auth: tuple):
    """A notes create turn must write a notes document for that user."""
    headers, user_id = probe_auth
    res = probe_client.post(
        "/api/v1/chat/text",
        headers=headers,
        json={"text": "note: buy oat milk", "language": "en"},
    )
    assert res.status_code == 200, res.text
    assert "oat milk" in res.json()["response"].lower()

    client, db_name = _mongo()
    try:
        doc = client[db_name]["notes"].find_one({"user_id": user_id})
        assert doc is not None
        assert "oat milk" in doc["content"].lower()
    finally:
        client.close()


def test_probe_reminders_create_persists(probe_client: TestClient, probe_auth: tuple):
    """A reminder create turn must write a reminders document for that user."""
    headers, user_id = probe_auth
    res = probe_client.post(
        "/api/v1/chat/text",
        headers=headers,
        json={"text": "remind me tomorrow to call the dentist", "language": "en"},
    )
    assert res.status_code == 200, res.text

    client, db_name = _mongo()
    try:
        doc = client[db_name]["reminders"].find_one({"user_id": user_id})
        assert doc is not None
        assert "dentist" in doc["content"].lower()
        assert doc.get("status") == "pending"
    finally:
        client.close()


def test_probe_recall_reads_semantic_fact(probe_client: TestClient, probe_auth: tuple):
    """Active recall must surface a fact previously stored in Semantic Memory."""
    headers, _user_id = probe_auth
    seeded = probe_client.post(
        "/api/v1/memory/semantic",
        headers=headers,
        json={
            "content": "User likes espresso",
            "importance_score": 0.8,
            "entities_involved": ["espresso"],
        },
    )
    assert seeded.status_code == 200, seeded.text

    res = probe_client.post(
        "/api/v1/chat/text",
        headers=headers,
        json={"text": "what do you know about me", "language": "en"},
    )
    assert res.status_code == 200, res.text
    assert "espresso" in res.json()["response"].lower()


def test_probe_web_search_returns_backend_hit(
    probe_client: TestClient, probe_auth: tuple
):
    """Web search must include a backend result in the spoken reply."""
    headers, _user_id = probe_auth
    fake = [
        {
            "title": "Probe Result",
            "href": "https://example.com/probe",
            "body": "A deterministic snippet.",
        }
    ]
    with patch(
        "src.skills.web_search.client.DuckDuckGoClient.search",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        res = probe_client.post(
            "/api/v1/chat/text",
            headers=headers,
            json={"text": "search for the capital of France", "language": "en"},
        )
    assert res.status_code == 200, res.text
    body = res.json()["response"]
    assert "Probe Result" in body or "example.com/probe" in body
