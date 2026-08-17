"""Chat routes – text and voice entry points for the orchestrator."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.deps import get_orchestrator
from src.security.exceptions import InputValidationError
from src.services.orchestrator import MAX_AUDIO_BYTES, ChatOrchestrator

router = APIRouter()

# Content types we accept for voice uploads (browsers vary).
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/flac",
    "application/octet-stream",  # some browsers omit a proper type
}


class TextChatRequest(BaseModel):
    """JSON body for pure text chat.

    Attributes:
        text: User message (1–4000 characters).
    """

    text: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Unified response for both text and voice turns.

    Attributes:
        transcript: Sanitized user utterance.
        response: LLM reply text.
        audio_base64: Optional base64-encoded TTS audio.
    """

    transcript: str
    response: str
    audio_base64: str | None = None


@router.post("/text", response_model=ChatResponse)
async def chat_text(
    body: TextChatRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_orchestrator)],
) -> ChatResponse:
    """Process a text message (fallback when voice is not used).

    JWT is enforced via the orchestrator dependency chain
    (WorkingMemory → current user).

    Args:
        body: JSON body with the user text.
        orchestrator: Injected chat orchestrator for the current user.

    Returns:
        ChatResponse with transcript, reply and optional audio.
    """
    try:
        result = await orchestrator.process(text=body.text)
        return ChatResponse(
            transcript=result.transcript,
            response=result.response,
            audio_base64=result.audio_base64,
        )
    except InputValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong on my side. Please try again.",
        ) from None  # prevents original exception to land in the Response-chain


@router.post("/voice", response_model=ChatResponse)
async def chat_voice(
    audio: Annotated[UploadFile, File(description="Audio file (wav, webm, …)")],
    orchestrator: Annotated[ChatOrchestrator, Depends(get_orchestrator)],
    language: Annotated[str | None, Form()] = None,
) -> ChatResponse:
    """Process a voice message: STT → Memory → LLM → TTS.

    JWT is enforced via the orchestrator dependency chain
    (WorkingMemory → current user).

    Args:
        audio: Uploaded audio file (wav, webm, …).
        orchestrator: Injected chat orchestrator for the current user.
        language: Optional STT language code (e.g. ``"de"``, ``"en"``, ``"hu"``).

    Returns:
        ChatResponse with transcript, reply and optional audio.
    """
    # Content-Type check (lenient but not completely open)
    content_type = (audio.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {content_type}",
        )

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio exceeds limit of {MAX_AUDIO_BYTES // (1024 * 1024)} MB",
        )

    try:
        result = await orchestrator.process(
            audio_bytes=audio_bytes,
            language=language,
        )
        return ChatResponse(
            transcript=result.transcript,
            response=result.response,
            audio_base64=result.audio_base64,
        )
    except InputValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong on my side. Please try again.",
        ) from None  # prevents original exception to land in the Response-chain
