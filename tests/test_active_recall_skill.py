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
async def test_execute_dedupes_identical_fact_lines():
    """The same stored sentence must appear once in the spoken recap."""
    same = "User likes oat milk."
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[_fact(same), _fact(same), _fact(same)])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(user_text="What do you know about me?", user_id="u1")
    assert result.handled is True
    assert result.response_text.count(same) == 1


@pytest.mark.asyncio
async def test_execute_name_question_uses_display_name_without_sm_search():
    """Name questions answer from User.display_name only; SM is not searched."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="What is my name?",
        user_id="u1",
        display_name="Akosh",
    )
    assert result.handled is True
    assert "Akosh" in result.response_text
    mock_sem.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_about_me_uses_display_name_not_copied_memory_fact():
    """Preferred name comes from the user record; leftover SM copies are skipped."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(
        return_value=[_fact("The user prefers to be addressed as Tony.")]
    )
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="What do you know about me?",
        user_id="u1",
        display_name="Tony",
    )
    assert result.response_text.count("Tony") == 1
    assert "I address you as Tony" in result.response_text
    assert "prefers to be addressed" not in result.response_text


@pytest.mark.asyncio
async def test_topic_recall_does_not_inject_display_name():
    """A topic question must not prepend the preferred name."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[_fact("User likes oat milk.")])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="What do you know about oat milk?",
        user_id="u1",
        display_name="Tony",
    )
    assert "Tony" not in result.response_text
    assert "oat milk" in result.response_text.lower()


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


@pytest.mark.asyncio
async def test_leading_greeting_does_not_become_the_recall_topic():
    """Live walk 2026-09-16: 'Hallo, was weisst Du über mich?' must recall me, not Hallo.

    A greeting before the trigger is leftover after phrase strip and must not
    become empty_topic '{query}'. Control: a topic that is the word Hallo
    still searches Hallo.
    """
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="Hallo, was weisst Du über mich?",
        user_id="u1",
    )
    assert result.handled is True
    assert "gespeichert: 'Hallo'" not in result.response_text
    assert "Hallo" not in result.response_text
    query = mock_sem.search.call_args.kwargs["query"]
    assert query.lower() not in {"hallo", "hallo,"}
    assert query.lower() in {"", "mich", "mir", "me"}

    mock_sem.search.reset_mock()
    topic = await skill.execute(
        user_text="Was weißt du über Hallo?",
        user_id="u1",
    )
    topic_query = mock_sem.search.call_args.kwargs["query"]
    assert "hallo" in topic_query.lower()
    assert "gespeichert: 'Hallo'" in topic.response_text


@pytest.mark.asyncio
async def test_leading_greeting_keeps_a_real_topic():
    """Greeting plus topic must search the topic, not the greeting."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    await skill.execute(
        user_text="Hallo, was weißt du über Ildi?",
        user_id="u1",
    )
    query = mock_sem.search.call_args.kwargs["query"]
    assert "ildi" in query.lower()
    assert "hallo" not in query.lower()


def test_can_handle_greeting_then_german_recall():
    """Spoken 'Hallo, …' plus a recall question is still ActiveRecall."""
    skill = ActiveRecallSkill()
    assert skill.can_handle("Hallo, was weisst Du über mich?") is True
    assert skill.can_handle("Hallo") is False


def test_can_handle_hungarian_recall_including_tuds_typo():
    """Live walk 2026-09-16: 'mit tuds rolam' must still be ActiveRecall.

    Canonical 'mit tudsz rólam' already matches. Dropped -sz and missing
    accent are typed/STT forms of the same intent. Control: first-person
    'mit tudok' is not recall.
    """
    skill = ActiveRecallSkill()
    assert skill.can_handle("mit tudsz rólam") is True
    assert skill.can_handle("mit tuds rolam") is True
    assert skill.can_handle("Mit tuds rólam?") is True
    assert skill.can_handle("mit tudok rólam") is False


@pytest.mark.asyncio
async def test_hungarian_tuds_typo_recalls_the_user_in_hungarian():
    """Dropped -sz must recall 'you', not fall through to the LLM path."""
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    skill = ActiveRecallSkill(semantic_memory=mock_sem)

    result = await skill.execute(user_text="mit tuds rolam", user_id="u1")
    assert result.handled is True
    query = mock_sem.search.call_args.kwargs["query"]
    assert query.lower() in {"", "rólam", "rolam", "nekem"}
    assert "személyes" in result.response_text.lower()
    assert "Here's what I know" not in result.response_text
