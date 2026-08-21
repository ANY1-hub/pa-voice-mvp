"""Pydantic models for User authentication."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.core.timezones import parse_iana_timezone


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
        must_change_password: Force a password change before chat.
        token_version: Incremented on password change; JWT ``ver`` must match.
        display_name: Preferred name Jarvis should use, or ``None`` until set.
        timezone: IANA timezone for spoken clock times, or ``None`` until set.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    hashed_password: str
    created_at: datetime = Field(default_factory=now_utc)
    is_active: bool = True
    is_superuser: bool = False
    must_change_password: bool = False
    token_version: int = 0
    display_name: str | None = None
    timezone: str | None = None

    def to_public(self) -> "UserPublic":
        """Safe user representation (no password hash)."""
        return UserPublic(
            id=self.id,
            email=self.email,
            created_at=self.created_at,
            is_active=self.is_active,
            is_superuser=self.is_superuser,
            must_change_password=self.must_change_password,
            display_name=self.display_name,
            timezone=self.timezone,
        )


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
        must_change_password: Whether a password change is still required.
        display_name: Preferred name, or ``None`` until first-login onboarding.
        timezone: IANA timezone for spoken clock times, or ``None`` until set.
    """

    id: str
    email: EmailStr
    created_at: datetime
    is_active: bool
    is_superuser: bool = False
    must_change_password: bool = False
    display_name: str | None = None
    timezone: str | None = None


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


class DisplayNameRequest(BaseModel):
    """Payload for first-login (or later) preferred-name update.

    Attributes:
        display_name: How Jarvis should address the user (1–40 characters).
    """

    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """Strip, collapse whitespace, and enforce the 40-character cap."""
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Display name cannot be empty")
        if len(cleaned) > 40:
            raise ValueError("Display name must be at most 40 characters")
        return cleaned


class TimezoneRequest(BaseModel):
    """Payload for the browser IANA timezone.

    Attributes:
        timezone: IANA name such as ``Europe/Berlin``.
    """

    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def normalize_timezone(cls, value: str) -> str:
        """Reject unknown IANA names so due times are never guessed."""
        return parse_iana_timezone(value)


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
