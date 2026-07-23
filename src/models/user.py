"""Pydantic models for User authentication."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field


def now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


# TODO user email-string validation with pydantic
class User(BaseModel):
    """User document stored in MongoDB."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=now_utc)
    is_active: bool = True


class UserCreate(BaseModel):
    """Payload for user registration."""

    email: EmailStr
    password: str = Field(min_length=12)


class UserLogin(BaseModel):
    """Payload for login."""

    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """Safe user representation (no password hash)."""

    id: str
    email: EmailStr
    created_at: datetime
    is_active: bool
