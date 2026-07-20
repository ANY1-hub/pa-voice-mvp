"""API dependencies (Auth, Headers, etc.)."""

from uuid import UUID

from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str | None = Header(None, alias="X-User-Id")) -> str:
    """
    Extract and validate the user ID from the request header.
    Must be a valid UUID. If not, returns 401 Unauthorized.
    """
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    try:
        # Validate that it's a valid UUID
        val = UUID(x_user_id)
        return str(val)
    except ValueError as e:
        raise HTTPException(
            status_code=401, detail="X-User-Id header must be a valid UUID."
        ) from e
