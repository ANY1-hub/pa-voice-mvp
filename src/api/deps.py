"""API dependencies (Auth)."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.jwt import verify_access_token
from src.auth.repository import UserRepository
from src.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> User:
    """
    Extract and validate the JWT from the Authorization header.
    Returns the full User object or raises 401.
    """
    token = credentials.credentials
    user_id = verify_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = UserRepository()
    user = await repo.get_by_id(user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_id(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> str:
    """
    Convenience dependency that returns only the user_id string.
    Keeps existing Memory routes working with minimal changes.
    """
    return current_user.id
