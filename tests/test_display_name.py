"""First-login preferred name: gate, POST, memory fact."""

import uuid

from tests.conftest import wipe_users


def _register_and_login(client) -> tuple[dict, str]:
    """Bootstrap one user without a display name; return headers and email."""
    wipe_users()
    email = f"name-{uuid.uuid4().hex[:10]}@example.com"
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
    return {"Authorization": f"Bearer {token}"}, email


def test_register_leaves_display_name_empty(client):
    """A new account has no preferred name until the onboarding POST."""
    wipe_users()
    email = f"empty-{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert reg.status_code == 201
    assert reg.json()["display_name"] is None


def test_me_exposes_display_name_null_before_onboarding(client):
    """GET /me stays open and reports display_name=null before onboarding."""
    headers, _email = _register_and_login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"] is None


def test_missing_display_name_blocks_memory_but_allows_me(client):
    """Chat/memory require a display name; /me does not."""
    headers, _email = _register_and_login(client)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    blocked = client.get("/api/v1/memory/working", headers=headers)
    assert blocked.status_code == 403
    assert "display name" in blocked.json()["detail"].lower()


def test_set_display_name_unlocks_ready_routes(client):
    """POST /display-name stores the name and opens chat/memory."""
    headers, _email = _register_and_login(client)
    set_name = client.post(
        "/api/v1/auth/display-name",
        headers=headers,
        json={"display_name": "  Tony  "},
    )
    assert set_name.status_code == 200, set_name.text
    assert set_name.json()["display_name"] == "Tony"

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Tony"

    memory = client.get("/api/v1/memory/working", headers=headers)
    assert memory.status_code == 200


def test_display_name_writes_semantic_fact(client):
    """Setting a preferred name must store a high-importance semantic fact."""
    headers, _email = _register_and_login(client)
    assert (
        client.post(
            "/api/v1/auth/display-name",
            headers=headers,
            json={"display_name": "Pepper"},
        ).status_code
        == 200
    )
    search = client.get(
        "/api/v1/memory/semantic",
        headers=headers,
        params={"query": "Pepper"},
    )
    assert search.status_code == 200
    facts = search.json()["data"]
    assert any("Pepper" in (item.get("content") or "") for item in facts)


def test_display_name_fact_is_not_duplicated(client):
    """Setting the same preferred name twice must leave a single semantic fact."""
    headers, _email = _register_and_login(client)
    payload = {"display_name": "Akosh"}
    assert (
        client.post(
            "/api/v1/auth/display-name", headers=headers, json=payload
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/display-name", headers=headers, json=payload
        ).status_code
        == 200
    )
    search = client.get(
        "/api/v1/memory/semantic",
        headers=headers,
        params={"query": "Akosh"},
    )
    assert search.status_code == 200
    facts = [
        item
        for item in search.json()["data"]
        if "prefers to be addressed as Akosh" in (item.get("content") or "")
    ]
    assert len(facts) == 1


def test_display_name_empty_rejected(client):
    """Whitespace-only names must be rejected."""
    headers, _email = _register_and_login(client)
    response = client.post(
        "/api/v1/auth/display-name",
        headers=headers,
        json={"display_name": "   "},
    )
    assert response.status_code == 422


def test_display_name_too_long_rejected(client):
    """Names longer than 40 characters after trim must be rejected."""
    headers, _email = _register_and_login(client)
    response = client.post(
        "/api/v1/auth/display-name",
        headers=headers,
        json={"display_name": "A" * 41},
    )
    assert response.status_code == 422


def test_display_name_requires_auth(client):
    """Unauthenticated POST /display-name must return 401."""
    response = client.post(
        "/api/v1/auth/display-name",
        json={"display_name": "Tony"},
    )
    assert response.status_code == 401


def test_password_change_required_before_display_name(client):
    """Admin-created users must change password before they can set a name."""
    wipe_users()
    super_email = f"super-{uuid.uuid4().hex[:8]}@example.com"
    super_pw = "SecurePass123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": super_email, "password": super_pw},
    )
    super_token = client.post(
        "/api/v1/auth/login",
        json={"email": super_email, "password": super_pw},
    ).json()["access_token"]
    super_headers = {"Authorization": f"Bearer {super_token}"}
    assert (
        client.post(
            "/api/v1/auth/display-name",
            headers=super_headers,
            json={"display_name": "Super"},
        ).status_code
        == 200
    )

    user_email = f"forced-{uuid.uuid4().hex[:8]}@example.com"
    initial_pw = "InitialPass123!"
    client.post(
        "/api/v1/admin/users",
        headers=super_headers,
        json={"email": user_email, "password": initial_pw},
    )
    user_token = client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": initial_pw},
    ).json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    blocked = client.post(
        "/api/v1/auth/display-name",
        headers=user_headers,
        json={"display_name": "Rhodey"},
    )
    assert blocked.status_code == 403
    assert "password" in blocked.json()["detail"].lower()

    new_token = client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={"current_password": initial_pw, "new_password": "FinalPass1234!"},
    ).json()["access_token"]
    fresh = {"Authorization": f"Bearer {new_token}"}
    set_name = client.post(
        "/api/v1/auth/display-name",
        headers=fresh,
        json={"display_name": "Rhodey"},
    )
    assert set_name.status_code == 200
    assert set_name.json()["display_name"] == "Rhodey"
