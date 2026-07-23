"""Shared pytest fixtures."""

import os

import pytest
from fastapi.testclient import TestClient

# SECRET_KEY must be set before the app (and Settings) is imported
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-32chars!")

from src.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """
    Register a fresh user, log in, return Authorization header.
    Uses a unique email per test run to avoid collisions.
    """
    import uuid

    email = f"test-{uuid.uuid4().hex[:12]}@example.com"
    password = "SecurePass123!"

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}
