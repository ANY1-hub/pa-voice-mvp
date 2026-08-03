"""Unit tests for auth core (JWT, password hashing, UserRepository)."""

from unittest.mock import AsyncMock

import pytest

from src.auth.jwt import create_access_token, verify_access_token
from src.auth.password import hash_password, verify_password
from src.auth.repository import UserRepository
from src.models.user import User

# ---------------------------------------------------------------------------
# password
# ---------------------------------------------------------------------------


def test_hash_password_not_plaintext():
    """Hashed password must differ from plaintext and use bcrypt format."""
    plain = "SecurePass123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2")  # bcrypt


def test_verify_password_ok():
    """Correct password must verify against its hash."""
    plain = "SecurePass123!"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong():
    """Wrong password must fail verification."""
    hashed = hash_password("SecurePass123!")
    assert verify_password("wrong-password", hashed) is False


# ---------------------------------------------------------------------------
# jwt
# ---------------------------------------------------------------------------


def test_create_and_verify_token_roundtrip():
    """JWT create → verify must return the original subject user_id."""
    user_id = "11111111-2222-3333-4444-555555555555"
    token = create_access_token(subject=user_id)
    assert isinstance(token, str)
    assert len(token) > 20
    assert verify_access_token(token) == user_id


def test_verify_invalid_token_returns_none():
    """Garbage token string must yield None, not raise."""
    assert verify_access_token("not.a.jwt") is None


def test_verify_tampered_token_returns_none():
    """Tampered JWT signature must yield None."""
    token = create_access_token(subject="some-user-id")
    # Flip a character in the payload/signature section
    tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    assert verify_access_token(tampered) is None


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repo_create_without_collection_raises():
    """UserRepository.create without DB must raise RuntimeError."""
    repo = UserRepository(collection=None)
    user = User(email="a@example.com", hashed_password="x")
    with pytest.raises(RuntimeError, match="not connected"):
        await repo.create(user)


@pytest.mark.asyncio
async def test_repo_get_by_email_none_collection():
    """get_by_email without collection must return None."""
    repo = UserRepository(collection=None)
    assert await repo.get_by_email("a@example.com") is None


@pytest.mark.asyncio
async def test_repo_get_by_id_none_collection():
    """get_by_id without collection must return None."""
    repo = UserRepository(collection=None)
    assert await repo.get_by_id("some-id") is None


@pytest.mark.asyncio
async def test_repo_create_inserts():
    """create must insert a document and lowercase the email domain."""
    collection = AsyncMock()
    repo = UserRepository(collection=collection)
    # EmailStr lowercases the domain part
    user = User(email="Test@Example.com", hashed_password="hash")

    result = await repo.create(user)

    assert result is user
    collection.insert_one.assert_awaited_once()
    dumped = collection.insert_one.await_args.args[0]
    assert dumped["email"] == "Test@example.com"


@pytest.mark.asyncio
async def test_repo_get_by_email_found():
    """get_by_email must find the user case-insensitively on the email."""
    user = User(email="user@example.com", hashed_password="hash")
    doc = user.model_dump(mode="json")
    doc["_id"] = "mongo-id"

    collection = AsyncMock()
    collection.find_one = AsyncMock(return_value=doc)
    repo = UserRepository(collection=collection)

    found = await repo.get_by_email("USER@example.com")

    assert found is not None
    assert found.email == "user@example.com"
    collection.find_one.assert_awaited_once_with({"email": "user@example.com"})


@pytest.mark.asyncio
async def test_repo_get_by_email_not_found():
    """Missing email must return None."""
    collection = AsyncMock()
    collection.find_one = AsyncMock(return_value=None)
    repo = UserRepository(collection=collection)

    assert await repo.get_by_email("missing@example.com") is None


@pytest.mark.asyncio
async def test_repo_get_by_id_found():
    """get_by_id must return the matching user."""
    user = User(email="user@example.com", hashed_password="hash")
    doc = user.model_dump(mode="json")
    doc["_id"] = "mongo-id"

    collection = AsyncMock()
    collection.find_one = AsyncMock(return_value=doc)
    repo = UserRepository(collection=collection)

    found = await repo.get_by_id(user.id)

    assert found is not None
    assert found.id == user.id
    collection.find_one.assert_awaited_once_with({"id": user.id})
