"""JWT creation and verification."""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from src.core.config import get_settings


def create_access_token(subject: str, token_version: int = 0) -> str:
    """Create a JWT access token.

    Args:
        subject: User ID (UUID as string) stored in the ``sub`` claim.
        token_version: Password-generation counter (``ver`` claim). Bumped on
            password change so older tokens stop verifying.

    Returns:
        Encoded JWT access token string.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": subject, "exp": expire, "ver": int(token_version)}
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> tuple[str, int] | None:
    """Verify a JWT and return ``(subject, token_version)``.

    Args:
        token: Encoded JWT string from the Authorization header.

    Returns:
        ``(user_id, version)`` if the token is valid, otherwise ``None``.
        Tokens minted before ``ver`` existed decode as version ``0``.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        subject: str | None = payload.get("sub")
        if not subject:
            return None
        raw_ver = payload.get("ver", 0)
        try:
            version = int(raw_ver)
        except (TypeError, ValueError):
            version = 0
        return subject, version
    except JWTError:
        return None


def verify_access_token(token: str) -> str | None:
    """Verify a JWT and return the subject (user_id).

    Args:
        token: Encoded JWT string from the Authorization header.

    Returns:
        The ``sub`` claim (user_id) if the token is valid, otherwise ``None``.
    """
    claims = decode_access_token(token)
    return claims[0] if claims else None
