"""Slice-Brief 2: STT garbage / weak signal falls back to GUI language.

When the utterance has no clear EN/DE/HU signal (e.g. Whisper junk
\"Zachmien wid!\"), reply text + TTS must follow the GUI language
(``gui_language`` from the frontend Help flags / getLang), not a hard
English default. Clear short EN/DE/HU utterances still follow the
utterance. Forced chat ``language`` still overrides both.

Mutation: hard-coding ``en`` on weak text, or wiring ``gui_language`` as
forced chat language, must go red against the control twins.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_orchestrator
from src.main import app
from src.services.orchestrator import (
    ChatOrchestrator,
    ChatResult,
    reply_language_instruction,
)
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill

# Live debt sample from the language re-walk (case 6 Speak MIXED).
_STT_GARBAGE = "Zachmien wid!"


def _registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(NotesSkill(repository=NoteRepository(user_id="u1")))
    registry.register(RemindersSkill(repository=ReminderRepository(user_id="u1")))
    return registry


def _tts_language(mock_tts: AsyncMock) -> str | None:
    call = mock_tts.synthesize.await_args
    if call is None:
        return None
    if "language" in call.kwargs:
        return call.kwargs["language"]
    if len(call.args) >= 2:
        return call.args[1]
    return None


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


# ---------------------------------------------------------------------------
# Orchestrator: garbage → GUI; clear utterance → utterance; forced wins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gui_lang", ["de", "hu", "en"])
@pytest.mark.asyncio
async def test_stt_garbage_falls_back_to_gui_language(
    mock_llm, mock_tts, gui_lang: str
):
    """STT garbage with no clear EN/DE/HU signal must use gui_language for reply+TTS."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(text=_STT_GARBAGE, gui_language=gui_lang)

    assert result.language == gui_lang
    assert _tts_language(mock_tts) == gui_lang
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction(gui_lang) in system


@pytest.mark.asyncio
async def test_voice_stt_garbage_falls_back_to_gui_language(mock_llm, mock_tts):
    """Voice path: junk transcript + gui_language=de must not pin English Piper."""
    stt = AsyncMock()
    stt.transcribe.return_value = (_STT_GARBAGE, "en")
    orch = ChatOrchestrator(llm=mock_llm, stt=stt, tts=mock_tts)

    result = await orch.process(audio_bytes=b"fake-audio", gui_language="de")

    assert result.transcript == _STT_GARBAGE
    assert result.language == "de"
    assert _tts_language(mock_tts) == "de"


@pytest.mark.asyncio
async def test_garbage_without_gui_language_defaults_to_en(mock_llm, mock_tts):
    """If GUI lang is missing, weak/garbage text still defaults to English."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(text=_STT_GARBAGE)

    assert result.language == "en"
    assert _tts_language(mock_tts) == "en"


@pytest.mark.parametrize(
    "utterance,expected",
    [
        ("Wie geht es dir?", "de"),
        ("Notiz: kaufe Milch", "de"),
        ("Mi van ma?", "hu"),
        ("Hello, how are you today?", "en"),
        ("Tell me a short story about Leipzig", "en"),
    ],
)
@pytest.mark.asyncio
async def test_clear_utterance_beats_gui_language(
    mock_llm, mock_tts, utterance: str, expected: str
):
    """Clear short EN/DE/HU must follow the utterance, not a conflicting GUI lang."""
    conflicting = {"de": "en", "hu": "de", "en": "de"}[expected]
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts, skill_registry=_registry())
    result = await orch.process(text=utterance, gui_language=conflicting)

    assert result.language == expected
    assert _tts_language(mock_tts) == expected


@pytest.mark.asyncio
async def test_forced_chat_language_beats_gui_and_garbage(mock_llm, mock_tts):
    """Forced ``language`` must pin the turn even when GUI disagrees and text is junk."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(text=_STT_GARBAGE, language="en", gui_language="de")

    assert result.language == "en"
    assert _tts_language(mock_tts) == "en"
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("en") in system


@pytest.mark.asyncio
async def test_forced_chat_language_beats_gui_on_clear_german(mock_llm, mock_tts):
    """Forced English must still override a clear German utterance (existing contract)."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(
        text="Wie geht es dir?", language="en", gui_language="de"
    )

    assert result.language == "en"
    system = mock_llm.generate_response.await_args.args[0][0]["content"]
    assert reply_language_instruction("en") in system


@pytest.mark.asyncio
async def test_gui_language_is_not_forced_chat_language(mock_llm, mock_tts):
    """gui_language alone must not force DE when the utterance is clearly English."""
    orch = ChatOrchestrator(llm=mock_llm, tts=mock_tts)
    result = await orch.process(
        text="Tell me a short story about Leipzig", gui_language="de"
    )

    assert result.language == "en"
    assert _tts_language(mock_tts) == "en"


# ---------------------------------------------------------------------------
# HTTP: gui_language forwarded; validated to en/de/hu; distinct from language
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    orch.process.return_value = ChatResult(
        transcript="User said this",
        response="Jarvis reply",
        audio_base64="ZmFrZS1hdWRpbw==",
        language="de",
    )
    return orch


@pytest.fixture
def client_with_mock_orch(mock_orchestrator, auth_headers):
    """Register via auth_headers first (wipe), then override orchestrator."""
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_chat_text_forwards_gui_language(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    """Optional gui_language on /chat/text must be passed to process(), not as language."""
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": _STT_GARBAGE, "gui_language": "de"},
    )
    assert res.status_code == 200
    call_kwargs = mock_orchestrator.process.await_args.kwargs
    assert call_kwargs["text"] == _STT_GARBAGE
    assert call_kwargs.get("gui_language") == "de"
    assert call_kwargs.get("language") in (None,)


def test_chat_text_forwards_forced_and_gui_separately(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    """Forced language and gui_language are distinct fields on the same request."""
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": "Hallo", "language": "en", "gui_language": "de"},
    )
    assert res.status_code == 200
    call_kwargs = mock_orchestrator.process.await_args.kwargs
    assert call_kwargs["language"] == "en"
    assert call_kwargs["gui_language"] == "de"


@pytest.mark.parametrize("bad", ["fr", "xx", "english", "DE-DE", ""])
def test_chat_text_rejects_invalid_gui_language(
    client_with_mock_orch, auth_headers, bad: str
):
    """gui_language must validate to en/de/hu only (untrusted client field)."""
    res = client_with_mock_orch.post(
        "/api/v1/chat/text",
        headers=auth_headers,
        json={"text": "Hello", "gui_language": bad},
    )
    assert res.status_code == 422


def test_chat_voice_forwards_gui_language(
    client_with_mock_orch, auth_headers, mock_orchestrator
):
    """Optional gui_language form field on /chat/voice must reach process()."""
    files = {"audio": ("recording.wav", b"fake-wav-content", "audio/wav")}
    res = client_with_mock_orch.post(
        "/api/v1/chat/voice",
        headers=auth_headers,
        files=files,
        data={"gui_language": "hu"},
    )
    assert res.status_code == 200
    call_kwargs = mock_orchestrator.process.await_args.kwargs
    assert call_kwargs["audio_bytes"] == b"fake-wav-content"
    assert call_kwargs.get("gui_language") == "hu"
