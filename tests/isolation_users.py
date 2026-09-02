"""Two real users for tenant-isolation tests.

Public register only works on an empty users collection. The second account
is created by the first user (SuperUser) via POST /api/v1/admin/users.
Admin-created accounts must change password before chat/memory/reminders;
the JWT returned by change-password replaces the login token.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeVar

from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from src.core.config import get_settings
from tests.conftest import set_test_display_name, wipe_users

T = TypeVar("T")

PASSWORD_A = "SecurePass123!"
PASSWORD_B_INITIAL = "InitialPass123!"
PASSWORD_B = "ChangedPass123!"


@dataclass(frozen=True)
class ReadyUser:
    """Authenticated user that has passed the ready-user gate."""

    email: str
    user_id: str
    headers: dict[str, str]


def two_ready_users(client: TestClient) -> tuple[ReadyUser, ReadyUser]:
    """Register SuperUser A, admin-create B, finish B's password and name.

    Returns:
        ``(user_a, user_b)`` with JWT headers and real ``users`` collection ids.
    """
    wipe_users()

    email_a = f"iso-a-{uuid.uuid4().hex[:10]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email_a, "password": PASSWORD_A},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["is_superuser"] is True
    assert reg.json()["must_change_password"] is False

    login_a = client.post(
        "/api/v1/auth/login",
        json={"email": email_a, "password": PASSWORD_A},
    )
    assert login_a.status_code == 200, login_a.text
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    set_test_display_name(client, headers_a, name="Ada")

    email_b = f"iso-b-{uuid.uuid4().hex[:10]}@example.com"
    create = client.post(
        "/api/v1/admin/users",
        headers=headers_a,
        json={
            "email": email_b,
            "password": PASSWORD_B_INITIAL,
            "is_superuser": False,
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["is_superuser"] is False
    assert create.json()["must_change_password"] is True

    login_b = client.post(
        "/api/v1/auth/login",
        json={"email": email_b, "password": PASSWORD_B_INITIAL},
    )
    assert login_b.status_code == 200, login_b.text
    headers_b_login = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers_b_login,
        json={
            "current_password": PASSWORD_B_INITIAL,
            "new_password": PASSWORD_B,
        },
    )
    assert changed.status_code == 200, changed.text
    headers_b = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    set_test_display_name(client, headers_b, name="Bea")

    me_a = client.get("/api/v1/auth/me", headers=headers_a)
    me_b = client.get("/api/v1/auth/me", headers=headers_b)
    assert me_a.status_code == 200, me_a.text
    assert me_b.status_code == 200, me_b.text
    id_a = me_a.json()["id"]
    id_b = me_b.json()["id"]
    assert id_a != id_b

    return (
        ReadyUser(email=email_a, user_id=id_a, headers=headers_a),
        ReadyUser(email=email_b, user_id=id_b, headers=headers_b),
    )


def run_async(coro: Awaitable[T]) -> T:
    """Run a coroutine on a fresh event loop (Motor client for that loop)."""
    return asyncio.run(coro)


@asynccontextmanager
async def mongo_collection(name: str) -> AsyncIterator[AsyncIOMotorCollection]:
    """Yield a Motor collection on a client bound to the current asyncio loop."""
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    try:
        yield client[settings.mongodb_db_name][name]
    finally:
        client.close()
