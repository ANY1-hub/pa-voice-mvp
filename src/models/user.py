"""Pydantic models for User authentication."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field


def now_utc() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        Timezone-aware ``datetime`` in UTC.
    """
    return datetime.now(UTC)


# TODO user email-string validation with pydantic
class User(BaseModel):
    """User document stored in MongoDB.

    Attributes:
        id: Server-generated UUID v4 string.
        email: Unique email address.
        hashed_password: Bcrypt password hash.
        created_at: Account creation timestamp (UTC).
        is_active: Whether the account is allowed to authenticate.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=now_utc)
    is_active: bool = True


class UserCreate(BaseModel):
    """Payload for user registration.

    Attributes:
        email: Email address (must be unique).
        password: Plain-text password (min. 12 characters).
    """

    email: EmailStr
    password: str = Field(min_length=12)


class UserLogin(BaseModel):
    """Payload for login.

    Attributes:
        email: Account email.
        password: Plain-text password.
    """

    email: EmailStr
    password: str


class UserPublic(BaseModel):
    """Safe user representation (no password hash).

    Attributes:
        id: User UUID.
        email: Email address.
        created_at: Account creation timestamp.
        is_active: Active flag.
    """

    id: str
    email: EmailStr
    created_at: datetime
    is_active: bool
