"""Slice-Brief 12: greeting clear-language heuristics (EN/DE/HU).

Bare greetings must return a clear language from
``detect_clear_response_language`` so replies do not fall back to English
via GUI/default alone.

DE: hallo, guten morgen/tag/abend, servus, moin (+ short variants).
EN: hello (existing); hi / hey as clear EN greeting signals.
HU: szia (existing); sziasztok (+ sensible variants).

Controls: DE sentence with Hallo stays de; reminder due phrases keep their
clear language; Hallo must not merge with hello (de vs en). Skills must not
claim bare greetings.
"""

from __future__ import annotations

import pytest

from src.core.language import (
    detect_clear_response_language,
    detect_response_language,
)
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill


def _registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(NotesSkill(repository=NoteRepository(user_id="u1")))
    registry.register(RemindersSkill(repository=ReminderRepository(user_id="u1")))
    return registry


@pytest.mark.parametrize(
    "utterance",
    [
        "Hallo",
        "hallo",
        "HALLO",
        "Hallo Jarvis",
        "hallo jarvis",
        "guten morgen",
        "Guten Morgen",
        "guten tag",
        "Guten Tag",
        "guten abend",
        "Guten Abend",
        "servus",
        "Servus",
        "moin",
        "Moin",
    ],
)
def test_clear_german_greetings(utterance: str):
    """DE greeting words must be a clear German signal without GUI fallback."""
    assert detect_clear_response_language(utterance) == "de", (
        f"expected clear de for {utterance!r}, "
        f"got {detect_clear_response_language(utterance)!r}"
    )
    # Without hint, response language must still be de (not English default).
    assert detect_response_language(utterance) == "de"
    assert detect_response_language(utterance, hint="en") == "de"


@pytest.mark.parametrize(
    "utterance",
    [
        "hello",
        "Hello",
        "hi",
        "Hi",
        "hey",
        "Hey",
        "hi jarvis",
        "hey there",
    ],
)
def test_clear_english_greetings(utterance: str):
    """EN greeting signals (hello + hi/hey) must be clear English."""
    assert detect_clear_response_language(utterance) == "en", (
        f"expected clear en for {utterance!r}, "
        f"got {detect_clear_response_language(utterance)!r}"
    )
    assert detect_response_language(utterance) == "en"


@pytest.mark.parametrize(
    "utterance",
    [
        "szia",
        "Szia",
        "sziasztok",
        "Sziasztok",
        "Szia Jarvis",
        "sziasztok jarvis",
    ],
)
def test_clear_hungarian_greetings(utterance: str):
    """HU greetings including sziasztok must be a clear Hungarian signal."""
    assert detect_clear_response_language(utterance) == "hu", (
        f"expected clear hu for {utterance!r}, "
        f"got {detect_clear_response_language(utterance)!r}"
    )
    assert detect_response_language(utterance) == "hu"
    assert detect_response_language(utterance, hint="en") == "hu"


def test_hallo_sentence_stays_german_control():
    """Control: DE sentence containing Hallo stays clear German."""
    text = "Hallo, wie geht es dir?"
    assert detect_clear_response_language(text) == "de"
    assert detect_response_language(text, hint="en") == "de"


def test_hallo_is_not_english_hello_merge():
    """Control: bare Hallo must not be treated as English hello."""
    assert detect_clear_response_language("Hallo") == "de"
    assert detect_clear_response_language("hello") == "en"
    assert detect_clear_response_language("Hallo") != detect_clear_response_language(
        "hello"
    )


@pytest.mark.parametrize(
    "utterance,expected",
    [
        ("Erinnere mich in two minutes", "en"),
        ("remind me in two minutes", "en"),
        ("emlékeztess két perc múlva", "hu"),
        ("Remind me tomorrow to call the dentist", "en"),
    ],
)
def test_reminder_due_phrases_clear_language_unchanged(utterance: str, expected: str):
    """Control: reminder due phrasing must keep its clear language signal."""
    assert detect_clear_response_language(utterance) == expected, (
        f"reminder phrase language drifted for {utterance!r}: "
        f"got {detect_clear_response_language(utterance)!r}, want {expected!r}"
    )


@pytest.mark.parametrize(
    "utterance",
    [
        "Hallo",
        "hi",
        "hey",
        "sziasztok",
        "guten morgen",
        "moin",
        "servus",
    ],
)
def test_bare_greetings_are_not_stolen_by_skills(utterance: str):
    """Control: bare greetings must not be claimed by Notes/Reminders."""
    found = _registry().find_handler(utterance)
    assert found is None, f"{utterance!r} stolen by {getattr(found, 'name', None)}"


def test_reminder_intent_still_claimed_control():
    """Control twin: German reminder create must still hit reminders."""
    found = _registry().find_handler("Erinnere mich in two minutes")
    assert found is not None
    assert found.name == "reminders"
