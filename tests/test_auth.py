"""Auth endpoint tests."""

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt

from src.core.config import get_settings
from src.db.mongodb import db_client


def test_register_success(client):
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


def test_register_duplicate_email(client):
    email = f"dup-{uuid.uuid4().hex[:10]}@example.com"
    payload = {"email": email, "password": "SecurePass123!"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_register_short_password(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_login_success(client):
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
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "SecurePass123!"},
    )
    assert response.status_code == 401


def test_me_with_valid_token(client, auth_headers):
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "id" in data
    assert "hashed_password" not in data


def test_me_without_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_malformed_token(client):
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

    # Deactivate the user directly in the DB
    assert db_client.db is not None
    result = db_client.db["users"].update_one(
        {"id": user_id}, {"$set": {"is_active": False}}
    )
    assert result.modified_count == 1

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
