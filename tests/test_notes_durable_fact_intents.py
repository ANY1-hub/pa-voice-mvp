"""Slice-Brief 11: durable personal-fact intents must create Notes.

HU „jegyezd meg…“ and DE „erinnere dich dass…“ (and EN „remember that I…“)
must route to NotesSkill and persist a note — not fall through to LLM-only
chat memory. Reminder due intents must stay RemindersSkill.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill


def _registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(NotesSkill(repository=NoteRepository(user_id="u1")))
    reg.register(RemindersSkill(repository=ReminderRepository(user_id="u1")))
    return reg


@pytest.mark.parametrize(
    "utterance",
    [
        "jegyezd meg, hogy allergiás vagyok a mogyoróra",
        "erinnere dich dass ich allergisch gegen Haselnüsse bin",
        "remember that I am allergic to hazelnuts",
    ],
)
def test_durable_personal_fact_intent_selects_notes(utterance: str):
    """Personal-fact remember phrases must resolve to the notes skill."""
    handler = _registry().find_handler(utterance)
    assert handler is not None, f"no skill claimed {utterance!r}"
    assert handler.name == "notes"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "utterance,needle",
    [
        ("jegyezd meg, hogy allergiás vagyok a mogyoróra", "allerg"),
        ("erinnere dich dass ich allergisch gegen Haselnüsse bin", "allerg"),
        ("remember that I am allergic to hazelnuts", "allerg"),
    ],
)
async def test_durable_personal_fact_creates_note(utterance: str, needle: str):
    """Execute path must create a note containing the durable fact."""
    repo = NoteRepository(user_id="u1", collection=None)
    skill = NotesSkill(repository=repo, semantic_memory=None)
    assert skill.can_handle(utterance) is True, f"notes must claim {utterance!r}"
    with patch.object(repo, "create", wraps=repo.create) as spy:
        result = await skill.execute(user_text=utterance, user_id="u1")
    assert result.handled is True
    spy.assert_awaited()
    content = spy.await_args.kwargs.get("content") or spy.await_args.args[0]
    assert needle in str(content).casefold()


def test_reminder_due_intent_still_selects_reminders_control():
    """Control twin: due reminder phrasing must not be stolen by notes."""
    utterance = "erinnere mich in two minutes to stretch"
    handler = _registry().find_handler(utterance)
    assert handler is not None
    assert handler.name == "reminders"
    notes = NotesSkill(repository=NoteRepository(user_id="u1"))
    assert notes.can_handle(utterance) is False


@pytest.mark.asyncio
async def test_active_recall_still_surfaces_personal_fact_control():
    """Control twin: ActiveRecall about-you still shows a real personal fact."""
    from datetime import UTC, datetime
    from unittest.mock import AsyncMock, MagicMock

    from src.models.memory import SemanticMemoryFact
    from src.skills.active_recall.skill import ActiveRecallSkill

    fact = SemanticMemoryFact(
        user_id="u1",
        content="User is allergic to hazelnuts.",
        importance_score=0.8,
        entities_involved=[],
        created_at=datetime(2026, 9, 16, tzinfo=UTC),
        last_accessed=datetime(2026, 9, 16, tzinfo=UTC),
    )
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[fact])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="What do you know about me?",
        user_id="u1",
        display_name="Ada",
        language="en",
    )
    assert "hazelnut" in result.response_text.casefold()
