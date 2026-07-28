"""API tests for /api/v1/chat/text and /api/v1/chat/voice.

Orchestrator is dependency-overridden so these tests focus on HTTP mapping:
status codes, request validation, and payload wiring — not LLM/STT internals.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_orchestrator
from src.main import app
from src.services.orchestrator import MAX_AUDIO_BYTES, ChatResult


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
    """200 + body fields; process() called with text only."""
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
    """Pydantic rejects empty text → 422 Unprocessable Entity."""
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": ""},
    )
    assert res.status_code == 422


def test_chat_text_orchestrator_value_error(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    """ValueError from orchestrator is mapped to HTTP 400."""
    mock_orchestrator.process.side_effect = ValueError("bad input")
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": "trigger error"},
    )
    assert res.status_code == 400
    assert "bad input" in res.json()["detail"]


def test_chat_text_orchestrator_unexpected_error(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    """Unexpected errors become HTTP 500 (no internal traceback leaked)."""
    mock_orchestrator.process.side_effect = RuntimeError("boom")
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": "trigger 500"},
    )
    assert res.status_code == 500
    assert "Chat failed" in res.json()["detail"]


# ---------------------------------------------------------------------------
# /chat/voice
# ---------------------------------------------------------------------------


def test_chat_voice_happy_path(client_with_mock_orch, auth_headers, mock_orchestrator):
    """200; audio bytes + language form field forwarded to process()."""
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
    """Zero-length upload is rejected before orchestrator runs."""
    files = {"audio": ("empty.wav", b"", "audio/wav")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
    )
    assert res.status_code == 400
    assert "Empty audio" in res.json()["detail"]


def test_chat_voice_unsupported_content_type(client_with_mock_orch, auth_headers):
    """Non-audio Content-Type → 415 Unsupported Media Type."""
    files = {"audio": ("file.txt", b"not-audio", "text/plain")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
    )
    assert res.status_code == 415


def test_chat_voice_too_large(client_with_mock_orch, auth_headers):
    """Payload above MAX_AUDIO_BYTES → 413 Request Entity Too Large."""
    huge = b"x" * (MAX_AUDIO_BYTES + 1)
    files = {"audio": ("big.wav", huge, "audio/wav")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
    )
    assert res.status_code == 413
    assert "exceeds limit" in res.json()["detail"]


def test_chat_voice_orchestrator_unexpected_error(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    """Unexpected orchestrator errors on voice route → HTTP 500."""
    mock_orchestrator.process.side_effect = RuntimeError("stt exploded")
    files = {"audio": ("recording.wav", b"fake-wav-content", "audio/wav")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
    )
    assert res.status_code == 500
    assert "Voice chat failed" in res.json()["detail"]
