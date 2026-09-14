"""REVIEWEXTERN P2-4: CORS must not be a wildcard, including on login.

Slice-Brief 15: only the Voice UI origins (:5500) may preflight the API.
Mutation M1: allow_origins=['*'] again → evil Origin gets ACAO * → this goes red.
Control: http://127.0.0.1:5500 still allowed; TestClient POST /login still works.
"""

from __future__ import annotations

_LOGIN = "/api/v1/auth/login"
_EVIL = "https://evil.example"
_UI = "http://127.0.0.1:5500"


def _preflight(client, origin: str):
    return client.options(
        _LOGIN,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


def test_cors_preflight_rejects_foreign_origin(client):
    """Evil Origin must not receive Access-Control-Allow-Origin * or itself.

    Mutation M1: restoring allow_origins=['*'] must make this go red.
    """
    res = _preflight(client, _EVIL)
    acao = res.headers.get("access-control-allow-origin")
    assert acao != "*", f"wildcard CORS still on: {res.headers!r}"
    assert acao != _EVIL, f"foreign origin echoed: {res.headers!r}"


def test_cors_preflight_allows_dev_ui_origin(client):
    """Control twin: the :5500 Voice UI origin is allowed."""
    res = _preflight(client, _UI)
    assert res.headers.get("access-control-allow-origin") == _UI, res.headers
