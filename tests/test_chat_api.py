"""API tests for /api/v1/chat/text and /api/v1/chat/voice."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_orchestrator
from src.main import app
from src.services.orchestrator import ChatResult


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    orch.process.return_value = ChatResult(
        transcript="User said this",
        response="Jarvis reply",
        audio_base64="ZmFrZS1hdWRpbw==",
    )
    return orch


@pytest.fixture
def client_with_mock_orch(mock_orchestrator):
    """TestClient with orchestrator dependency overridden."""
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /chat/text
# ---------------------------------------------------------------------------


def test_chat_text_happy_path(client_with_mock_orch, auth_headers, mock_orchestrator):
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": "Hello Jarvis"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["transcript"] == "User said this"
    assert data["response"] == "Jarvis reply"
    assert data["audio_base64"] == "ZmFrZS1hdWRpbw=="

    mock_orchestrator.process.assert_awaited_once()
    call_kwargs = mock_orchestrator.process.await_args.kwargs
    assert call_kwargs["text"] == "Hello Jarvis"
    assert call_kwargs.get("audio_bytes") is None


def test_chat_text_empty_body(client_with_mock_orch, auth_headers):
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": ""},
    )
    assert res.status_code == 422


def test_chat_text_orchestrator_value_error(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    mock_orchestrator.process.side_effect = ValueError("bad input")
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": "trigger error"},
    )
    assert res.status_code == 400
    assert "bad input" in res.json()["detail"]


# ---------------------------------------------------------------------------
# /chat/voice
# ---------------------------------------------------------------------------


def test_chat_voice_happy_path(client_with_mock_orch, auth_headers, mock_orchestrator):
    files = {"audio": ("recording.wav", b"fake-wav-content", "audio/wav")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
        data={"language": "de"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["transcript"] == "User said this"
    assert data["response"] == "Jarvis reply"
    assert data["audio_base64"] is not None

    mock_orchestrator.process.assert_awaited_once()
    call_kwargs = mock_orchestrator.process.await_args.kwargs
    assert call_kwargs["audio_bytes"] == b"fake-wav-content"
    assert call_kwargs["language"] == "de"
    assert call_kwargs.get("text") is None


def test_chat_voice_empty_audio(client_with_mock_orch, auth_headers):
    files = {"audio": ("empty.wav", b"", "audio/wav")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
    )
    assert res.status_code == 400
    assert "Empty audio" in res.json()["detail"]


def test_chat_voice_unsupported_content_type(client_with_mock_orch, auth_headers):
    files = {"audio": ("file.txt", b"not-audio", "text/plain")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
    )
    assert res.status_code == 415
