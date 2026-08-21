"""User IANA timezone: persist from the browser, expose on /me, validate."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import pytest

from src.core.timezones import parse_iana_timezone, to_utc, zoneinfo_or_utc
from tests.conftest import wipe_users

_FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _register_and_login(client) -> dict:
    """Bootstrap one user and return auth headers (no display name required)."""
    wipe_users()
    email = f"tz-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    assert (
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        ).status_code
        == 201
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_leaves_timezone_empty(client):
    """A new account has no timezone until the browser posts one."""
    wipe_users()
    email = f"tz-empty-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert reg.status_code == 201
    assert reg.json()["timezone"] is None


def test_me_exposes_timezone_null_before_sync(client):
    """GET /me reports timezone=null until the client sends an IANA zone."""
    headers = _register_and_login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["timezone"] is None


def test_set_timezone_persists_iana_name(client):
    """POST /auth/timezone must store a valid IANA zone and return it on /me."""
    headers = _register_and_login(client)
    res = client.post(
        "/api/v1/auth/timezone",
        headers=headers,
        json={"timezone": "Europe/Berlin"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["timezone"] == "Europe/Berlin"
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["timezone"] == "Europe/Berlin"


def test_set_timezone_rejects_unknown_zone(client):
    """Unknown IANA names must be rejected so due times are never guessed."""
    headers = _register_and_login(client)
    res = client.post(
        "/api/v1/auth/timezone",
        headers=headers,
        json={"timezone": "Not/AZone"},
    )
    assert res.status_code == 422


def test_set_timezone_requires_auth(client):
    """Timezone updates require a JWT."""
    res = client.post(
        "/api/v1/auth/timezone",
        json={"timezone": "Europe/Berlin"},
    )
    assert res.status_code == 401


def test_parse_iana_timezone_rejects_empty_and_junk():
    """Invalid names must not silently become UTC."""
    with pytest.raises(ValueError):
        parse_iana_timezone("")
    with pytest.raises(ValueError):
        parse_iana_timezone("Europe/ Berlin")
    with pytest.raises(ValueError):
        parse_iana_timezone("Not/AZone")
    assert parse_iana_timezone("UTC") == "UTC"
    assert zoneinfo_or_utc(None).key == "UTC"
    assert zoneinfo_or_utc("Not/AZone").key == "UTC"
    naive = datetime(2026, 8, 21, 13, 30)
    assert to_utc(naive).tzinfo is not None


def test_frontend_sends_browser_timezone():
    """Voice UI must POST Intl IANA timezone so spoken clock times are local."""
    auth = (_FRONTEND / "auth.js").read_text(encoding="utf-8")
    app = (_FRONTEND / "app.js").read_text(encoding="utf-8")
    combined = auth + app
    assert "resolvedOptions().timeZone" in combined
    assert "/api/v1/auth/timezone" in combined
