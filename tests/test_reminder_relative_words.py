"""Cluster 3 / Slice-Brief 8: relative due with number WORDS + honest confirm.

Re-Walk L7: ``_RELATIVE_N`` only matches digits (``in 2 minutes``), not
``two`` / ``zwei`` / ``két``. Confirm must not claim a scheduled reminder
when ``due_at`` is None (no \"I'll remind you\" / \"Ich erinnere dich\" /
\"Emlékeztetlek\" due-claim without a time).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill

_FIXED_NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

_DUE_CLAIM_EN = ("i'll remind you", "i will remind you")
_DUE_CLAIM_DE = ("ich erinnere dich",)
_DUE_CLAIM_HU = ("emlékeztetlek",)


def _skill() -> tuple[RemindersSkill, ReminderRepository]:
    repo = ReminderRepository(user_id="u1", collection=None)
    return RemindersSkill(repository=repo, semantic_memory=None, llm=None), repo


def _assert_no_due_claim(text: str, phrases: tuple[str, ...]) -> None:
    lower = text.lower()
    for phrase in phrases:
        assert (
            phrase not in lower
        ), f"dishonest due-claim {phrase!r} without due_at: {text!r}"


@pytest.mark.asyncio
async def test_relative_digit_minutes_english_still_sets_due_control():
    """Control twin: digit path ``in 2 minutes`` must keep setting due_at."""
    skill, repo = _skill()
    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc", return_value=_FIXED_NOW),
    ):
        result = await skill.execute(
            user_text="remind me in 2 minutes to drink water",
            user_id="u1",
            language="en",
        )
    assert result.handled is True
    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 12, 2, tzinfo=UTC)
    lower = result.response_text.lower()
    assert any(p in lower for p in _DUE_CLAIM_EN)


@pytest.mark.asyncio
async def test_relative_word_two_minutes_english_sets_due():
    """'in two minutes' must set due_at (+2 min), not leave due unset."""
    skill, repo = _skill()
    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc", return_value=_FIXED_NOW),
    ):
        result = await skill.execute(
            user_text="Remind me in two minutes to stretch",
            user_id="u1",
            language="en",
        )
    assert result.handled is True
    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(2026, 8, 20, 12, 2, tzinfo=UTC), (
        f"word-number relative due missing; got due_at={due!r} "
        f"reply={result.response_text!r}"
    )
    assert "stretch" in spy.await_args.kwargs["content"].lower()


@pytest.mark.asyncio
async def test_relative_word_zwei_minuten_german_sets_due():
    """'in zwei Minuten' must set due_at two minutes from now."""
    skill, repo = _skill()
    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc", return_value=_FIXED_NOW),
    ):
        result = await skill.execute(
            user_text="Erinner mich in zwei Minuten mich zu dehnen",
            user_id="u1",
            language="de",
        )
    assert result.handled is True
    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(
        2026, 8, 20, 12, 2, tzinfo=UTC
    ), f"German word-number relative due missing; got due_at={due!r}"


@pytest.mark.asyncio
async def test_relative_word_ket_perc_hungarian_sets_due():
    """'két perc múlva' must set due_at two minutes from now."""
    skill, repo = _skill()
    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc", return_value=_FIXED_NOW),
    ):
        result = await skill.execute(
            user_text="emlékeztess két perc múlva nyújtózkodni",
            user_id="u1",
            language="hu",
        )
    assert result.handled is True
    due = spy.await_args.kwargs["due_at"]
    assert due == datetime(
        2026, 8, 20, 12, 2, tzinfo=UTC
    ), f"Hungarian word-number relative due missing; got due_at={due!r}"


@pytest.mark.asyncio
async def test_confirm_without_due_at_must_not_claim_scheduled_reminder_en():
    """Create without parsable due must not use due-claim phrasing.

    ``created`` / ``created_due`` must key strictly on due_at is not None —
    no \"I'll remind you\" when no time was determined.
    """
    skill, repo = _skill()
    with patch.object(repo, "create", wraps=repo.create) as spy:
        result = await skill.execute(
            user_text="Remind me to stretch",
            user_id="u1",
            language="en",
        )
    assert result.handled is True
    assert spy.await_args.kwargs["due_at"] is None
    _assert_no_due_claim(result.response_text, _DUE_CLAIM_EN)


@pytest.mark.asyncio
async def test_confirm_without_due_at_must_not_claim_scheduled_reminder_de():
    """German create without due must not say 'Ich erinnere dich'."""
    skill, repo = _skill()
    with patch.object(repo, "create", wraps=repo.create) as spy:
        result = await skill.execute(
            user_text="Erinner mich ans Dehnen",
            user_id="u1",
            language="de",
        )
    assert result.handled is True
    assert spy.await_args.kwargs["due_at"] is None
    _assert_no_due_claim(result.response_text, _DUE_CLAIM_DE)


@pytest.mark.asyncio
async def test_confirm_without_due_at_must_not_claim_scheduled_reminder_hu():
    """Hungarian create without due must not say 'Emlékeztetlek'."""
    skill, repo = _skill()
    with patch.object(repo, "create", wraps=repo.create) as spy:
        result = await skill.execute(
            user_text="emlékeztess nyújtózkodni",
            user_id="u1",
            language="hu",
        )
    assert result.handled is True
    assert spy.await_args.kwargs["due_at"] is None
    _assert_no_due_claim(result.response_text, _DUE_CLAIM_HU)


@pytest.mark.asyncio
async def test_confirm_with_due_still_claims_reminder_en_control():
    """Control twin: when due_at is set, EN confirm may claim the reminder."""
    skill, repo = _skill()
    with (
        patch.object(repo, "create", wraps=repo.create) as spy,
        patch("src.skills.reminders.skill._now_utc", return_value=_FIXED_NOW),
    ):
        result = await skill.execute(
            user_text="remind me in 2 minutes to stretch",
            user_id="u1",
            language="en",
        )
    assert spy.await_args.kwargs["due_at"] is not None
    lower = result.response_text.lower()
    assert any(p in lower for p in _DUE_CLAIM_EN)
