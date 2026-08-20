"""Authentication routes: register, login, me."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError

from src.api.deps import (
    get_current_user,
    get_embeddings_adapter,
    get_semantic_memory_collection,
    get_user_repository,
)
from src.auth.jwt import create_access_token
from src.auth.password import hash_password, verify_password
from src.auth.repository import UserRepository
from src.memory.semantic_memory import SemanticMemory
from src.models.user import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    DisplayNameRequest,
    User,
    UserCreate,
    UserLogin,
    UserPublic,
)
from src.services.embeddings.openai import OpenAIEmbeddingsAdapter
from src.services.memory_facts import FACT_IMPORTANCE

logger = logging.getLogger(__name__)

router = APIRouter()


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
    try:
        await repo.create(user, extra={"bootstrap_slot": 0})
    except DuplicateKeyError:
        raise HTTPException(
            403,
            detail="Public registration is closed. Ask an administrator to create your account.",
        ) from None

    return user.to_public()


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

    access_token = create_access_token(
        subject=user.id, token_version=user.token_version
    )
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
    return current_user.to_public()


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
) -> ChangePasswordResponse:
    """Change the current user's password and return a JWT for the new version."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password",
        )

    updated = await repo.update_password(
        current_user.id,
        hashed_password=hash_password(payload.new_password),
        must_change_password=False,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    public = updated.to_public()
    return ChangePasswordResponse(
        **public.model_dump(),
        access_token=create_access_token(
            subject=updated.id, token_version=updated.token_version
        ),
        token_type="bearer",
    )


@router.post("/display-name", response_model=UserPublic)
async def set_display_name(
    payload: DisplayNameRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    repo: UserRepository = Depends(get_user_repository),  # noqa: B008
    semantic_collection: AsyncIOMotorCollection | None = Depends(  # noqa: B008
        get_semantic_memory_collection
    ),
    embeddings: OpenAIEmbeddingsAdapter | None = Depends(  # noqa: B008
        get_embeddings_adapter
    ),
) -> UserPublic:
    """Store how Jarvis should address the user; required after first login.

    Writes a semantic fact so Active Recall can find the name later.
    Password change (if required) must complete first.
    """
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )

    updated = await repo.set_display_name(current_user.id, payload.display_name)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        memory = SemanticMemory(
            user_id=updated.id,
            collection=semantic_collection,
            embeddings_adapter=embeddings,
        )
        await memory.add_fact(
            fact=f"The user prefers to be addressed as {payload.display_name}.",
            importance=FACT_IMPORTANCE,
            entities=[payload.display_name],
        )
    except Exception:
        logger.exception("Failed to store display-name fact in semantic memory")

    return updated.to_public()
