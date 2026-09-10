"""REVIEWEXTERN P1-4: GET /health must be readiness that touches Mongo.

Slice-Brief 7: ready (200 + status ok) only when a cheap DB ping succeeds;
if Mongo is down/unreachable, must NOT report ok (prefer 503 + honest body).
Simulate ping failure via monkeypatch — never stop shared NAS Mongo, never
touch jarvis_db.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from pymongo.errors import ConnectionFailure

from src.db.mongodb import db_client


def _assert_no_secrets(body: dict) -> None:
    blob = str(body).lower()
    for leak in ("password", "secret_key", "mongodb_uri", "mongodb+srv", "bearer "):
        assert leak not in blob, f"health body must not leak {leak!r}: {body!r}"


def test_health_ready_when_db_reachable(client):
    """Control twin: with jarvis_test up, /health reports ready (200 + ok)."""
    assert db_client.client is not None, "TestClient lifespan must connect Mongo"
    response = client.get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "ok"
    _assert_no_secrets(body)


def test_health_not_ok_when_mongo_ping_fails(client, monkeypatch):
    """Forced Mongo ping failure must not report ok (prefer 503).

    Motor returns a new ``admin`` handle on every access, so pin one instance
    on the client before patching ``command``.
    """
    mongo = db_client.client
    assert mongo is not None, "TestClient lifespan must connect Mongo"
    admin = mongo.admin
    monkeypatch.setattr(
        admin,
        "command",
        AsyncMock(side_effect=ConnectionFailure("simulated mongo down")),
    )
    monkeypatch.setattr(mongo, "admin", admin, raising=False)

    response = client.get("/health")
    assert (
        response.status_code == 503
    ), f"expected 503 when DB ping fails, got {response.status_code}: {response.text}"
    body = response.json()
    status = str(body.get("status", "")).lower()
    assert status != "ok", f"must not claim ok when DB is down: {body!r}"
    assert status in {
        "error",
        "unavailable",
        "degraded",
        "fail",
        "failed",
    }, f"honest non-ok status expected, got {body!r}"
    _assert_no_secrets(body)


def test_health_not_ok_when_client_missing(client, monkeypatch):
    """No Motor client must not report ok (prefer 503)."""
    monkeypatch.setattr(db_client, "client", None)
    response = client.get("/health")
    assert response.status_code == 503, response.text
    body = response.json()
    status = str(body.get("status", "")).lower()
    assert status != "ok", f"must not claim ok when client is missing: {body!r}"
    assert status in {
        "error",
        "unavailable",
        "degraded",
        "fail",
        "failed",
    }, f"honest non-ok status expected, got {body!r}"
    _assert_no_secrets(body)
