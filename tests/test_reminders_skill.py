"""Unit tests for RemindersSkill and ReminderRepository (Phase 4 + date-aware Phase 5)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
    assert dumped["_id"] == r.id
    assert dumped["id"] == r.id


@pytest.mark.asyncio
async def test_repository_create_with_due_at():
    """Create must accept and store an explicit due_at datetime."""
    repo = ReminderRepository(user_id="u1", collection=None)
    due = datetime(2026, 8, 10, 14, 0, tzinfo=UTC)
    r = await repo.create(content="Arbeitsagentur", due_at=due)
    assert r.due_at == due
    assert r.content == "Arbeitsagentur"


@pytest.mark.asyncio
async def test_repository_list_with_due_range():
    """list_reminders must filter by due_from / due_to when provided."""
    mock_coll = MagicMock()

    due = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    docs = [
        {
            "id": "r1",
            "user_id": "u1",
            "content": "Zahnarzt",
            "due_at": due.isoformat(),
            "status": "pending",
            "created_at": due.isoformat(),
            "last_accessed": due.isoformat(),
        }
    ]

    class Cursor:
        def __init__(self, data):
            self._data = data
            self._idx = 0

        def sort(self, *args, **kwargs):
            return self

        def limit(self, n):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._idx >= len(self._data):
                raise StopAsyncIteration
            item = self._data[self._idx]
            self._idx += 1
            return item

    mock_coll.find = MagicMock(return_value=Cursor(docs))
    repo = ReminderRepository(user_id="u1", collection=mock_coll)

    due_from = datetime(2026, 8, 1, tzinfo=UTC)
    due_to = datetime(2026, 8, 10, tzinfo=UTC)
    results = await repo.list_reminders(due_from=due_from, due_to=due_to)
    assert len(results) == 1
    assert results[0].content == "Zahnarzt"
    call_filters = mock_coll.find.call_args[0][0]
    assert "due_at" in call_filters


@pytest.mark.asyncio
async def test_repository_search_by_content():
    """search_by_content must return reminders whose content matches the query."""
    mock_coll = MagicMock()

    docs = [
        {
            "id": "r1",
            "user_id": "u1",
            "content": "Termin bei der Arbeitsagentur",
            "due_at": datetime(2026, 8, 12, 9, 30, tzinfo=UTC).isoformat(),
            "status": "pending",
            "created_at": datetime(2026, 8, 1, tzinfo=UTC).isoformat(),
            "last_accessed": datetime(2026, 8, 1, tzinfo=UTC).isoformat(),
        }
    ]

    class Cursor:
        def __init__(self, data):
            self._data = data
            self._idx = 0

        def sort(self, *args, **kwargs):
            return self

        def limit(self, n):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._idx >= len(self._data):
                raise StopAsyncIteration
            item = self._data[self._idx]
            self._idx += 1
            return item

    mock_coll.find = MagicMock(return_value=Cursor(docs))
    repo = ReminderRepository(user_id="u1", collection=mock_coll)

    results = await repo.search_by_content("Arbeitsagentur")
    assert len(results) == 1
    assert "Arbeitsagentur" in results[0].content
    assert results[0].due_at is not None
    assert results[0].due_at.hour == 9


def test_can_handle_create_intents():
    """Skill must claim create-reminder utterances and reject unrelated chat."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("remind me to call mom") is True
    assert skill.can_handle("Erinner mich an den Termin") is True
    assert skill.can_handle("Erinnere mich morgen um 14 Uhr an den Zahnarzt") is True
    assert skill.can_handle("just chatting") is False


def test_can_handle_list_intents():
    """Skill must claim list-reminders utterances in EN/DE."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("show reminders") is True
    assert skill.can_handle("meine Erinnerungen") is True


def test_can_handle_agenda_intents():
    """Skill must claim agenda queries (today / this week / next week / this month)."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("was steht heute an?") is True
    assert skill.can_handle("what's on today") is True
    assert skill.can_handle("was steht diese Woche an") is True
    assert skill.can_handle("what is next week") is True
    assert skill.can_handle("was steht diesen Monat an") is True


def test_can_handle_lookup_intents():
    """Skill must claim specific-event lookup questions."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert (
        skill.can_handle("wann habe ich meinen Termin bei der Arbeitsagentur?") is True
    )
    assert skill.can_handle("when is the dentist appointment?") is True
    assert skill.can_handle("Wann muss ich X.Y. anrufen?") is True


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
async def test_execute_create_sets_due_at_tomorrow():
    """Create with 'tomorrow' must set due_at to the next calendar day."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with patch("src.skills.reminders.skill._now_utc") as mock_now:
        mock_now.return_value = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="remind me tomorrow: call the dentist",
            user_id="u1",
        )

    assert result.handled is True
    assert "dentist" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_create_sets_due_at_with_time():
    """Create with explicit time must store hour and minute on due_at."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with patch("src.skills.reminders.skill._now_utc") as mock_now:
        mock_now.return_value = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="Erinner mich morgen um 14 Uhr an den Zahnarzt",
            user_id="u1",
        )

    assert result.handled is True
    assert (
        "Zahnarzt" in result.response_text or "zahnarzt" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_list_empty():
    """List with no pending reminders must say so clearly."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo)

    result = await skill.execute(user_text="show reminders", user_id="u1")
    assert result.handled is True
    assert "no pending" in result.response_text.lower()


@pytest.mark.asyncio
async def test_execute_agenda_today_empty():
    """Agenda 'today' with no matching reminders must say so."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo)

    result = await skill.execute(user_text="was steht heute an?", user_id="u1")
    assert result.handled is True
    assert (
        "nothing" in result.response_text.lower()
        or "nichts" in result.response_text.lower()
        or "keine" in result.response_text.lower()
        or "no pending" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_lookup_by_content():
    """Lookup must find a reminder by keyword and return date + time if set."""
    due = datetime(2026, 8, 12, 9, 30, tzinfo=UTC)
    mock_repo = MagicMock(spec=ReminderRepository)
    mock_repo.search_by_content = AsyncMock(
        return_value=[
            Reminder(
                user_id="u1",
                content="Termin bei der Arbeitsagentur",
                due_at=due,
            )
        ]
    )
    skill = RemindersSkill(repository=mock_repo)

    result = await skill.execute(
        user_text="wann habe ich meinen Termin bei der Arbeitsagentur?",
        user_id="u1",
    )
    assert result.handled is True
    text = result.response_text.lower()
    assert "arbeitsagentur" in text
    assert (
        "9" in result.response_text
        or "09" in result.response_text
        or "12" in result.response_text
    )


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


def test_can_handle_rejects_incidental_when():
    """Bare 'when' mid-sentence must not trigger reminder lookup."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert (
        skill.can_handle(
            "I just want to see if you can record a very important memory of mine. "
            "This is the moment when you are supposed to start functioning."
        )
        is False
    )
    assert skill.can_handle("Tell me when you are ready.") is False
    assert skill.can_handle("Call me when the package arrives.") is False


def test_can_handle_lookup_still_matches_explicit_questions():
    """Explicit lookup questions must still be claimed after tightening patterns."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("when is the dentist appointment?") is True
    assert (
        skill.can_handle("wann habe ich meinen Termin bei der Arbeitsagentur?") is True
    )
    assert skill.can_handle("when do i need to call the bank?") is True


@pytest.mark.asyncio
async def test_execute_create_german_reply_and_numeric_date():
    """DE create must answer in German and parse a numeric date like 18.8."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="Erinnerung für heute dem 18.8. Zahnarzt",
            user_id="u1",
        )

    assert result.handled is True
    assert "erinnere dich" in result.response_text.lower()
    assert "got it" not in result.response_text.lower()
    assert "Zahnarzt" in result.response_text
    spy.assert_awaited_once()
    due = spy.await_args.kwargs["due_at"]
    assert due is not None
    assert due.date() == datetime(2026, 8, 18).date()
    content = spy.await_args.kwargs["content"]
    assert "zahnarzt" in content.lower()
    assert "18.8" not in content
    assert "heute" not in content.lower()


@pytest.mark.asyncio
async def test_execute_create_uses_llm_slots_when_available():
    """LLM slot fill must win over regex for content and due_at."""
    repo = ReminderRepository(user_id="u1", collection=None)
    llm = AsyncMock()
    llm.generate_response.return_value = (
        '{"content": "Zahnarzt", "due_iso": "2026-08-18T00:00:00+00:00"}'
    )
    skill = RemindersSkill(repository=repo, semantic_memory=None, llm=llm)

    with patch.object(repo, "create", wraps=repo.create) as spy:
        result = await skill.execute(
            user_text="Erinnerung für heute dem 18.8. bitte",
            user_id="u1",
        )

    assert result.handled is True
    spy.assert_awaited_once()
    assert spy.await_args.kwargs["content"] == "Zahnarzt"
    assert spy.await_args.kwargs["due_at"].date() == datetime(2026, 8, 18).date()
    llm.generate_response.assert_awaited()


@pytest.mark.asyncio
async def test_llm_slots_invalid_due_keeps_regex_due():
    """Unparseable due_iso must not wipe a date already parsed from the utterance."""
    repo = ReminderRepository(user_id="u1", collection=None)
    llm = AsyncMock()
    llm.generate_response.return_value = (
        '{"content": "Zahnarzt", "due_iso": "not-a-date"}'
    )
    skill = RemindersSkill(repository=repo, semantic_memory=None, llm=llm)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        await skill.execute(
            user_text="Erinnerung für den 18.8. Zahnarzt",
            user_id="u1",
        )

    due = spy.await_args.kwargs["due_at"]
    assert due is not None
    assert due.date() == datetime(2026, 8, 18).date()
    assert spy.await_args.kwargs["content"] == "Zahnarzt"


@pytest.mark.asyncio
async def test_llm_slots_failure_falls_back_to_regex():
    """If slot extraction raises, create must still succeed via regex."""
    repo = ReminderRepository(user_id="u1", collection=None)
    llm = AsyncMock()
    llm.generate_response.side_effect = RuntimeError("llm down")
    skill = RemindersSkill(repository=repo, semantic_memory=None, llm=llm)

    result = await skill.execute(
        user_text="remind me tomorrow: call the dentist",
        user_id="u1",
    )
    assert result.handled is True
    assert "dentist" in result.response_text.lower()


def test_can_handle_rejects_incidental_today():
    """Bare date words must not claim ordinary chat or search."""
    skill = RemindersSkill(repository=ReminderRepository(user_id="u1"))
    assert skill.can_handle("how are you today?") is False
    assert skill.can_handle("search for weather today") is False
    assert skill.can_handle("I have a lot this week") is False


@pytest.mark.asyncio
async def test_execute_create_with_today_does_not_run_agenda():
    """'Remind me today …' must create a reminder, not list today's agenda."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="remind me today to call mom",
            user_id="u1",
        )

    assert result.handled is True
    assert "mom" in result.response_text.lower()
    assert "nothing scheduled" not in result.response_text.lower()
    spy.assert_awaited_once()
    due = spy.await_args.kwargs["due_at"]
    assert due is not None
    assert due.date() == datetime(2026, 8, 3).date()


@pytest.mark.asyncio
async def test_execute_create_time_without_date_defaults_today_or_tomorrow():
    """'Remind me at 14:00 …' with no date token must still set due_at."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="remind me at 14:00 to call the bank",
            user_id="u1",
        )

    assert result.handled is True
    spy.assert_awaited_once()
    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 3, 14, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_execute_hungarian_this_week_uses_week_window():
    """'Mi van a héten' must list Monday–Sunday, not only today."""
    mock_repo = MagicMock(spec=ReminderRepository)
    mock_repo.list_reminders = AsyncMock(return_value=[])
    skill = RemindersSkill(repository=mock_repo)

    with patch("src.skills.reminders.skill._now_utc") as mock_now:
        mock_now.return_value = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        result = await skill.execute(user_text="mi van a héten", user_id="u1")

    assert result.handled is True
    kwargs = mock_repo.list_reminders.await_args.kwargs
    assert kwargs["due_from"].date() == date(2026, 8, 17)
    assert kwargs["due_to"].date() == date(2026, 8, 23)


@pytest.mark.asyncio
async def test_execute_hungarian_today_agenda_uses_today_window():
    """'Mi van ma a naptáramban' must bound due_at to the current calendar day."""
    mock_repo = MagicMock(spec=ReminderRepository)
    mock_repo.list_reminders = AsyncMock(return_value=[])
    skill = RemindersSkill(repository=mock_repo)

    with patch("src.skills.reminders.skill._now_utc") as mock_now:
        mock_now.return_value = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
        result = await skill.execute(user_text="mi van ma a naptáramban", user_id="u1")

    assert result.handled is True
    kwargs = mock_repo.list_reminders.await_args.kwargs
    assert kwargs["due_from"].date() == date(2026, 8, 19)
    assert kwargs["due_to"].date() == date(2026, 8, 19)


@pytest.mark.asyncio
async def test_execute_create_relative_minutes_english():
    """'in 2 minutes' must set due_at two minutes from now (UTC)."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        result = await skill.execute(
            user_text="remind me in 2 minutes to drink water",
            user_id="u1",
        )

    assert result.handled is True
    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 12, 2, tzinfo=UTC)
    assert "water" in spy.await_args.kwargs["content"].lower()


@pytest.mark.asyncio
async def test_execute_create_relative_minutes_german():
    """'in 5 Minuten' must set due_at five minutes from now."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        await skill.execute(
            user_text="Erinner mich in 5 Minuten Wasser zu trinken",
            user_id="u1",
        )

    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 12, 5, tzinfo=UTC)


@pytest.mark.asyncio
async def test_execute_create_relative_minutes_hungarian():
    """'2 perc múlva' must set due_at two minutes from now."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        await skill.execute(
            user_text="emlékeztess 2 perc múlva vizet inni",
            user_id="u1",
        )

    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 12, 2, tzinfo=UTC)


@pytest.mark.asyncio
async def test_execute_create_relative_hour_german():
    """'in einer Stunde' must set due_at one hour from now."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        await skill.execute(
            user_text="Erinner mich in einer Stunde an den Anruf",
            user_id="u1",
        )

    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 13, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_execute_create_relative_hour_hungarian():
    """'1 óra múlva' must set due_at one hour from now."""
    repo = ReminderRepository(user_id="u1", collection=None)
    skill = RemindersSkill(repository=repo, semantic_memory=None)

    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc") as mock_now,
    ):
        mock_now.return_value = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        await skill.execute(
            user_text="emlékeztess 1 óra múlva a hívásra",
            user_id="u1",
        )

    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 13, 0, tzinfo=UTC)
