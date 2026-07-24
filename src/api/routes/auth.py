"""Authentication routes: register, login, me."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_user, get_user_repository
from src.auth.jwt import create_access_token
from src.auth.password import hash_password, verify_password
from src.auth.repository import UserRepository
from src.models.user import User, UserCreate, UserLogin, UserPublic

router = APIRouter()


@router.post(
    "/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED
)
async def register(
    payload: UserCreate,
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> UserPublic:
    """Register a new user. Email must be unique."""
    existing = await repo.get_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
    )
    await repo.create(user)

    return UserPublic(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active,
    )


@router.post("/login")
async def login(
    payload: UserLogin,
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> dict:
    """Authenticate and return a JWT access token."""
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
    """Return the currently authenticated user."""
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
        is_active=current_user.is_active,
    )
