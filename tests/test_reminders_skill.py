"""Unit tests for RemindersSkill and ReminderRepository (Phase 4 Option A)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.reminder import Reminder
from src.skills.base import SkillResult
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill


def test_reminder_defaults():
    """Reminder model must default to pending status and auto-generate an id."""
    r = Reminder(user_id="u1", content="Call dentist")
    assert r.user_id == "u1"
    assert r.content == "Call dentist"
    assert r.due_at is None
    assert r.status == "pending"
    assert r.id


@pytest.mark.asyncio
async def test_repository_create_without_collection():
    """Create must still return a Reminder when no Mongo collection is wired."""
    repo = ReminderRepository(user_id="u1", collection=None)
    r = await repo.create(content="Buy tickets")
    assert r.content == "Buy tickets"
    assert r.user_id == "u1"


@pytest.mark.asyncio
async def test_repository_list_empty_without_collection():
    """List without a collection must return an empty list."""
    repo = ReminderRepository(user_id="u1", collection=None)
    assert await repo.list_reminders() == []


@pytest.mark.asyncio
async def test_repository_create_calls_insert():
    """Create must persist via insert_one with user_id and pending status."""
    mock_coll = MagicMock()
    mock_coll.insert_one = AsyncMock()
    repo = ReminderRepository(user_id="u1", collection=mock_coll)

    r = await repo.create(content="Meeting tomorrow")
    assert r.content == "Meeting tomorrow"
    mock_coll.insert_one.assert_awaited_once()
    dumped = mock_coll.insert_one.call_args[0][0]
    assert dumped["user_id"] == "u1"
    assert dumped["status"] == "pending"


def test_can_handle_create_intents():
    """Skill must claim create-reminder utterances and reject unrelated chat."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("remind me to call mom") is True
    assert skill.can_handle("Erinner mich an den Termin") is True
    assert skill.can_handle("just chatting") is False


def test_can_handle_list_intents():
    """Skill must claim list-reminders utterances in EN/DE."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("show reminders") is True
    assert skill.can_handle("meine Erinnerungen") is True


@pytest.mark.asyncio
async def test_execute_create_reminder():
    """Create path must confirm the reminder and echo its content."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    result = await skill.execute(
        user_text="remind me: buy oat milk tomorrow",
        user_id="u1",
    )
    assert isinstance(result, SkillResult)
    assert result.handled is True
    assert "remind" in result.response_text.lower() or "Got it" in result.response_text
    assert "oat milk" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_list_empty():
    """List with no pending reminders must say so clearly."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo)

    result = await skill.execute(user_text="show reminders", user_id="u1")
    assert result.handled is True
    assert "no pending" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_create_writes_semantic_summary():
    """Creating a reminder must write a short summary fact into Semantic Memory."""
    repo = ReminderRepository(user_id="u1", collection=None)
    mock_sem = MagicMock()
    mock_sem.add_fact = AsyncMock()
    skill = RemindersSkill(repository=repo, semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="remind me: important meeting on Friday",
        user_id="u1",
    )
    assert result.handled is True
    mock_sem.add_fact.assert_awaited_once()
    call_kwargs = mock_sem.add_fact.call_args.kwargs
    assert (
        "reminder" in call_kwargs["fact"].lower()
        or "meeting" in call_kwargs["fact"].lower()
    )


def test_registry_finds_reminders():
    """Registry must find the skill by name and by matching intent."""
    registry = SkillRegistry()
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    registry.register(skill)

    assert registry.get("reminders") is skill
    found = registry.find_handler("remind me to water the plants")
    assert found is skill
    assert registry.find_handler("hello world") is None
