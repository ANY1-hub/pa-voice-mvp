"""REVIEWEXTERN P1-3: POST /login must bound failed attempts.

Slice-Brief 8: after N failures in a window for the same client IP + email,
the next attempt returns 429 + Retry-After. Unknown emails use the same
shape (no existence leak). Success clears the key. 401 body under the cap
stays ``Incorrect email or password``. Logs must not include the password.

Mutation M1: removing the limiter so a burst stays 401 must make the 429
tests go red. Control twin: under-cap correct password still 200.
"""

from __future__ import annotations

import uuid

import pytest

from src.core.config import get_settings
from tests.conftest import wipe_users

_WRONG = "WrongPassword99!"
_RIGHT = "SecurePass123!"
_TEST_MAX = 3
_TEST_WINDOW = 60


def _assert_no_secrets(blob: str) -> None:
    lowered = blob.lower()
    for leak in ("secret_key", "mongodb_uri", "mongodb+srv", "hashed_password"):
        assert leak not in lowered, f"must not leak {leak!r}: {blob!r}"
    assert _WRONG.lower() not in lowered
    assert _RIGHT.lower() not in lowered


@pytest.fixture(autouse=True)
def _tight_login_limits(monkeypatch):
    """Keep bursts short; reset the in-process window between tests."""
    monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", str(_TEST_MAX))
    monkeypatch.setenv("LOGIN_WINDOW_SECONDS", str(_TEST_WINDOW))
    get_settings.cache_clear()
    from src.auth.login_limiter import login_limiter

    login_limiter.reset()
    yield
    login_limiter.reset()
    get_settings.cache_clear()


def _register(client, email: str, password: str = _RIGHT) -> None:
    wipe_users()
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert res.status_code == 201, res.text


def _login(client, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def _assert_rate_limited(response) -> None:
    assert (
        response.status_code == 429
    ), f"expected 429 after burst, got {response.status_code}: {response.text}"
    retry = response.headers.get("retry-after")
    assert retry is not None, f"missing Retry-After: {response.headers!r}"
    assert (
        retry.isdigit() and int(retry) >= 1
    ), f"Retry-After must be seconds: {retry!r}"
    body = response.json()
    detail = str(body.get("detail", ""))
    assert detail, f"429 must have a detail the UI can show: {body!r}"
    _assert_no_secrets(response.text)
    _assert_no_secrets(detail)


def test_login_burst_wrong_password_returns_429(client):
    """N+1 wrong password on a real account must 429 with Retry-After.

    Mutation M1: dropping the limiter so this burst stays 401 must go red.
    """
    email = f"limit-{uuid.uuid4().hex[:10]}@example.com"
    _register(client, email)
    for i in range(_TEST_MAX):
        res = _login(client, email, _WRONG)
        assert (
            res.status_code == 401
        ), f"failure {i + 1} under cap must stay 401, got {res.status_code}: {res.text}"
        assert res.json()["detail"] == "Incorrect email or password"
    _assert_rate_limited(_login(client, email, _WRONG))


def test_login_burst_unknown_email_returns_429_same_shape(client):
    """Unknown email must hit the same 429 — not a free unlimited path."""
    email = f"nobody-{uuid.uuid4().hex[:10]}@example.com"
    for i in range(_TEST_MAX):
        res = _login(client, email, _WRONG)
        assert (
            res.status_code == 401
        ), f"unknown failure {i + 1} under cap must stay 401, got {res.status_code}"
        assert res.json()["detail"] == "Incorrect email or password"
    _assert_rate_limited(_login(client, email, _WRONG))


def test_login_succeeds_under_cap_after_failures(client):
    """Control twin: fewer than N failures, then the real password still 200."""
    email = f"ok-{uuid.uuid4().hex[:10]}@example.com"
    _register(client, email)
    for _ in range(_TEST_MAX - 1):
        assert _login(client, email, _WRONG).status_code == 401
    res = _login(client, email, _RIGHT)
    assert res.status_code == 200, res.text
    assert "access_token" in res.json()


def test_login_success_clears_failure_window(client):
    """A successful login resets the key so later failures start from zero."""
    email = f"reset-{uuid.uuid4().hex[:10]}@example.com"
    _register(client, email)
    for _ in range(_TEST_MAX - 1):
        assert _login(client, email, _WRONG).status_code == 401
    assert _login(client, email, _RIGHT).status_code == 200
    for i in range(_TEST_MAX):
        res = _login(client, email, _WRONG)
        assert (
            res.status_code == 401
        ), f"after reset, failure {i + 1} must be 401, got {res.status_code}: {res.text}"
    _assert_rate_limited(_login(client, email, _WRONG))


def test_login_failure_log_does_not_include_password(client, caplog):
    """Failed login (and 429) logs must not contain the password."""
    email = f"log-{uuid.uuid4().hex[:10]}@example.com"
    _register(client, email)
    with caplog.at_level("WARNING"):
        for _ in range(_TEST_MAX):
            _login(client, email, _WRONG)
        _login(client, email, _WRONG)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert _WRONG not in joined
    _assert_no_secrets(joined)
