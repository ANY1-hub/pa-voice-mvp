"""Tests for SuperUser bootstrap and admin endpoints (Phase 5)."""

import uuid

from pymongo import MongoClient

from src.core.config import get_settings


def _wipe_users() -> None:
    """Remove all users so bootstrap can be tested deterministically.

    Safety: refuses to run against a non-test database name.
    """
    settings = get_settings()
    if "test" not in settings.mongodb_db_name.lower():
        raise RuntimeError(
            f"Refusing to wipe users collection: "
            f"DB name '{settings.mongodb_db_name}' does not look like a test DB. "
            "Set MONGODB_DB_NAME=jarvis_test (conftest does this automatically)."
        )
    sync = MongoClient(settings.mongodb_uri)
    try:
        sync[settings.mongodb_db_name]["users"].delete_many({})
    finally:
        sync.close()


def _make_superuser_headers(client) -> dict:
    """Register the first user (becomes SuperUser) and return auth headers."""
    _wipe_users()
    email = f"super-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["is_superuser"] is True

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_normal_headers(client) -> dict:
    """Register a second (non-super) user and return auth headers."""
    email = f"normal-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["is_superuser"] is False

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
    _wipe_users()
    email = f"first-{uuid.uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_superuser"] is True
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_second_register_is_not_superuser(client):
    """Any registration after the first must yield is_superuser=False."""
    _wipe_users()
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
    assert response.status_code == 201
    assert response.json()["is_superuser"] is False


def test_me_includes_is_superuser(client):
    """GET /me must expose the is_superuser flag."""
    headers = _make_superuser_headers(client)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "is_superuser" in data
    assert data["is_superuser"] is True


# ---------------------------------------------------------------------------
# SuperUser guard
# ---------------------------------------------------------------------------


def test_admin_list_users_requires_superuser(client):
    """Non-superuser must receive 403 on admin routes."""
    _wipe_users()
    # First user = super, second = normal
    _make_superuser_headers(client)
    normal = _make_normal_headers(client)
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
    _make_normal_headers(client)  # second user
    response = client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    for u in data:
        assert "id" in u
        assert "email" in u
        assert "is_superuser" in u
        assert "hashed_password" not in u


def test_admin_create_user_ok(client):
    """SuperUser can create a new user (default not superuser)."""
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


def test_admin_create_user_as_superuser(client):
    """SuperUser can create another SuperUser."""
    headers = _make_superuser_headers(client)
    email = f"admin-super-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={"email": email, "password": "SecurePass123!", "is_superuser": True},
    )
    assert response.status_code == 201
    assert response.json()["is_superuser"] is True


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
    # create a normal user via admin
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
    _wipe_users()
    super_headers = _make_superuser_headers(client)
    normal = _make_normal_headers(client)
    # grab a real id from list (as super) then try as normal
    listing = client.get("/api/v1/admin/users", headers=super_headers)
    user_id = listing.json()[0]["id"]
    response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=normal,
        json={"is_active": False},
    )
    assert response.status_code == 403
