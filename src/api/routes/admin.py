"""Admin routes – SuperUser only (user management)."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_superuser, get_user_repository
from src.auth.password import hash_password
from src.auth.repository import UserRepository
from src.models.user import User, UserAdminCreate, UserAdminUpdate, UserPublic

router = APIRouter()


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
    return [
        UserPublic(
            id=u.id,
            email=u.email,
            created_at=u.created_at,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
        )
        for u in users
    ]


@router.post(
    "/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
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
    )
    await repo.create(user)

    return UserPublic(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )


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

    return UserPublic(
        id=updated.id,
        email=updated.email,
        created_at=updated.created_at,
        is_active=updated.is_active,
        is_superuser=updated.is_superuser,
    )
