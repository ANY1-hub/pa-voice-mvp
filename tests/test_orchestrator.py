"""Unit tests for ChatOrchestrator."""

from unittest.mock import ANY, AsyncMock

import pytest

from src.services.orchestrator import MAX_AUDIO_BYTES, ChatOrchestrator, ChatResult


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate_response.return_value = "Hello from Jarvis."
    return llm


@pytest.fixture
def mock_stt():
    stt = AsyncMock()
    stt.transcribe.return_value = "Hello world"
    return stt


@pytest.fixture
def mock_tts():
    tts = AsyncMock()
    tts.synthesize.return_value = b"fake-wav-bytes"
    return tts


@pytest.fixture
def mock_working_memory():
    wm = AsyncMock()
    wm.retrieve.return_value = []
    wm.add.return_value = None
    return wm


@pytest.fixture
def mock_semantic_memory():
    sm = AsyncMock()
    sm.search.return_value = []
    return sm


@pytest.fixture
def orchestrator(
    mock_llm, mock_stt, mock_tts, mock_working_memory, mock_semantic_memory
):
    return ChatOrchestrator(
        llm=mock_llm,
        stt=mock_stt,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_text_happy_path(
    orchestrator, mock_llm, mock_tts, mock_working_memory
):
    result = await orchestrator.process(text="Hi there")

    assert isinstance(result, ChatResult)
    assert result.transcript == "Hi there"
    assert result.response == "Hello from Jarvis."
    assert result.audio_base64 is not None  # base64 of fake-wav-bytes

    mock_llm.generate_response.assert_awaited_once()
    mock_tts.synthesize.assert_awaited_once_with("Hello from Jarvis.", language=ANY)
    assert mock_working_memory.add.await_count == 2  # user + jarvis turn


@pytest.mark.asyncio
async def test_process_voice_happy_path(orchestrator, mock_stt, mock_llm, mock_tts):
    audio = b"fake-audio-bytes"
    result = await orchestrator.process(audio_bytes=audio, language="de")

    assert result.transcript == "Hello world"
    assert result.response == "Hello from Jarvis."

    mock_stt.transcribe.assert_awaited_once_with(audio, language="de")
    mock_llm.generate_response.assert_awaited_once()
    mock_tts.synthesize.assert_awaited_once_with("Hello from Jarvis.", language="de")


# ---------------------------------------------------------------------------
# Validation / error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_requires_text_or_audio(orchestrator):
    with pytest.raises(ValueError, match="Either text or audio_bytes"):
        await orchestrator.process()


@pytest.mark.asyncio
async def test_process_rejects_both_text_and_audio(orchestrator):
    with pytest.raises(ValueError, match="not both"):
        await orchestrator.process(text="hi", audio_bytes=b"audio")


@pytest.mark.asyncio
async def test_process_rejects_oversized_audio(orchestrator):
    huge = b"x" * (MAX_AUDIO_BYTES + 1)
    with pytest.raises(ValueError, match="Audio too large"):
        await orchestrator.process(audio_bytes=huge)


@pytest.mark.asyncio
async def test_process_empty_transcript_raises(orchestrator, mock_stt):
    mock_stt.transcribe.return_value = "   "
    with pytest.raises(ValueError, match="Could not transcribe"):
        await orchestrator.process(audio_bytes=b"some-audio")


@pytest.mark.asyncio
async def test_process_no_stt_configured_raises(mock_llm):
    orch = ChatOrchestrator(llm=mock_llm, stt=None)
    with pytest.raises(RuntimeError, match="STT adapter is not configured"):
        await orch.process(audio_bytes=b"audio")


# ---------------------------------------------------------------------------
# Resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_failure_does_not_break_turn(orchestrator, mock_tts):
    mock_tts.synthesize.side_effect = RuntimeError("piper crashed")

    result = await orchestrator.process(text="Still works")

    assert result.transcript == "Still works"
    assert result.response == "Hello from Jarvis."
    assert result.audio_base64 is None  # TTS failed → no audio, but turn succeeds


@pytest.mark.asyncio
async def test_empty_llm_response_gets_fallback(orchestrator, mock_llm):
    mock_llm.generate_response.return_value = "   "

    result = await orchestrator.process(text="Hello")

    assert result.response == "I am sorry, I could not generate a response."
