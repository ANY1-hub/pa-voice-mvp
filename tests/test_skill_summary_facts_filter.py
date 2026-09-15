"""Slice-Brief 9: skill-summary SM facts must not enter personal-fact surfaces.

Explicit ActiveRecall and Orchestrator ``Relevant personal facts`` must omit
Semantic Memory lines that are Reminder/Notes skill writebacks:
- ``User set a reminder:``
- ``User saved a note:``
- ``User saved a note titled``

Real personal facts (allergy, prefs, …) and display_name address remain.
Reminder/Notes keep writing those summaries (not tested here).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.memory import SemanticMemoryFact
from src.services.orchestrator import ChatOrchestrator
from src.skills.active_recall.skill import ActiveRecallSkill

_NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
USER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

_REMINDER_SUMMARY = "User set a reminder: stretch in two minutes"
_NOTE_SUMMARY = "User saved a note: grocery list for weekend"
_NOTE_TITLED_SUMMARY = "User saved a note titled 'Taxes': call accountant Monday"
_PERSONAL = "User is allergic to hazelnuts."
_PREF = "User likes oat milk."


def _fact(content: str) -> SemanticMemoryFact:
    return SemanticMemoryFact(
        user_id=USER,
        content=content,
        importance_score=0.7,
        entities_involved=[],
        created_at=_NOW,
        last_accessed=_NOW,
    )


def _ar(facts: list[SemanticMemoryFact]) -> ActiveRecallSkill:
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=facts)
    return ActiveRecallSkill(semantic_memory=mock_sem)


def _orch(facts: list[SemanticMemoryFact]) -> ChatOrchestrator:
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = "ok"
    mock_sem = AsyncMock()
    mock_sem.search = AsyncMock(return_value=facts)
    mock_wm = AsyncMock()
    mock_wm.retrieve = AsyncMock(return_value=[])
    return ChatOrchestrator(
        llm=mock_llm,
        stt=None,
        tts=None,
        working_memory=mock_wm,
        semantic_memory=mock_sem,
    )


# ---------------------------------------------------------------------------
# ActiveRecall
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_recall_about_you_omits_reminder_and_note_summaries():
    """About-you recall lists personal facts, not skill-summary SM lines."""
    skill = _ar(
        [
            _fact(_REMINDER_SUMMARY),
            _fact(_NOTE_SUMMARY),
            _fact(_NOTE_TITLED_SUMMARY),
            _fact(_PERSONAL),
            _fact(_PREF),
        ]
    )
    result = await skill.execute(
        user_text="What do you know about me?",
        user_id=USER,
        display_name="Ákosh",
        language="en",
    )
    text = result.response_text
    assert result.handled is True
    assert "hazelnut" in text.casefold()
    assert "oat milk" in text.casefold()
    assert "Ákosh" in text
    assert "user set a reminder:" not in text.casefold()
    assert "user saved a note:" not in text.casefold()
    assert "user saved a note titled" not in text.casefold()


@pytest.mark.asyncio
async def test_active_recall_topic_omits_skill_summaries_keeps_personal():
    """Topic recall keeps real facts; skill summaries stay out of the bullets."""
    skill = _ar(
        [
            _fact(_REMINDER_SUMMARY),
            _fact(_NOTE_SUMMARY),
            _fact(_PERSONAL),
        ]
    )
    result = await skill.execute(
        user_text="What do you know about my allergies?",
        user_id=USER,
        display_name="Ákosh",
        language="en",
    )
    text = result.response_text.casefold()
    assert "hazelnut" in text
    assert "user set a reminder:" not in text
    assert "user saved a note:" not in text


@pytest.mark.asyncio
async def test_active_recall_only_skill_summaries_is_honest_empty_control():
    """Control twin: only reminder/note summaries → honest empty, not a dump."""
    skill = _ar(
        [
            _fact(_REMINDER_SUMMARY),
            _fact(_NOTE_SUMMARY),
            _fact(_NOTE_TITLED_SUMMARY),
        ]
    )
    result = await skill.execute(
        user_text="What do you know about me?",
        user_id=USER,
        display_name=None,
        language="en",
    )
    text = result.response_text.casefold()
    assert "user set a reminder:" not in text
    assert "user saved a note:" not in text
    assert "user saved a note titled" not in text
    assert "personal facts stored yet" in text or "don't have" in text


@pytest.mark.asyncio
async def test_name_recall_still_display_name_only_control():
    """Control twin: name questions stay display_name-only (no SM dump)."""
    skill = _ar(
        [
            _fact(_REMINDER_SUMMARY),
            _fact("User's name is Tony."),
            _fact(_PERSONAL),
        ]
    )
    result = await skill.execute(
        user_text="What is my name?",
        user_id=USER,
        display_name="Ákosh",
        language="en",
    )
    assert "Ákosh" in result.response_text
    assert "tony" not in result.response_text.casefold()
    assert "user set a reminder:" not in result.response_text.casefold()


# ---------------------------------------------------------------------------
# Orchestrator LLM context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_relevant_personal_facts_omits_skill_summaries():
    """SM→Relevant personal facts must drop reminder/note writeback prefixes."""
    orch = _orch(
        [
            _fact(_REMINDER_SUMMARY),
            _fact(_NOTE_SUMMARY),
            _fact(_NOTE_TITLED_SUMMARY),
            _fact(_PERSONAL),
        ]
    )
    context, _history = await orch._build_memory_context("allergies")
    lower = context.casefold()
    assert "relevant personal facts" in lower
    assert "hazelnut" in lower
    assert "user set a reminder:" not in lower
    assert "user saved a note:" not in lower
    assert "user saved a note titled" not in lower


@pytest.mark.asyncio
async def test_orchestrator_only_skill_summaries_yields_no_personal_facts_block():
    """Control twin: only skill summaries → no Relevant personal facts dump."""
    orch = _orch(
        [
            _fact(_REMINDER_SUMMARY),
            _fact(_NOTE_TITLED_SUMMARY),
        ]
    )
    context, _history = await orch._build_memory_context("reminders")
    lower = context.casefold()
    assert "user set a reminder:" not in lower
    assert "user saved a note titled" not in lower
    assert "relevant personal facts" not in lower
