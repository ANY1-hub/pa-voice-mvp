"""Shared pytest fixtures."""

import contextlib
import os
import uuid

# --- Test isolation: never touch the production database name ---
os.environ["MONGODB_DB_NAME"] = "jarvis_test"
# SECRET_KEY must be set before the app (and Settings) is imported
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-32chars!")

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from src.core.config import get_settings

get_settings.cache_clear()  # important: Settings is lru_cached

from src.main import app  # noqa: E402


def set_test_display_name(
    client: TestClient, headers: dict, name: str = "Test"
) -> None:
    """Complete first-login name onboarding so ready-user routes are allowed."""
    res = client.post(
        "/api/v1/auth/display-name",
        headers=headers,
        json={"display_name": name},
    )
    assert res.status_code == 200, res.text


def wipe_users() -> None:
    """Delete all users in the test DB so bootstrap/register stays deterministic.

    Safety: refuses to run if the DB name does not look like a test database.
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


@pytest.fixture(scope="session", autouse=True)
def _wipe_test_users_after_suite():
    """Do not leave a pytest SuperUser in jarvis_test after the suite."""
    yield
    with contextlib.suppress(Exception):
        wipe_users()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Wipe users, bootstrap-register one account, return Authorization header.

    Public register only works on an empty collection, so we wipe first.
    """
    wipe_users()
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
    headers = {"Authorization": f"Bearer {token}"}
    set_test_display_name(client, headers)
    return headers
