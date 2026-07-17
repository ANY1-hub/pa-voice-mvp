"""Shared FastAPI dependencies."""

from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    """
    Simple user isolation for the MVP.

    Requires the client to send an `X-User-Id` header.
    Full JWT authentication will replace this later.
    """
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing or empty X-User-Id header",
        )
    return x_user_id.strip()
