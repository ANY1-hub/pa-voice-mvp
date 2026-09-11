"""Reject oversized POST /api/v1/chat/voice before the body is parsed.

REVIEWEXTERN P1-5: FastAPI reads multipart (and JWT deps) only after the
body is on disk. Declared Content-Length over MAX_AUDIO_BYTES is 413 with
no ``receive``. A lying/omitted length is capped while reading.
"""

from __future__ import annotations

import json

from src.services.orchestrator import MAX_AUDIO_BYTES

_VOICE_PATH = "/api/v1/chat/voice"
_DETAIL = f"Audio exceeds limit of {MAX_AUDIO_BYTES // (1024 * 1024)} MB"


class _BodyTooLarge(Exception):
    """Streamed body crossed MAX_AUDIO_BYTES."""


def _header(scope: dict, name: bytes) -> bytes | None:
    for key, value in scope.get("headers") or []:
        if key == name:
            return value
    return None


def _content_length(scope: dict) -> int | None:
    raw = _header(scope, b"content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


async def _send_413(send) -> None:
    payload = json.dumps({"detail": _DETAIL}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class _CappedReceive:
    """Count http.request bytes; raise when they exceed the cap."""

    def __init__(self, receive, cap: int) -> None:
        self._receive = receive
        self._cap = cap
        self._total = 0

    async def __call__(self) -> dict:
        message = await self._receive()
        if message.get("type") == "http.request":
            self._total += len(message.get("body") or b"")
            if self._total > self._cap:
                raise _BodyTooLarge()
        return message


class VoiceUploadLimitMiddleware:
    """ASGI gate for voice uploads only (single uvicorn worker)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        if scope.get("path") != _VOICE_PATH:
            await self.app(scope, receive, send)
            return

        length = _content_length(scope)
        if length is not None and length > MAX_AUDIO_BYTES:
            await _send_413(send)
            return

        try:
            await self.app(scope, _CappedReceive(receive, MAX_AUDIO_BYTES), send)
        except _BodyTooLarge:
            await _send_413(send)
