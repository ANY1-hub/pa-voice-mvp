"""REVIEWEXTERN P1-5: reject oversized /chat/voice before the body is read.

Slice-Brief 9: Content-Length over MAX_AUDIO_BYTES must 413 without calling
receive (no disk, no JWT). Unauthenticated oversize is 413, not 401. Small
unsigned voice still fails auth (control twin).

Mutation M1: skip the Content-Length check so this request reaches the inner
app → test_voice_oversize_content_length_is_413_before_body must go red.
"""

from __future__ import annotations

import pytest

from src.api.voice_upload_limit import VoiceUploadLimitMiddleware
from src.main import app
from src.services.orchestrator import MAX_AUDIO_BYTES

_VOICE = "/api/v1/chat/voice"


def _assert_no_secrets(blob: bytes | str) -> None:
    lowered = str(blob).lower()
    for leak in ("secret_key", "mongodb_uri", "mongodb+srv", "hashed_password"):
        assert leak not in lowered, f"413 body must not leak {leak!r}: {blob!r}"


def _response_status(sent: list[dict]) -> int | None:
    for message in sent:
        if message.get("type") == "http.response.start":
            return int(message["status"])
    return None


def _response_body(sent: list[dict]) -> bytes:
    return b"".join(
        message.get("body", b"")
        for message in sent
        if message.get("type") == "http.response.body"
    )


async def _asgi_call(scope: dict, body: bytes = b"") -> tuple[list[dict], list[int]]:
    """Drive the limiter wrapping a dummy app (no FastAPI lifespan / Mongo)."""
    receive_calls: list[int] = []
    sent: list[dict] = []
    inner_hits: list[int] = []

    async def receive() -> dict:
        receive_calls.append(len(body))
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    async def inner(scope, receive, send):
        inner_hits.append(1)
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"inner"})

    middleware = VoiceUploadLimitMiddleware(inner)
    await middleware(scope, receive, send)
    return sent, receive_calls


def _http_scope(path: str, content_length: int | None) -> dict:
    headers = [
        (b"host", b"testserver"),
        (b"content-type", b"multipart/form-data; boundary=----x"),
    ]
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode("ascii")))
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }


def test_voice_limit_middleware_is_wired_on_app():
    """Limiter must sit on the FastAPI stack, not only in unit tests."""
    names = [item.cls.__name__ for item in app.user_middleware]
    assert "VoiceUploadLimitMiddleware" in names


@pytest.mark.asyncio
async def test_voice_oversize_content_length_is_413_before_body():
    """Declared length over the cap, tiny body, no token → 413; receive unused.

    Mutation M1: dropping the Content-Length gate must make this go red
    (inner app would pull the body).
    """
    sent, receive_calls = await _asgi_call(
        _http_scope(_VOICE, MAX_AUDIO_BYTES + 1),
        body=b"x",
    )
    assert (
        _response_status(sent) == 413
    ), f"expected 413 before parse, got {_response_status(sent)} body={_response_body(sent)!r}"
    assert (
        receive_calls == []
    ), f"must not pull the body when Content-Length is over cap, got {receive_calls!r}"
    body = _response_body(sent)
    assert body, "413 must have a body the client can show"
    _assert_no_secrets(body)


@pytest.mark.asyncio
async def test_voice_oversize_content_length_without_token_is_not_401():
    """Oversize unsigned upload is a size reject, not an auth reject."""
    sent, _ = await _asgi_call(_http_scope(_VOICE, MAX_AUDIO_BYTES + 1), body=b"x")
    status = _response_status(sent)
    assert status == 413
    assert status != 401
    assert status != 403


def test_voice_small_upload_without_token_still_requires_auth(client):
    """Control twin: under-cap unsigned /voice is auth-fail, not 413."""
    res = client.post(
        _VOICE,
        files={"audio": ("recording.wav", b"fake-wav-content", "audio/wav")},
    )
    assert res.status_code in {
        401,
        403,
    }, f"small unsigned voice must still require auth, got {res.status_code}: {res.text}"
    assert res.status_code != 413
