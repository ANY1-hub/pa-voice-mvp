"""Unit tests for ChatOrchestrator.

Covers the full turn pipeline (STT/text → guardrails → memory → LLM → TTS)
plus validation errors and resilience when optional subsystems fail.
"""

from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import UUID

import pytest

from src.security.exceptions import InputValidationError
from src.services.llm.base import LLMResult
from src.services.orchestrator import (
    MAX_AUDIO_BYTES,
    SYSTEM_PROMPT,
    ChatOrchestrator,
    ChatResult,
    reply_language_instruction,
)
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
    assert result.path == "llm"
    assert result.language == "en"
    UUID(result.correlation_id)

    mock_llm.generate_response.assert_awaited_once()
    mock_tts.synthesize.assert_awaited_once_with("Hello from Jarvis.", language=ANY)
    assert result.stt_ms == 0.0
    assert result.tts_ms >= 0.0
    assert result.reply_ms >= 0.0
    assert result.duration_ms >= result.tts_ms
    assert result.status == "ok"
    assert result.error_type is None
    assert mock_working_memory.add.await_count == 2  # user + jarvis turn
    for call in mock_working_memory.add.await_args_list:
        assert call.kwargs["correlation_id"] == result.correlation_id


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
    assert result.stt_ms >= 0.0
    assert result.tts_ms >= 0.0


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
    assert result.status == "ok"
    assert result.error_type == "tts"


@pytest.mark.asyncio
async def test_empty_llm_response_gets_fallback(orchestrator, mock_llm):
    """Blank LLM output is replaced with a safe fallback string."""
    mock_llm.generate_response.return_value = "   "

    result = await orchestrator.process(text="Hello")

    assert result.response == "I am sorry, I could not generate a response."
    assert result.status == "error"
    assert result.error_type == "llm"


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
async def test_store_turn_injection_error_does_not_break_turn(
    orchestrator, mock_working_memory, mock_llm
):
    """Assistant text that trips the user blocklist must not become HTTP 400."""
    mock_llm.generate_response.return_value = "The nervous system: it is complex."
    mock_working_memory.add.side_effect = InputValidationError(
        "Potential prompt injection detected: 'system:'"
    )

    result = await orchestrator.process(text="Tell me about biology")

    assert result.response == "The nervous system: it is complex."


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

    result = await orch.process(text="note: buy milk", language="de")

    assert result.transcript == "note: buy milk"
    assert "saved the note" in result.response.lower() or "Got it" in result.response
    mock_registry.find_handler.assert_called_once()
    mock_skill.execute.assert_awaited_once()
    mock_llm.generate_response.assert_not_awaited()
    assert mock_working_memory.add.await_count == 2  # user + jarvis
    assert result.path == "skill"
    assert result.skill_name == "notes"
    assert result.language == "de"
    assert result.duration_ms >= 0.0


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
    assert result.path == "llm"
    assert result.skill_name is None
    assert result.duration_ms >= 0.0


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


@pytest.mark.asyncio
async def test_llm_result_tokens_are_recorded_on_the_turn(orchestrator, mock_llm):
    """OpenAI-style usage on LLMResult must land on ChatResult for the monitor."""
    mock_llm.generate_response.return_value = LLMResult(
        text="Hello from Jarvis.",
        prompt_tokens=12,
        completion_tokens=8,
    )

    result = await orchestrator.process(text="Hi")

    assert result.status == "ok"
    assert result.error_type is None
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8
    assert result.tokens == 20


@pytest.mark.asyncio
async def test_llm_failure_returns_friendly_fallback(orchestrator, mock_llm):
    """LLM exceptions must not 500 the turn – return a safe user-facing message."""
    mock_llm.generate_response.side_effect = RuntimeError("api down")

    result = await orchestrator.process(text="Hello")

    assert result.transcript == "Hello"
    assert "trouble generating a response" in result.response.lower()
    assert result.status == "error"
    assert result.error_type == "llm"


@pytest.mark.asyncio
async def test_skill_exception_falls_through_to_llm(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Unexpected skill crash must fall through to the normal LLM path."""
    skill = AsyncMock()
    skill.name = "notes"
    skill.can_handle.return_value = True
    skill.execute.side_effect = RuntimeError("skill exploded")
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

    result = await orch.process(text="note: buy milk")

    skill.execute.assert_awaited_once()
    mock_llm.generate_response.assert_awaited_once()
    assert result.response == "Hello from Jarvis."


@pytest.mark.asyncio
async def test_personal_utterance_writes_semantic_facts(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """A first-person preference must be stored in Semantic Memory after the reply."""
    mock_llm.generate_response.side_effect = [
        "I'll remember that you like espresso.",
        '{"facts":[{"content":"User likes espresso","entities":["espresso"]}]}',
    ]
    mock_semantic_memory.add_fact = AsyncMock()

    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )
    result = await orch.process(text="I like espresso")

    assert "espresso" in result.response.lower()
    mock_semantic_memory.add_fact.assert_awaited_once()
    kwargs = mock_semantic_memory.add_fact.await_args.kwargs
    assert kwargs["fact"] == "User likes espresso"
    assert kwargs["importance"] >= 0.7
    assert kwargs["language"] == "en"


@pytest.mark.asyncio
async def test_fact_extraction_failure_does_not_break_turn(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """A failed fact-extract call must not hide the assistant reply."""
    mock_llm.generate_response.side_effect = [
        "Nice to meet you, Tony.",
        RuntimeError("extract down"),
    ]

    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )
    result = await orch.process(text="My name is Tony")

    assert result.response == "Nice to meet you, Tony."
    mock_semantic_memory.add_fact.assert_not_awaited()


@pytest.mark.asyncio
async def test_semantic_add_fact_failure_does_not_break_turn(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """A Semantic Memory write error after extraction must not hide the reply."""
    mock_llm.generate_response.side_effect = [
        "Got it.",
        '{"facts":[{"content":"User likes tea","entities":["tea"]}]}',
    ]
    mock_semantic_memory.add_fact = AsyncMock(side_effect=RuntimeError("write down"))

    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )
    result = await orch.process(text="I like tea")

    assert result.response == "Got it."
    mock_semantic_memory.add_fact.assert_awaited()


@pytest.mark.asyncio
async def test_display_name_is_in_system_prompt(mock_llm, mock_tts):
    """When a preferred name is set, the system prompt must tell Jarvis to use it."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts, display_name="Jarvis-Tester")
    await orch.process(text="Hello")
    messages = mock_llm.generate_response.await_args.args[0]
    system = messages[0]["content"]
    assert "Jarvis-Tester" in system


def test_system_prompt_current_language_outranks_prior_commitments():
    """Standing language promises must not be treated as a binding rule."""
    assert "latest user message" in SYSTEM_PROMPT.lower()
    assert "not binding" in SYSTEM_PROMPT.lower()


def test_reply_language_instruction_follows_memory_block():
    """The current-turn language line must sit after untrusted working memory."""
    orch = ChatOrchestrator(llm=AsyncMock())
    lock = (
        "Recent conversation context:\n"
        "- Jarvis: Got it. I'll stick to English from now on."
    )
    messages = orch._build_messages(
        "Bitte antworte auf Deutsch.",
        lock,
        reply_language="de",
    )
    system = messages[0]["content"]
    assert system.index("Reply in German") > system.index("stick to English")
    assert "Ignore earlier conversation about which language" in system


@pytest.mark.asyncio
async def test_german_turn_overrides_working_memory_english_lock(
    orchestrator, mock_llm, mock_working_memory
):
    """A prior English commitment in WM must not keep the reply language English."""
    lock = MagicMock()
    lock.content = "Jarvis: Got it. I'll stick to English from now on."
    mock_working_memory.retrieve.return_value = [lock]

    await orchestrator.process(text="Bitte antworte auf Deutsch. Wie geht es dir?")

    messages = mock_llm.generate_response.await_args.args[0]
    system = messages[0]["content"]
    assert "stick to English" in system
    assert system.index("Reply in German") > system.index("stick to English")
    assert reply_language_instruction("de") in system


@pytest.mark.asyncio
async def test_hungarian_turn_overrides_working_memory_english_lock(
    orchestrator, mock_llm, mock_working_memory
):
    """Hungarian utterances must request Hungarian even after an English WM promise."""
    lock = MagicMock()
    lock.content = "Jarvis: I'll stick to English from now on."
    mock_working_memory.retrieve.return_value = [lock]

    await orchestrator.process(text="Nem tudom, hogy mi van")

    messages = mock_llm.generate_response.await_args.args[0]
    system = messages[0]["content"]
    assert system.index("Reply in Hungarian") > system.index("stick to English")
    assert reply_language_instruction("hu") in system


@pytest.mark.asyncio
async def test_auto_detect_german_text_requests_german_reply(orchestrator, mock_llm):
    """With no forced language, German function words must request a German reply."""
    await orchestrator.process(text="Wie geht es dir?")
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("de") in system


@pytest.mark.asyncio
async def test_forced_english_overrides_german_utterance(orchestrator, mock_llm):
    """A forced chat language must pin the LLM even if the user wrote German."""
    await orchestrator.process(text="Wie geht es dir?", language="en")
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("en") in system


@pytest.mark.asyncio
async def test_notes_skill_works_without_llm():
    """Notes must handle a turn when no LLM adapter is wired."""
    from src.skills.notes.repository import NoteRepository
    from src.skills.notes.skill import NotesSkill
    from src.skills.registry import SkillRegistry

    repo = NoteRepository(user_id="u1", collection=None)
    registry = SkillRegistry()
    registry.register(NotesSkill(repository=repo))
    orch = ChatOrchestrator(llm=None, skill_registry=registry)

    result = await orch.process(text="take a note buy milk")

    assert result.path == "skill"
    assert result.skill_name == "notes"
    assert "milk" in result.response.lower()


@pytest.mark.asyncio
async def test_llm_path_without_adapter_is_friendly():
    """Missing LLM adapter must not raise; return the same friendly fallback."""
    orch = ChatOrchestrator(llm=None)
    result = await orch.process(text="Hello there how are you")
    assert result.path == "llm"
    assert "trouble generating a response" in result.response.lower()
