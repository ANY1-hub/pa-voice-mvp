"""Auth endpoint tests."""

import uuid


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
