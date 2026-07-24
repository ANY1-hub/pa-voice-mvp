"""Chat routes – text and voice entry points for the orchestrator."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user, get_orchestrator
from src.models.user import User
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
    """JSON body for pure text chat."""

    text: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Unified response for both text and voice turns."""

    transcript: str
    response: str
    audio_base64: str | None = None


@router.post("/text", response_model=ChatResponse)
async def chat_text(
    body: TextChatRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),  # noqa: B008
) -> ChatResponse:
    """Process a text message (fallback when voice is not used)."""
    try:
        result = await orchestrator.process(text=body.text)
        return ChatResponse(
            transcript=result.transcript,
            response=result.response,
            audio_base64=result.audio_base64,
        )
    except InputValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {e.__class__.__name__}",
        ) from e


@router.post("/voice", response_model=ChatResponse)
async def chat_voice(
    audio: UploadFile = File(..., description="Audio file (wav, webm, …)"),  # noqa: B008
    language: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),  # noqa: B008
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),  # noqa: B008
) -> ChatResponse:
    """Process a voice message: STT → Memory → LLM → TTS."""
    # Content-Type check (lenient but not completely open)
    content_type = (audio.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {content_type}",
        )

    # Size check before fully loading into memory if possible
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice chat failed: {e.__class__.__name__}",
        ) from e
