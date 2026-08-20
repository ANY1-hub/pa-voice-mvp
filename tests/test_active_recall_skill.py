"""Unit tests for ActiveRecallSkill."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.memory import SemanticMemoryFact
from src.skills.active_recall.skill import ActiveRecallSkill
from src.skills.base import SkillResult
from src.skills.registry import SkillRegistry


def _fact(content: str, importance: float = 0.7) -> SemanticMemoryFact:
    return SemanticMemoryFact(
        user_id="u1",
        content=content,
        importance_score=importance,
        entities_involved=[],
        created_at=datetime.now(UTC),
        last_accessed=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# can_handle
# ---------------------------------------------------------------------------


def test_can_handle_english_recall_intents():
    """Skill must claim clear English recall questions and reject plain chat."""
    skill = ActiveRecallSkill()
    assert skill.can_handle("What do you know about my allergies?") is True
    assert skill.can_handle("What do you remember about my job?") is True
    assert skill.can_handle("Remind me what I told you about coffee") is True
    assert skill.can_handle("What are my preferences?") is True
    assert skill.can_handle("just chatting about the weather") is False
    assert skill.can_handle("I don't recall his name") is False
    assert skill.can_handle("What is my name?") is True
    assert skill.can_handle("I have asked what my name is") is True


def test_can_handle_german_recall_intents():
    """Skill must claim German recall phrasings used in the MVP languages."""
    skill = ActiveRecallSkill()
    assert skill.can_handle("Was weißt du über meine Allergien?") is True
    assert skill.can_handle("Was erinnerst du dich an meine Vorlieben") is True
    assert skill.can_handle("Was weißt du über mich?") is True
    assert skill.can_handle("Hallo, wie geht's?") is False
    assert skill.can_handle("Erinnere mich an den Zahnarzt") is False
    assert skill.can_handle("Wie heiße ich?") is True


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_returns_facts_for_topic():
    """Successful search must return a formatted list of matching facts."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[
            _fact("User is allergic to shellfish"),
            _fact("User prefers oat milk"),
        ]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What do you know about my allergies?",
        user_id="u1",
    )
    assert isinstance(result, SkillResult)
    assert result.handled is True
    assert "allergic to shellfish" in result.response_text.lower()
    assert "oat milk" in result.response_text.lower()
    mock_sem.search.assert_awaited()


@pytest.mark.asyncio
async def test_execute_name_question_searches_about_the_user():
    """A name question must look up personal facts, not a leftover topic string."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[_fact("The user prefers to be addressed as Akosh.")]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(user_text="What is my name?", user_id="u1")
    assert result.handled is True
    assert "Akosh" in result.response_text
    mock_sem.search.assert_awaited()
    assert mock_sem.search.await_args.kwargs["query"] == ""


@pytest.mark.asyncio
async def test_execute_no_facts_gives_clear_empty_reply():
    """When Semantic Memory returns nothing, the skill must say so clearly."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="What do you know about quantum physics?",
        user_id="u1",
    )
    assert result.handled is True
    assert (
        "don't have anything" in result.response_text.lower()
        or "nothing" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_without_semantic_memory():
    """Missing Semantic Memory must still return a handled, graceful reply."""
    skill = ActiveRecallSkill(semantic_memory=None)
    result = await skill.execute(user_text="What do you know about me?", user_id="u1")
    assert result.handled is True
    assert "memory" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_extracts_topic_from_trigger():
    """Query passed to search must be the topic after the trigger phrase is stripped."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    await skill.execute(
        user_text="What do you know about my coffee preferences?",
        user_id="u1",
    )
    call_kwargs = mock_sem.search.call_args.kwargs
    assert "coffee" in call_kwargs["query"].lower()


# ---------------------------------------------------------------------------
# Registry placement
# ---------------------------------------------------------------------------


def test_registry_finds_active_recall_before_notes():
    """ActiveRecall registered first must win over Notes for pure recall questions."""
    from src.skills.notes.repository import NoteRepository
    from src.skills.notes.skill import NotesSkill

    registry = SkillRegistry()
    registry.register(ActiveRecallSkill())
    registry.register(NotesSkill(repository=NoteRepository(user_id="u1")))

    found = registry.find_handler("What do you know about my notes?")
    assert found is not None
    assert found.name == "active_recall"


@pytest.mark.asyncio
async def test_execute_german_recall_replies_in_german():
    """German recall questions must be answered in German."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[_fact("User likes oat milk")])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="Was weißt du über mich?",
        user_id="u1",
    )
    assert result.handled is True
    assert "weiß" in result.response_text.lower() or "Das weiß" in result.response_text
    assert "Here's what I know" not in result.response_text
