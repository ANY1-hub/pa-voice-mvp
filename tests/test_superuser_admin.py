"""Tests for SuperUser bootstrap and admin endpoints (Phase 5).

Slice-Brief 6 / REVIEWEXTERN P1-1: non-superuser admin 403s must come
from ``get_current_superuser`` (detail mentions Superuser) after full
onboarding — not from ready-user password/display-name gates.
"""

import uuid

from tests.conftest import set_test_display_name, wipe_users


def _make_superuser_headers(client) -> dict:
    """Bootstrap the first user (SuperUser) and return auth headers."""
    wipe_users()
    email = f"super-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["is_superuser"] is True
    assert reg.json()["must_change_password"] is False

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    set_test_display_name(client, headers)
    return headers


def _make_normal_headers(client, super_headers: dict) -> dict:
    """Create a fully onboarded non-super user and return their auth headers.

    Public register is closed after the first user, so the second account
    must be created by a SuperUser. Admin-created users start with
    ``must_change_password=True`` and no display_name — complete both
    before returning so admin 403s hit ``get_current_superuser`` (detail
    mentions Superuser), not the ready-user onboarding gates.
    """
    email = f"normal-{uuid.uuid4().hex[:10]}@example.com"
    initial_password = "SecurePass123!"
    new_password = "NormalPass1234!"
    create = client.post(
        "/api/v1/admin/users",
        headers=super_headers,
        json={"email": email, "password": initial_password, "is_superuser": False},
    )
    assert create.status_code == 201, create.text
    assert create.json()["is_superuser"] is False
    assert create.json()["must_change_password"] is True

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": initial_password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": initial_password, "new_password": new_password},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False
    headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}

    set_test_display_name(client, headers, name="NormalUser")
    return headers


def _assert_superuser_forbidden(response) -> None:
    """403 from the SuperUser gate (not password/display-name onboarding)."""
    assert response.status_code == 403, response.text
    detail = str(response.json().get("detail", "")).lower()
    assert "superuser" in detail, (
        f"expected SuperUser gate detail, got {response.json()!r} "
        "(onboarding 403s prove the wrong Depends path)"
    )


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_first_register_becomes_superuser(client):
    """When the users collection is empty, the first registered user is SuperUser."""
    wipe_users()
    email = f"first-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_superuser"] is True
    assert data["is_active"] is True
    assert data["must_change_password"] is False
    assert "hashed_password" not in data


def test_register_success(client):
    """Successful registration returns 201 with email and id, never the password hash."""
    wipe_users()
    email = f"reg-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email.lower()
    assert "id" in data
    assert "hashed_password" not in data
    assert data["must_change_password"] is False


def test_second_register_is_forbidden(client):
    """Public registration must be rejected once at least one user exists."""
    wipe_users()
    client.post(
        "/api/v1/auth/register",
        json={
            "email": f"first-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
        },
    )
    email = f"second-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert response.status_code == 403
    assert "closed" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# SuperUser guard
# ---------------------------------------------------------------------------


def test_admin_list_users_requires_superuser(client):
    """Ready non-superuser gets 403 with SuperUser detail on admin list.

    Mutation M1: replacing ``if not current_user.is_superuser`` with
    ``if False`` in ``get_current_superuser`` must make this go red
    (would return 200). Must not be satisfiable by onboarding 403s.
    """
    super_headers = _make_superuser_headers(client)
    normal = _make_normal_headers(client, super_headers)
    response = client.get("/api/v1/admin/users", headers=normal)
    _assert_superuser_forbidden(response)


def test_admin_create_requires_superuser(client):
    """Ready non-superuser gets 403 with SuperUser detail on admin create."""
    super_headers = _make_superuser_headers(client)
    normal = _make_normal_headers(client, super_headers)
    response = client.post(
        "/api/v1/admin/users",
        headers=normal,
        json={
            "email": f"blocked-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
            "is_superuser": False,
        },
    )
    _assert_superuser_forbidden(response)


def test_admin_list_users_without_token(client):
    """Control twin: missing token must return 401 (not 403 SuperUser)."""
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


def test_admin_list_users_ok(client):
    """Control twin: SuperUser can list all users (200)."""
    headers = _make_superuser_headers(client)
    _make_normal_headers(client, headers)
    response = client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    for u in data:
        assert "id" in u
        assert "email" in u
        assert "is_superuser" in u
        assert "must_change_password" in u
        assert "hashed_password" not in u


def test_admin_create_user_ok(client):
    """SuperUser can create a user; admin-created accounts must force password change."""
    headers = _make_superuser_headers(client)
    email = f"admin-create-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={"email": email, "password": "SecurePass123!", "is_superuser": False},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email.lower()
    assert data["is_superuser"] is False
    assert data["is_active"] is True
    assert data["must_change_password"] is True


def test_admin_create_user_as_superuser(client):
    """SuperUser can create another SuperUser (still forced to change password)."""
    headers = _make_superuser_headers(client)
    email = f"admin-super-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={"email": email, "password": "SecurePass123!", "is_superuser": True},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_superuser"] is True
    assert data["must_change_password"] is True


def test_admin_create_duplicate_email(client):
    """Admin create with existing email must return 409."""
    headers = _make_superuser_headers(client)
    email = f"dup-admin-{uuid.uuid4().hex[:8]}@example.com"
    payload = {"email": email, "password": "SecurePass123!"}
    assert (
        client.post("/api/v1/admin/users", headers=headers, json=payload).status_code
        == 201
    )
    response = client.post("/api/v1/admin/users", headers=headers, json=payload)
    assert response.status_code == 409


def test_admin_patch_user_ok(client):
    """SuperUser can toggle is_active and is_superuser."""
    headers = _make_superuser_headers(client)
    email = f"patch-{uuid.uuid4().hex[:8]}@example.com"
    create = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={"email": email, "password": "SecurePass123!"},
    )
    assert create.status_code == 201
    user_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"is_active": False, "is_superuser": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False
    assert data["is_superuser"] is True


def test_admin_cannot_demote_last_superuser(client):
    """Demoting or deactivating the last active SuperUser must be rejected."""
    headers = _make_superuser_headers(client)
    listing = client.get("/api/v1/admin/users", headers=headers)
    super_id = listing.json()[0]["id"]
    response = client.patch(
        f"/api/v1/admin/users/{super_id}",
        headers=headers,
        json={"is_superuser": False},
    )
    assert response.status_code == 400
    assert "last" in response.json()["detail"].lower()


def test_admin_patch_unknown_user(client):
    """Patching a non-existent user_id must return 404."""
    headers = _make_superuser_headers(client)
    fake_id = str(uuid.uuid4())
    response = client.patch(
        f"/api/v1/admin/users/{fake_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 404


def test_admin_patch_requires_superuser(client):
    """Ready non-superuser gets 403 with SuperUser detail on admin patch."""
    super_headers = _make_superuser_headers(client)
    normal = _make_normal_headers(client, super_headers)
    listing = client.get("/api/v1/admin/users", headers=super_headers)
    user_id = listing.json()[0]["id"]
    response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=normal,
        json={"is_active": False},
    )
    _assert_superuser_forbidden(response)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_status_empty(client):
    """bootstrap-status must report needs_bootstrap=true on an empty collection."""
    wipe_users()
    response = client.get("/api/v1/auth/bootstrap-status")
    assert response.status_code == 200
    assert response.json()["needs_bootstrap"] is True


def test_bootstrap_status_after_first_user(client):
    """bootstrap-status must report needs_bootstrap=false after the first user."""
    wipe_users()
    client.post(
        "/api/v1/auth/register",
        json={
            "email": f"boot-{uuid.uuid4().hex[:8]}@example.com",
            "password": "SecurePass123!",
        },
    )
    response = client.get("/api/v1/auth/bootstrap-status")
    assert response.status_code == 200
    assert response.json()["needs_bootstrap"] is False


# ---------------------------------------------------------------------------
# me endpoint
# ---------------------------------------------------------------------------


def test_me_includes_is_superuser(client):
    """GET /me must expose the is_superuser flag."""
    headers = _make_superuser_headers(client)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "is_superuser" in data
    assert data["is_superuser"] is True
    assert "must_change_password" in data
