"""Unit tests for NotesSkill and NoteRepository (Phase 4 Option A)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.note import Note
from src.skills.base import SkillResult
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry

# ---------------------------------------------------------------------------
# Note model
# ---------------------------------------------------------------------------


def test_note_defaults():
    """Note model must set sensible defaults (no title/tags, auto id + timestamp)."""
    note = Note(user_id="u1", content="Buy milk")
    assert note.user_id == "u1"
    assert note.content == "Buy milk"
    assert note.title is None
    assert note.tags == []
    assert note.id
    assert note.created_at is not None


def test_note_with_title_and_tags():
    """Optional title and tags must be stored on the Note model."""
    note = Note(
        user_id="u1",
        content="Project deadline",
        title="Work",
        tags=["work", "urgent"],
    )
    assert note.title == "Work"
    assert note.tags == ["work", "urgent"]


# ---------------------------------------------------------------------------
# NoteRepository (in-memory / no collection)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repository_create_without_collection():
    """Create must still return a Note when no Mongo collection is wired (unit mode)."""
    repo = NoteRepository(user_id="u1", collection=None)
    note = await repo.create(content="Hello note")
    assert note.content == "Hello note"
    assert note.user_id == "u1"


@pytest.mark.asyncio
async def test_repository_list_empty_without_collection():
    """List without a collection must return an empty list, not raise."""
    repo = NoteRepository(user_id="u1", collection=None)
    notes = await repo.list_notes()
    assert notes == []


@pytest.mark.asyncio
async def test_repository_create_calls_insert():
    """Create must persist the note via insert_one with user_id and content."""
    mock_coll = MagicMock()
    mock_coll.insert_one = AsyncMock()
    repo = NoteRepository(user_id="u1", collection=mock_coll)

    note = await repo.create(content="Persisted note", title="T1")
    assert note.content == "Persisted note"
    mock_coll.insert_one.assert_awaited_once()
    dumped = mock_coll.insert_one.call_args[0][0]
    assert dumped["user_id"] == "u1"
    assert dumped["content"] == "Persisted note"
    assert dumped["title"] == "T1"
    assert dumped["_id"] == note.id
    assert dumped["id"] == note.id


# ---------------------------------------------------------------------------
# NotesSkill – can_handle
# ---------------------------------------------------------------------------


def test_can_handle_create_intents():
    """Skill must claim create-note utterances and reject unrelated chat."""
    skill = NotesSkill(repository=NoteRepository(user_id="u1"))
    assert skill.can_handle("Please note: buy milk") is True
    assert skill.can_handle("Notiz: Meeting um 15 Uhr") is True
    assert skill.can_handle("remember this: call mom") is True
    assert skill.can_handle("just chatting about the weather") is False


def test_can_handle_list_intents():
    """Skill must claim list-notes utterances in EN/DE."""
    skill = NotesSkill(repository=NoteRepository(user_id="u1"))
    assert skill.can_handle("show my notes") is True
    assert skill.can_handle("list notes") is True
    assert skill.can_handle("meine Notizen") is True


# ---------------------------------------------------------------------------
# NotesSkill – execute create / list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_create_note():
    """Create path must confirm save and echo the note content."""
    repo = NoteRepository(user_id="u1", collection=None)
    skill = NotesSkill(repository=repo, semantic_memory=None)

    result = await skill.execute(
        user_text="note: buy oat milk tomorrow",
        user_id="u1",
    )
    assert isinstance(result, SkillResult)
    assert result.handled is True
    assert (
        "saved the note" in result.response_text.lower()
        or "Got it" in result.response_text
    )
    assert "buy oat milk" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_list_empty():
    """List with no notes must tell the user the list is empty."""
    repo = NoteRepository(user_id="u1", collection=None)
    skill = NotesSkill(repository=repo)

    result = await skill.execute(user_text="show my notes", user_id="u1")
    assert result.handled is True
    assert "no notes" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_create_writes_semantic_summary():
    """Creating a note must also write a short summary fact into Semantic Memory."""
    repo = NoteRepository(user_id="u1", collection=None)
    mock_sem = MagicMock()
    mock_sem.add_fact = AsyncMock()
    skill = NotesSkill(repository=repo, semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="note: important meeting on Friday",
        user_id="u1",
    )
    assert result.handled is True
    mock_sem.add_fact.assert_awaited_once()
    call_kwargs = mock_sem.add_fact.call_args.kwargs
    assert (
        "note" in call_kwargs["fact"].lower()
        or "meeting" in call_kwargs["fact"].lower()
    )


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------


def test_registry_register_and_find():
    """Registry must return the skill by name and by matching intent."""
    registry = SkillRegistry()
    skill = NotesSkill(repository=NoteRepository(user_id="u1"))
    registry.register(skill)

    assert registry.get("notes") is skill
    assert registry.list_names() == ["notes"]

    found = registry.find_handler("please note: something")
    assert found is skill

    assert registry.find_handler("hello world") is None


def test_registry_duplicate_raises():
    """Registering the same skill name twice must raise ValueError."""
    registry = SkillRegistry()
    skill = NotesSkill(repository=NoteRepository(user_id="u1"))
    registry.register(skill)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(skill)


@pytest.mark.asyncio
async def test_execute_create_note_replies_in_german():
    """German create utterances must get a German confirmation, not English."""
    repo = NoteRepository(user_id="u1", collection=None)
    skill = NotesSkill(repository=repo, semantic_memory=None)

    result = await skill.execute(
        user_text="merk dir das: Milch kaufen",
        user_id="u1",
    )
    assert result.handled is True
    assert (
        "Notiz" in result.response_text or "gespeichert" in result.response_text.lower()
    )
    assert "Got it" not in result.response_text
