"""JWT creation and verification."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from src.core.config import get_settings


def create_access_token(subject: str) -> str:
    """Create a JWT access token.

    Args:
        subject: User ID (UUID as string) stored in the ``sub`` claim.

    Returns:
        Encoded JWT access token string.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def verify_access_token(token: str) -> str | None:
    """Verify a JWT and return the subject (user_id).

    Args:
        token: Encoded JWT string from the Authorization header.

    Returns:
        The ``sub`` claim (user_id) if the token is valid, otherwise ``None``.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        subject: str | None = payload.get("sub")
        return subject
    except JWTError:
        return None
