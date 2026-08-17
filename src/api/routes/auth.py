"""Authentication routes: register, login, me."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_user, get_user_repository
from src.auth.jwt import create_access_token
from src.auth.password import hash_password, verify_password
from src.auth.repository import UserRepository
from src.models.user import (
    ChangePasswordRequest,
    User,
    UserCreate,
    UserLogin,
    UserPublic,
)

router = APIRouter()


def _to_public(user: User) -> UserPublic:
    """Map a User document to the public response model."""
    return UserPublic(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
    )


@router.get("/bootstrap-status")
async def bootstrap_status(
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> dict:
    """Report whether the first SuperUser account still needs to be created."""
    count = await repo.count()
    return {"needs_bootstrap": count == 0}


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(
    payload: UserCreate,
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserPublic:
    """Register a new user. Email must be unique.

    The first successful registration on an empty users collection
    automatically becomes a SuperUser (bootstrap).

    Args:
        payload: Registration data (email + password).
        repo: Injected user repository.

    Returns:
        Public user representation of the newly created account.
    """
    if (await repo.count()) > 0:
        raise HTTPException(
            403,
            detail="Public registration is closed. Ask an administrator to create your account.",
        )
    existing = await repo.get_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # first user only:

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        is_superuser=True,
        must_change_password=False,
    )
    await repo.create(user)

    return UserPublic(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )


@router.post("/login")
async def login(
    payload: UserLogin,
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> dict:
    """Authenticate and return a JWT access token.

    Args:
        payload: Login credentials (email + password).
        repo: Injected user repository.

    Returns:
        Dict with ``access_token`` and ``token_type`` (``\"bearer\"``).
    """
    user = await repo.get_by_email(payload.email)

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserPublic)
async def me(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserPublic:
    """Return the currently authenticated user.

    Args:
        current_user: User resolved from the JWT (via dependency).

    Returns:
        Public user representation.
    """
    return _to_public(current_user)


@router.post("/change-password", response_model=UserPublic)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserPublic:
    """Return the currently authenticated user.

    Args:
        current_user: User resolved from the JWT (via dependency).

    Returns:
        Public user representation.
    """
    return _to_public(current_user)
