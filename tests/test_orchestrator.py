"""Unit tests for ChatOrchestrator.

Covers the full turn pipeline (STT/text → guardrails → memory → LLM → TTS)
plus validation errors and resilience when optional subsystems fail.
"""

from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from src.services.orchestrator import MAX_AUDIO_BYTES, ChatOrchestrator, ChatResult
from src.skills.base import SkillResult


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
    """Text turn: LLM + TTS + two Working Memory writes (user + assistant)."""
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
    """Voice turn: STT language hint is forwarded to STT and TTS."""
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
    """Reject calls that provide neither text nor audio."""
    with pytest.raises(ValueError, match="Either text or audio_bytes"):
        await orchestrator.process()


@pytest.mark.asyncio
async def test_process_rejects_both_text_and_audio(orchestrator):
    """Reject calls that provide both text and audio (ambiguous input)."""
    with pytest.raises(ValueError, match="not both"):
        await orchestrator.process(text="hi", audio_bytes=b"audio")


@pytest.mark.asyncio
async def test_process_rejects_oversized_audio(orchestrator):
    """Protect host resources: reject audio above MAX_AUDIO_BYTES."""
    huge = b"x" * (MAX_AUDIO_BYTES + 1)
    with pytest.raises(ValueError, match="Audio too large"):
        await orchestrator.process(audio_bytes=huge)


@pytest.mark.asyncio
async def test_process_empty_transcript_raises(orchestrator, mock_stt):
    """Empty STT output is treated as a client/input error."""
    mock_stt.transcribe.return_value = "   "
    with pytest.raises(ValueError, match="Could not transcribe"):
        await orchestrator.process(audio_bytes=b"some-audio")


@pytest.mark.asyncio
async def test_process_no_stt_configured_raises(mock_llm):
    """Voice turns require an STT adapter."""
    orch = ChatOrchestrator(llm=mock_llm, stt=None)
    with pytest.raises(RuntimeError, match="STT adapter is not configured"):
        await orch.process(audio_bytes=b"audio")


# ---------------------------------------------------------------------------
# Resilience / edge cases
# Optional subsystems must not take down the whole turn.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tts_failure_does_not_break_turn(orchestrator, mock_tts):
    """TTS exceptions are swallowed; reply text is still returned."""
    mock_tts.synthesize.side_effect = RuntimeError("piper crashed")

    result = await orchestrator.process(text="Still works")

    assert result.transcript == "Still works"
    assert result.response == "Hello from Jarvis."
    assert result.audio_base64 is None


@pytest.mark.asyncio
async def test_empty_llm_response_gets_fallback(orchestrator, mock_llm):
    """Blank LLM output is replaced with a safe fallback string."""
    mock_llm.generate_response.return_value = "   "

    result = await orchestrator.process(text="Hello")

    assert result.response == "I am sorry, I could not generate a response."


@pytest.mark.asyncio
async def test_working_memory_retrieve_failure_does_not_break_turn(
    orchestrator, mock_working_memory
):
    """Working-memory read errors are logged and ignored."""
    mock_working_memory.retrieve.side_effect = RuntimeError("mongo down")

    result = await orchestrator.process(text="Continue please")

    assert result.transcript == "Continue please"
    assert result.response == "Hello from Jarvis."


@pytest.mark.asyncio
async def test_semantic_memory_search_failure_does_not_break_turn(
    orchestrator, mock_semantic_memory
):
    """Semantic-memory search errors are logged and ignored."""
    mock_semantic_memory.search.side_effect = RuntimeError("search failed")

    result = await orchestrator.process(text="Continue please")

    assert result.response == "Hello from Jarvis."


@pytest.mark.asyncio
async def test_store_turn_failure_does_not_break_turn(
    orchestrator, mock_working_memory
):
    """Failing to persist the turn must not fail the user-visible response."""
    mock_working_memory.add.side_effect = RuntimeError("write failed")

    result = await orchestrator.process(text="Still ok")

    assert result.transcript == "Still ok"
    assert result.response == "Hello from Jarvis."


@pytest.mark.asyncio
async def test_no_tts_adapter_returns_no_audio(mock_llm):
    """When no TTS adapter is wired, audio_base64 stays None."""
    orch = ChatOrchestrator(llm=mock_llm, tts=None)
    result = await orch.process(text="Hi")
    assert result.audio_base64 is None


@pytest.mark.asyncio
async def test_tts_empty_bytes_returns_no_audio(orchestrator, mock_tts):
    """Empty synthesis output is treated as 'no audio', not an error."""
    mock_tts.synthesize.return_value = b""
    result = await orchestrator.process(text="Hi")
    assert result.audio_base64 is None


# ---------------------------------------------------------------------------
# Skill routing
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_skill():
    skill = AsyncMock()
    skill.name = "notes"
    skill.can_handle.return_value = True
    skill.execute.return_value = SkillResult(
        response_text="Got it. I saved the note: buy milk",
        handled=True,
    )
    return skill


@pytest.fixture
def mock_registry(mock_skill):
    registry = MagicMock()
    registry.find_handler.return_value = mock_skill
    return registry


@pytest.mark.asyncio
async def test_skill_handles_turn_skips_llm(
    mock_llm,
    mock_tts,
    mock_working_memory,
    mock_semantic_memory,
    mock_registry,
    mock_skill,
):
    """When a skill claims the turn, LLM is never called."""
    mock_working_memory.user_id = "u-test"
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
        skill_registry=mock_registry,
    )

    result = await orch.process(text="note: buy milk")

    assert result.transcript == "note: buy milk"
    assert "saved the note" in result.response.lower() or "Got it" in result.response
    mock_registry.find_handler.assert_called_once()
    mock_skill.execute.assert_awaited_once()
    mock_llm.generate_response.assert_not_awaited()
    assert mock_working_memory.add.await_count == 2  # user + jarvis


@pytest.mark.asyncio
async def test_no_skill_match_uses_llm(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """When no skill matches, the normal LLM path runs."""
    registry = MagicMock()
    registry.find_handler.return_value = None

    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
        skill_registry=registry,
    )

    result = await orch.process(text="How is the weather?")

    assert result.response == "Hello from Jarvis."
    registry.find_handler.assert_called_once()
    mock_llm.generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_skill_handled_false_falls_through_to_llm(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Skill that returns handled=False does not short-circuit the turn."""
    skill = AsyncMock()
    skill.can_handle.return_value = True
    skill.execute.return_value = SkillResult(
        response_text="partial",
        handled=False,
    )
    registry = MagicMock()
    registry.find_handler.return_value = skill
    mock_working_memory.user_id = "u-test"

    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
        skill_registry=registry,
    )

    result = await orch.process(text="note: something")

    skill.execute.assert_awaited_once()
    mock_llm.generate_response.assert_awaited_once()
    assert result.response == "Hello from Jarvis."
