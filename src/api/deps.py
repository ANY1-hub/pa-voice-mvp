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
from src.skills.active_recall.skill import ActiveRecallSkill
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill
from src.skills.web_search.skill import WebSearchSkill

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Module-level singletons for heavy models (loaded once per process)
# ---------------------------------------------------------------------------
_stt_adapter: FasterWhisperSTTAdapter | None = None
_tts_adapter: PiperTTSAdapter | None = None
_llm_adapter: OpenAILLMAdapter | None = None


def get_users_collection() -> AsyncIOMotorCollection | None:
    """Return the users collection or ``None`` if DB is not connected.

    Returns:
        MongoDB collection for users, or ``None``.
    """
    if db_client.db is None:
        return None
    return db_client.db["users"]


def get_working_memory_collection() -> AsyncIOMotorCollection | None:
    """Return the working_memory collection or ``None`` if DB is not connected.

    Returns:
        MongoDB collection for working memory, or ``None``.
    """
    if db_client.db is None:
        return None
    return db_client.db["working_memory"]


def get_semantic_memory_collection() -> AsyncIOMotorCollection | None:
    """Return the semantic_memory collection or ``None`` if DB is not connected.

    Returns:
        MongoDB collection for semantic memory, or ``None``.
    """
    if db_client.db is None:
        return None
    return db_client.db["semantic_memory"]


def get_notes_collection() -> AsyncIOMotorCollection | None:
    """Return the notes collection or ``None`` if DB is not connected.

    Returns:
        MongoDB collection for notes, or ``None``.
    """
    if db_client.db is None:
        return None
    return db_client.db["notes"]


def get_reminders_collection() -> AsyncIOMotorCollection | None:
    """Return the reminders collection or ``None`` if DB is not connected.

    Returns:
        MongoDB collection for reminders, or ``None``.
    """
    if db_client.db is None:
        return None
    return db_client.db["reminders"]


# -----------------------------------------------------------------------------


def get_user_repository(
    collection: Annotated[AsyncIOMotorCollection | None, Depends(get_users_collection)],
) -> UserRepository:
    """Provide a UserRepository instance with the injected collection.

    Args:
        collection: Users collection (maybe ``None`` in tests).

    Returns:
        Configured ``UserRepository``.
    """
    return UserRepository(collection=collection)


def get_embeddings_adapter() -> OpenAIEmbeddingsAdapter | None:
    """Create the embeddings adapter.

    Returns:
        ``OpenAIEmbeddingsAdapter`` if an API key is configured, otherwise
        ``None`` so the system can still run without embeddings.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAIEmbeddingsAdapter()


def get_stt_adapter() -> STTAdapter:
    """Return a process-wide Faster-Whisper instance (loaded once).

    Returns:
        Shared ``STTAdapter`` singleton.
    """
    global _stt_adapter
    if _stt_adapter is None:
        _stt_adapter = FasterWhisperSTTAdapter()
    return _stt_adapter


def get_tts_adapter() -> TTSAdapter | None:
    """Return a process-wide Piper instance (loaded once).

    Returns:
        Shared ``TTSAdapter`` singleton, or ``None`` if the voice model file
        is missing (text-only mode).
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
    """Return a process-wide OpenAI LLM adapter (MVP default).

    Returns:
        Shared ``LLMAdapter`` singleton.

    Raises:
        RuntimeError: If ``OPENAI_API_KEY`` is not configured.
    """
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
    """Extract and validate the JWT from the Authorization header.

    Args:
        credentials: Bearer token from the request.
        repo: User repository used to load the full user record.

    Returns:
        Authenticated ``User`` object.

    Raises:
        HTTPException: 401 if the token is invalid/expired or the user is
            missing/inactive.
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


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require that the authenticated user is a SuperUser.

    Args:
        current_user: User resolved by ``get_current_user``.

    Returns:
        The same ``User`` if ``is_superuser`` is True.

    Raises:
        HTTPException: 403 if the user is not a SuperUser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user


async def get_current_user_id(
    current_user: Annotated[User, Depends(get_current_user)],
) -> str:
    """Return only the user_id string of the authenticated user.

    Args:
        current_user: Full user resolved by ``get_current_user``.

    Returns:
        User ID (UUID string).
    """
    return current_user.id


def get_working_memory(
    user_id: Annotated[str, Depends(get_current_user_id)],
    collection: Annotated[
        AsyncIOMotorCollection | None, Depends(get_working_memory_collection)
    ],
) -> WorkingMemory:
    """Provide a WorkingMemory instance for the current user.

    Args:
        user_id: Authenticated user ID.
        collection: Working-memory MongoDB collection (maybe ``None``).

    Returns:
        ``WorkingMemory`` bound to the current user.
    """
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
    """Provide a SemanticMemory instance for the current user.

    Args:
        user_id: Authenticated user ID.
        collection: Semantic-memory MongoDB collection (maybe ``None``).
        embeddings: Optional embeddings adapter for vector search.

    Returns:
        ``SemanticMemory`` bound to the current user.
    """
    return SemanticMemory(
        user_id=user_id,
        collection=collection,
        embeddings_adapter=embeddings,
    )


def get_note_repository(
    user_id: Annotated[str, Depends(get_current_user_id)],
    collection: Annotated[AsyncIOMotorCollection | None, Depends(get_notes_collection)],
) -> NoteRepository:
    """Provide a NoteRepository instance for the current user.

    Args:
        user_id: Authenticated user ID.
        collection: Notes MongoDB collection (maybe ``None``).

    Returns:
        ``NoteRepository`` bound to the current user.
    """
    return NoteRepository(user_id=user_id, collection=collection)


def get_reminder_repository(
    user_id: Annotated[str, Depends(get_current_user_id)],
    collection: Annotated[
        AsyncIOMotorCollection | None, Depends(get_reminders_collection)
    ],
) -> ReminderRepository:
    return ReminderRepository(user_id=user_id, collection=collection)


def get_skill_registry(
    note_repo: Annotated[NoteRepository, Depends(get_note_repository)],
    reminder_repo: Annotated[ReminderRepository, Depends(get_reminder_repository)],
    semantic_memory: Annotated[SemanticMemory, Depends(get_semantic_memory)],
) -> SkillRegistry:
    """Build and return a SkillRegistry with all available skills for the user.

    ActiveRecall is registered first so pure knowledge questions are not
    claimed by Notes / Reminders / WebSearch.

    Args:
        note_repo: User-scoped note repository.
        reminder_repo: User-scoped reminder repository
        semantic_memory: User-scoped semantic memory (for summary facts).

    Returns:
        ``SkillRegistry`` with registered skills.
    """
    registry = SkillRegistry()
    registry.register(ActiveRecallSkill(semantic_memory=semantic_memory))
    registry.register(NotesSkill(repository=note_repo, semantic_memory=semantic_memory))
    registry.register(
        RemindersSkill(repository=reminder_repo, semantic_memory=semantic_memory)
    )
    registry.register(WebSearchSkill(semantic_memory=semantic_memory))
    return registry


def get_orchestrator(
    llm: Annotated[LLMAdapter, Depends(get_llm_adapter)],
    stt: Annotated[STTAdapter, Depends(get_stt_adapter)],
    tts: Annotated[TTSAdapter | None, Depends(get_tts_adapter)],
    working_memory: Annotated[WorkingMemory, Depends(get_working_memory)],
    semantic_memory: Annotated[SemanticMemory, Depends(get_semantic_memory)],
    skill_registry: Annotated[SkillRegistry, Depends(get_skill_registry)],
) -> ChatOrchestrator:
    """Wire a ChatOrchestrator for the current authenticated user.

    Args:
        llm: LLM adapter singleton.
        stt: STT adapter singleton.
        tts: Optional TTS adapter singleton.
        working_memory: User-scoped working memory.
        semantic_memory: User-scoped semantic memory.
        skill_registry: Registry of available skills for the current user.

    Returns:
        Fully wired ``ChatOrchestrator``.
    """
    return ChatOrchestrator(
        llm=llm,
        stt=stt,
        tts=tts,
        working_memory=working_memory,
        semantic_memory=semantic_memory,
        skill_registry=skill_registry,
    )
