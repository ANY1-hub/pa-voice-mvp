"""Auth endpoint tests."""

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt
from pymongo import MongoClient

from src.core.config import get_settings
from tests.conftest import wipe_users


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


def test_register_duplicate_email(client):
    """Registering the same email twice: second attempt is closed (403), not 409.

    After the first user exists, public registration is fully closed, so a
    duplicate email never reaches the uniqueness check via this route.
    """
    wipe_users()
    email = f"dup-{uuid.uuid4().hex[:10]}@example.com"
    payload = {"email": email, "password": "SecurePass123!"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 403


def test_register_short_password(client):
    """Passwords below the minimum length must be rejected with 422."""
    wipe_users()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_success(client):
    """Valid credentials must return a bearer access token."""
    wipe_users()
    email = f"login-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    """Wrong password must return 401 without leaking whether the email exists."""
    wipe_users()
    email = f"wrong-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePass123!"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword99!"},
    )
    assert response.status_code == 401


def test_login_unknown_email(client):
    """Unknown email must return 401 (same shape as wrong password)."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "SecurePass123!"},
    )
    assert response.status_code == 401


def test_me_with_valid_token(client, auth_headers):
    """Valid JWT must return the current user profile without hashed_password."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "id" in data
    assert "hashed_password" not in data


def test_me_without_token(client):
    """Missing Authorization header must return 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_malformed_token(client):
    """Non-JWT bearer value must return 401."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_me_with_invalid_signature(client):
    """Token signed with a different secret must be rejected."""
    fake = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "completely-wrong-secret-key-xxxxx",
        algorithm="HS256",
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fake}"},
    )
    assert response.status_code == 401


def test_me_with_expired_token(client):
    """Token whose exp is in the past must be rejected."""
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401


def test_me_with_inactive_user(client):
    """Valid token for a deactivated user must still be rejected."""
    wipe_users()
    email = f"inactive-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    settings = get_settings()
    sync_client = MongoClient(settings.mongodb_uri)
    try:
        result = sync_client[settings.mongodb_db_name]["users"].update_one(
            {"id": user_id}, {"$set": {"is_active": False}}
        )
        assert result.modified_count == 1
    finally:
        sync_client.close()

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_memory_with_invalid_token(client):
    """Memory endpoints must also reject invalid tokens."""
    response = client.post(
        "/api/v1/memory/working",
        headers={"Authorization": "Bearer garbage-token"},
        json={"content": "should fail", "importance_score": 0.5},
    )
    assert response.status_code == 401


def test_change_password_success(client):
    """Changing password with the correct current password must clear must_change_password."""
    wipe_users()
    email = f"chpw-{uuid.uuid4().hex[:10]}@example.com"
    old_pw = "SecurePass123!"
    new_pw = "NewSecurePass99!"

    # Bootstrap superuser (no forced change)
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_pw},
    )
    assert reg.status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_pw},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": old_pw, "new_password": new_pw},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False

    # Old password must no longer work
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": old_pw},
        ).status_code
        == 401
    )
    # New password must work
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": new_pw},
        ).status_code
        == 200
    )


def test_change_password_wrong_current(client):
    """Wrong current password must return 400 and leave the password unchanged."""
    wipe_users()
    email = f"chpw-bad-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongPassword99!",
            "new_password": "NewSecurePass99!",
        },
    )
    assert response.status_code == 400
    assert "incorrect" in response.json()["detail"].lower()

    # Original password still works
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        ).status_code
        == 200
    )


def test_change_password_same_as_old(client):
    """New password identical to the current one must be rejected."""
    wipe_users()
    email = f"chpw-same-{uuid.uuid4().hex[:10]}@example.com"
    password = "SecurePass123!"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": password, "new_password": password},
    )
    assert response.status_code == 400
    assert "differ" in response.json()["detail"].lower()


def test_change_password_requires_auth(client):
    """change-password without a token must return 401."""
    response = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "SecurePass123!",
            "new_password": "NewSecurePass99!",
        },
    )
    assert response.status_code == 401


def test_admin_created_user_must_change_password_then_clear(client):
    """Admin-created user starts with must_change_password=true; change clears it."""
    wipe_users()
    # Bootstrap super
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

    # Admin creates user with initial password
    user_email = f"forced-{uuid.uuid4().hex[:8]}@example.com"
    initial_pw = "InitialPass123!"
    create = client.post(
        "/api/v1/admin/users",
        headers=super_headers,
        json={"email": user_email, "password": initial_pw},
    )
    assert create.status_code == 201
    assert create.json()["must_change_password"] is True

    user_token = client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": initial_pw},
    ).json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    me = client.get("/api/v1/auth/me", headers=user_headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={"current_password": initial_pw, "new_password": "FinalPass1234!"},
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False


def test_must_change_password_blocks_memory_but_allows_me(client):
    """Admin-created users must change password before chat/memory, but /me stays open."""
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

    me = client.get("/api/v1/auth/me", headers=user_headers)
    assert me.status_code == 200
    blocked = client.get("/api/v1/memory/working", headers=user_headers)
    assert blocked.status_code == 403
    assert "password" in blocked.json()["detail"].lower()


def test_password_change_invalidates_old_token(client):
    """After a password change the previous JWT must no longer authenticate."""
    wipe_users()
    email = f"rot-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    old_token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {old_token}"}

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": password, "new_password": "NewSecurePass99!"},
    )
    assert changed.status_code == 200

    stale = client.get("/api/v1/auth/me", headers=headers)
    assert stale.status_code == 401


def test_password_change_returns_token_that_authenticates(client):
    """Change-password must mint a JWT that still authenticates after rotation."""
    wipe_users()
    email = f"fresh-{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePass123!"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    old_token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]

    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={"current_password": password, "new_password": "NewSecurePass99!"},
    )
    assert changed.status_code == 200
    new_token = changed.json()["access_token"]
    assert new_token
    assert new_token != old_token

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert me.status_code == 200
    assert me.json()["must_change_password"] is False
    assert me.json()["email"] == email
