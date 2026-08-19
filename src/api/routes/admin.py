"""Admin routes – SuperUser only (user management)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from src.api.deps import get_current_superuser, get_user_repository
from src.auth.password import hash_password
from src.auth.repository import UserRepository
from src.models.user import User, UserAdminCreate, UserAdminUpdate, UserPublic

router = APIRouter()


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
    )


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    _super: User = Depends(get_current_superuser),  # noqa: B008
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> list[UserPublic]:
    """List all users (SuperUser only).

    Args:
        _super: Authenticated SuperUser (guard).
        repo: Injected user repository.

    Returns:
        List of public user representations.
    """
    users = await repo.list_users(limit=200)
    return [_to_public(u) for u in users]


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserAdminCreate,
    _super: User = Depends(get_current_superuser),  # noqa: B008
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserPublic:
    """Create a new user (SuperUser only).

    Args:
        payload: Email, password and optional is_superuser flag.
        _super: Authenticated SuperUser (guard).
        repo: Injected user repository.

    Returns:
        Public representation of the created user.
    """
    existing = await repo.get_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        is_superuser=payload.is_superuser,
        is_active=payload.is_active,
        must_change_password=True,  # force change on first login
    )
    try:
        await repo.create(user)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None

    return _to_public(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: str,
    payload: UserAdminUpdate,
    _super: User = Depends(get_current_superuser),  # noqa: B008
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserPublic:
    """Update is_active and/or is_superuser of a user (SuperUser only).

    Args:
        user_id: Target user UUID.
        payload: Fields to change (only provided ones are applied).
        _super: Authenticated SuperUser (guard).
        repo: Injected user repository.

    Returns:
        Updated public user representation.
    """
    would_demote = payload.is_superuser is False
    would_deactivate = payload.is_active is False
    if would_demote or would_deactivate:
        users = await repo.list_users(limit=500)
        target = next((u for u in users if u.id == user_id), None)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        remaining_supers = [
            u for u in users if u.id != user_id and u.is_superuser and u.is_active
        ]
        target_still_super = (
            target.is_superuser if payload.is_superuser is None else payload.is_superuser
        )
        target_still_active = (
            target.is_active if payload.is_active is None else payload.is_active
        )
        if not remaining_supers and not (target_still_super and target_still_active):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last active SuperUser",
            )

    updated = await repo.update(
        user_id,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _to_public(updated)
