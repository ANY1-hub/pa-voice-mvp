"""Walk-regression: reply language + Piper follow this user utterance."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.orchestrator import ChatOrchestrator, reply_language_instruction
from src.skills.base import SkillResult
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill, fire_speech
from src.skills.replies import reply_language


def _registry() -> SkillRegistry:
    """Production registration order with in-memory skill stores."""
    registry = SkillRegistry()
    registry.register(NotesSkill(repository=NoteRepository(user_id="u1")))
    registry.register(RemindersSkill(repository=ReminderRepository(user_id="u1")))
    return registry


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate_response.return_value = "Hello from Jarvis."
    return llm


@pytest.fixture
def mock_tts():
    tts = AsyncMock()
    tts.synthesize.return_value = b"fake-wav-bytes"
    return tts


@pytest.mark.asyncio
async def test_german_utterance_keeps_german_piper_when_llm_replies_english(
    mock_llm, mock_tts
):
    """DE in must stay DE Piper even if the model answers in English."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(text="Wie geht es dir?")

    assert result.language == "de"
    mock_tts.synthesize.assert_awaited_once_with("Hello from Jarvis.", language="de")
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("de") in system


@pytest.mark.asyncio
async def test_german_w_question_without_ich_keeps_german_reply_language(
    mock_llm, mock_tts
):
    """DE 'Woher hast Du …' must not default to English (no ß/ich/und)."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(text="Woher hast Du diese Information?")

    assert result.language == "de"
    mock_tts.synthesize.assert_awaited_once_with("Hello from Jarvis.", language="de")
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("de") in system


@pytest.mark.asyncio
async def test_english_story_uses_english_piper_despite_hungarian_stt_hint(
    mock_llm, mock_tts
):
    """EN story + stale HU Whisper hint must not pick the Hungarian voice."""
    mock_llm.generate_response.return_value = (
        "Once upon a time Leipzig stood on a river."
    )
    stt = AsyncMock()
    stt.transcribe.return_value = (
        "Tell me a short story about Leipzig",
        "hu",
    )
    orch = ChatOrchestrator(llm=mock_llm, stt=stt, tts=mock_tts)

    result = await orch.process(audio_bytes=b"fake-audio")

    assert result.transcript == "Tell me a short story about Leipzig"
    assert result.path == "llm"
    assert result.language == "en"
    mock_tts.synthesize.assert_awaited_once_with(
        "Once upon a time Leipzig stood on a river.", language="en"
    )
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("en") in system


@pytest.mark.asyncio
async def test_hungarian_agenda_reply_and_piper_follow_utterance(mock_llm, mock_tts):
    """HU 'Mi van ma?' must yield HU agenda text and HU Piper, not English."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts, skill_registry=_registry())

    result = await orch.process(text="Mi van ma?")

    assert result.path == "skill"
    assert result.skill_name == "reminders"
    assert result.language == "hu"
    assert "Ebben az időszakban nincs semmi." in result.response
    assert "Nothing scheduled" not in result.response
    mock_tts.synthesize.assert_awaited_once_with(result.response, language="hu")
    mock_llm.generate_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_english_smalltalk_after_hungarian_agenda_is_english_not_agenda(
    mock_llm, mock_tts
):
    """EN 'how are you today?' after a HU agenda turn is smalltalk, EN Piper."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts, skill_registry=_registry())

    first = await orch.process(text="Mi van ma?")
    assert first.path == "skill"
    assert first.language == "hu"

    mock_tts.reset_mock()
    second = await orch.process(text="how are you today?")

    assert second.path == "llm"
    assert second.language == "en"
    mock_tts.synthesize.assert_awaited_once_with("Hello from Jarvis.", language="en")
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("en") in system


@pytest.mark.asyncio
async def test_german_note_after_english_story_is_german_reply_and_piper(
    mock_llm, mock_tts
):
    """EN story then DE note request must not keep English skill text or Piper."""
    mock_llm.generate_response.return_value = (
        "Once upon a time Leipzig stood on a river."
    )
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts, skill_registry=_registry())

    story = await orch.process(text="Tell me a short story about Leipzig")
    assert story.path == "llm"
    assert story.language == "en"

    mock_tts.reset_mock()
    note = await orch.process(text="Notiz: kaufe Milch")

    assert note.path == "skill"
    assert note.skill_name == "notes"
    assert note.language == "de"
    assert "Gespeichert" in note.response or "gespeichert" in note.response.lower()
    assert "Got it" not in note.response
    mock_tts.synthesize.assert_awaited_once_with(note.response, language="de")


@pytest.mark.asyncio
async def test_english_reminder_with_akos_stays_english_including_due_tts():
    """Listed HU name in an EN reminder must not flip confirm or due speech to HU."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="Remind me in two minutes to stretch, Ákos",
            user_id="u1",
            language="hu",
            display_name="Ákosh",
        )

    assert result.handled is True
    assert "I'll remind you" in result.response_text
    assert "Emlékeztetlek" not in result.response_text
    assert spy.await_args.kwargs["language"] == "en"
    assert fire_speech("stretch", spy.await_args.kwargs["language"]).startswith(
        "Reminder:"
    )


@pytest.mark.asyncio
async def test_english_skill_string_does_not_retarget_piper_away_from_german(
    mock_llm, mock_tts
):
    """Piper follows the utterance, not a mismatched English skill string."""
    skill = AsyncMock()
    skill.name = "notes"
    skill.can_handle.return_value = True
    skill.execute.return_value = SkillResult(
        response_text="Got it. I saved the note: buy milk",
        handled=True,
    )
    registry = MagicMock()
    registry.find_handler.return_value = skill
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts, skill_registry=registry)

    result = await orch.process(text="Notiz: kaufe Milch")

    assert result.path == "skill"
    assert result.language == "de"
    mock_tts.synthesize.assert_awaited_once_with(
        "Got it. I saved the note: buy milk", language="de"
    )
    skill.execute.assert_awaited_once()
    assert skill.execute.await_args.kwargs["language"] == "de"


def test_reply_language_strips_display_name_before_guessing():
    """Skill replies must ignore display-name accents, same as Piper."""
    assert (
        reply_language(
            "Got it, Áxel, I'll stay in English.",
            {"language": "en", "display_name": "Áxel"},
        )
        == "en"
    )
