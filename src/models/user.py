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


class User(BaseModel):
    """User document stored in MongoDB.

    Attributes:
        id: Server-generated UUID v4 string.
        email: Unique email address.
        hashed_password: Bcrypt password hash.
        created_at: Account creation timestamp (UTC).
        is_active: Whether the account is allowed to authenticate.
        is_superuser: Whether the account has admin privileges.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=now_utc)
    is_active: bool = True
    is_superuser: bool = False
    must_change_password: bool = False
    token_version: int = 0


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
        is_superuser: Superuser flag.
    """

    id: str
    email: EmailStr
    created_at: datetime
    is_active: bool
    is_superuser: bool = False
    must_change_password: bool = False


class UserAdminCreate(BaseModel):
    """Payload for admin-created users.

    Attributes:
        email: Email address (must be unique).
        password: Plain-text password (min. 12 characters).
        is_superuser: Whether the new account should be a SuperUser.
    """

    email: EmailStr
    password: str = Field(min_length=12)
    is_superuser: bool = False
    is_active: bool = True


class UserAdminUpdate(BaseModel):
    """Partial update payload for admin PATCH.

    Attributes:
        is_active: Optional new active flag.
        is_superuser: Optional new superuser flag.
    """

    is_active: bool | None = None
    is_superuser: bool | None = None


class ChangePasswordRequest(BaseModel):
    """Payload for authenticated password change.

    Attributes:
        current_password: Existing password (must match).
        new_password: New password (min. 12 characters).
    """

    current_password: str
    new_password: str = Field(min_length=12)


class ChangePasswordResponse(UserPublic):
    """Password-change result: public user plus a JWT for the new token_version."""

    access_token: str
    token_type: str = "bearer"
