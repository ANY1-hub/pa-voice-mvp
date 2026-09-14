"""Password hashing utilities (bcrypt via passlib)."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BCRYPT_MAX_BYTES = 72
_TOO_LONG = "Password is too long (bcrypt limit is 72 bytes)."


def password_utf8_byte_length(plain_password: str) -> int:
    """Return UTF-8 byte length (bcrypt's input unit, not character count)."""
    return len(plain_password.encode("utf-8"))


def ensure_password_fits_bcrypt(plain_password: str) -> str:
    """Reject passwords bcrypt would silently truncate.

    Args:
        plain_password: Raw password from the user.

    Returns:
        The same string if it fits in 72 UTF-8 bytes.

    Raises:
        ValueError: If UTF-8 length exceeds ``BCRYPT_MAX_BYTES``.
    """
    if password_utf8_byte_length(plain_password) > BCRYPT_MAX_BYTES:
        raise ValueError(_TOO_LONG)
    return plain_password


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password.

    Args:
        plain_password: Raw password from the user.

    Returns:
        Bcrypt hash string suitable for storage.
    """
    ensure_password_fits_bcrypt(plain_password)
    return str(pwd_context.hash(plain_password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored hash.

    Args:
        plain_password: Password provided at login.
        hashed_password: Stored bcrypt hash.

    Returns:
        ``True`` if the password matches, otherwise ``False``.
    """
    if password_utf8_byte_length(plain_password) > BCRYPT_MAX_BYTES:
        return False
    return bool(pwd_context.verify(plain_password, hashed_password))
