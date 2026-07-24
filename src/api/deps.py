"""API dependencies (Auth + Memory + Voice + Orchestrator factories)."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorCollection

from src.auth.jwt import verify_access_token
from src.auth.repository import UserRepository
from src.core.config import get_settings
from src.db.mongodb import db_client
from src.memory.semantic_memory import SemanticMemory
from src.memory.working_memory import WorkingMemory
from src.models.user import User
from src.services.embeddings.openai import OpenAIEmbeddingsAdapter
from src.services.llm.base import LLMAdapter
from src.services.llm.openai import OpenAILLMAdapter
from src.services.orchestrator import ChatOrchestrator
from src.services.stt.base import STTAdapter
from src.services.stt.faster_whisper import FasterWhisperSTTAdapter
from src.services.tts.base import TTSAdapter
from src.services.tts.piper import PiperTTSAdapter

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Module-level singletons for heavy models (loaded once per process)
# ---------------------------------------------------------------------------
_stt_adapter: FasterWhisperSTTAdapter | None = None
_tts_adapter: PiperTTSAdapter | None = None
_llm_adapter: OpenAILLMAdapter | None = None


def get_users_collection() -> AsyncIOMotorCollection | None:
    """Return the users collection or None if DB is not connected."""
    if db_client.db is None:
        return None
    return db_client.db["users"]


def get_working_memory_collection() -> AsyncIOMotorCollection | None:
    """Return the working_memory collection or None if DB is not connected."""
    if db_client.db is None:
        return None
    return db_client.db["working_memory"]


def get_semantic_memory_collection() -> AsyncIOMotorCollection | None:
    """Return the semantic_memory collection or None if DB is not connected."""
    if db_client.db is None:
        return None
    return db_client.db["semantic_memory"]


def get_user_repository(
    collection: Annotated[AsyncIOMotorCollection | None, Depends(get_users_collection)],
) -> UserRepository:
    """Provide a UserRepository instance with the injected collection."""
    return UserRepository(collection=collection)


def get_embeddings_adapter() -> OpenAIEmbeddingsAdapter | None:
    """
    Create the embeddings adapter.

    Returns None if no OpenAI API key is configured so the system can still
    run without embeddings during local development / tests.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAIEmbeddingsAdapter()


def get_stt_adapter() -> STTAdapter:
    """Return a process-wide Faster-Whisper instance (loaded once)."""
    global _stt_adapter
    if _stt_adapter is None:
        _stt_adapter = FasterWhisperSTTAdapter()
    return _stt_adapter


def get_tts_adapter() -> TTSAdapter | None:
    """
    Return a process-wide Piper instance (loaded once).

    Returns None if the voice model file is missing so the rest of the
    system can still run (text-only mode).
    """
    global _tts_adapter
    if _tts_adapter is None:
        try:
            _tts_adapter = PiperTTSAdapter()
        except FileNotFoundError:
            # Voice model not present – TTS will be skipped
            return None
    return _tts_adapter


def get_llm_adapter() -> LLMAdapter:
    """Return a process-wide OpenAI LLM adapter (MVP default)."""
    global _llm_adapter
    if _llm_adapter is None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for the chat orchestrator (MVP)"
            )
        _llm_adapter = OpenAILLMAdapter()
    return _llm_adapter


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    repo: Annotated[UserRepository, Depends(get_user_repository)],
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

    user = await repo.get_by_id(user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_id(
    current_user: Annotated[User, Depends(get_current_user)],
) -> str:
    """
    Convenience dependency that returns only the user_id string.
    Keeps existing Memory routes working with minimal changes.
    """
    return current_user.id


def get_working_memory(
    user_id: Annotated[str, Depends(get_current_user_id)],
    collection: Annotated[
        AsyncIOMotorCollection | None, Depends(get_working_memory_collection)
    ],
) -> WorkingMemory:
    """Provide a WorkingMemory instance for the current user."""
    return WorkingMemory(user_id=user_id, collection=collection)


def get_semantic_memory(
    user_id: Annotated[str, Depends(get_current_user_id)],
    collection: Annotated[
        AsyncIOMotorCollection | None, Depends(get_semantic_memory_collection)
    ],
    embeddings: Annotated[
        OpenAIEmbeddingsAdapter | None, Depends(get_embeddings_adapter)
    ],
) -> SemanticMemory:
    """Provide a SemanticMemory instance for the current user."""
    return SemanticMemory(
        user_id=user_id,
        collection=collection,
        embeddings_adapter=embeddings,
    )


def get_orchestrator(
    llm: Annotated[LLMAdapter, Depends(get_llm_adapter)],
    stt: Annotated[STTAdapter, Depends(get_stt_adapter)],
    tts: Annotated[TTSAdapter | None, Depends(get_tts_adapter)],
    working_memory: Annotated[WorkingMemory, Depends(get_working_memory)],
    semantic_memory: Annotated[SemanticMemory, Depends(get_semantic_memory)],
) -> ChatOrchestrator:
    """Wire a ChatOrchestrator for the current authenticated user."""
    return ChatOrchestrator(
        llm=llm,
        stt=stt,
        tts=tts,
        working_memory=working_memory,
        semantic_memory=semantic_memory,
    )
