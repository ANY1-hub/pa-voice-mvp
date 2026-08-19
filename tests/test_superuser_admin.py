"""Tests for SuperUser bootstrap and admin endpoints (Phase 5)."""

import uuid

from tests.conftest import wipe_users


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
    return {"Authorization": f"Bearer {token}"}


def _make_normal_headers(client, super_headers: dict) -> dict:
    """Create a non-super user via admin API and return their auth headers.

    Public register is closed after the first user, so the second account
    must be created by a SuperUser.
    """
    email = f"normal-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    create = client.post(
        "/api/v1/admin/users",
        headers=super_headers,
        json={"email": email, "password": password, "is_superuser": False},
    )
    assert create.status_code == 201, create.text
    assert create.json()["is_superuser"] is False
    assert create.json()["must_change_password"] is True

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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
    """Non-superuser must receive 403 on admin routes."""
    super_headers = _make_superuser_headers(client)
    normal = _make_normal_headers(client, super_headers)
    response = client.get("/api/v1/admin/users", headers=normal)
    assert response.status_code == 403


def test_admin_list_users_without_token(client):
    """Missing token must return 401."""
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


def test_admin_list_users_ok(client):
    """SuperUser can list all users."""
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
    """Normal user cannot patch via admin route."""
    super_headers = _make_superuser_headers(client)
    normal = _make_normal_headers(client, super_headers)
    listing = client.get("/api/v1/admin/users", headers=super_headers)
    user_id = listing.json()[0]["id"]
    response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=normal,
        json={"is_active": False},
    )
    assert response.status_code == 403


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
