"""Slice-Brief 15: conversational follow-ups must not trigger WebSearch.

Short definition/identity triggers (what is / was ist / mi az, who is /
wer ist / ki az) must match with Gap 0 only — no filler words between tokens.
Longer search phrases (suche nach, search for, …) keep existing gap tolerance.

Negatives: meta follow-ups like DE „ich wollte nur sehen was deine Antwort ist“
must fall through to the LLM (can_handle False). Controls: „was ist RAG“ etc.
still claim WebSearch.
"""

from __future__ import annotations

import pytest

from src.skills.web_search.skill import WebSearchSkill


def _skill() -> WebSearchSkill:
    return WebSearchSkill(client=None, semantic_memory=None)


@pytest.mark.parametrize(
    "utterance",
    [
        "ich wollte nur sehen was deine Antwort ist.",
        "ich wollte nur sehen was deine Antwort ist",
        "I just wanted to see what your answer is.",
        "csak azt akartam látni mi az",
        "csak azt akartam latni mi az",
        "was deine Antwort ist",
    ],
)
def test_conversational_followup_does_not_claim_web_search(utterance: str):
    """Meta follow-ups / gappy was…ist must not be claimed by WebSearch."""
    skill = _skill()
    assert (
        skill.can_handle(utterance) is False
    ), f"WebSearch must not claim conversational follow-up {utterance!r}"


@pytest.mark.parametrize(
    "utterance",
    [
        "was ist RAG",
        "what is RAG",
        "mi az a RAG",
        "who is Angela Merkel",
        "wer ist Angela Merkel",
        "ki az Angela Merkel",
        "was ist deine Antwort",
        "what is photosynthesis",
    ],
)
def test_tight_definition_triggers_still_claim_web_search(utterance: str):
    """Control: adjacent what/was/mi + is/ist/az (Gap 0) still claims WebSearch."""
    skill = _skill()
    assert (
        skill.can_handle(utterance) is True
    ), f"expected WebSearch to claim definition query {utterance!r}"


@pytest.mark.parametrize(
    "utterance",
    [
        "suche nach RAG",
        "search for RAG",
        "keress rá a RAG-ra",
        "schlag bitte nach RAG",
    ],
)
def test_long_search_phrases_keep_gap_tolerance(utterance: str):
    """Control: longer search phrases may still allow fillers between tokens."""
    skill = _skill()
    assert (
        skill.can_handle(utterance) is True
    ), f"expected WebSearch to claim long search phrase {utterance!r}"


def test_registry_routes_followup_away_from_web_search():
    """Control twin: registry must not hand the DE follow-up to web_search."""
    from src.skills.notes.repository import NoteRepository
    from src.skills.notes.skill import NotesSkill
    from src.skills.registry import SkillRegistry
    from src.skills.reminders.repository import ReminderRepository
    from src.skills.reminders.skill import RemindersSkill
    from src.skills.web_search.skill import WebSearchSkill as WSS

    registry = SkillRegistry()
    registry.register(NotesSkill(repository=NoteRepository(user_id="u1")))
    registry.register(RemindersSkill(repository=ReminderRepository(user_id="u1")))
    registry.register(WSS(client=None, semantic_memory=None))

    utterance = "ich wollte nur sehen was deine Antwort ist"
    found = registry.find_handler(utterance)
    assert (
        found is None or found.name != "web_search"
    ), f"follow-up stolen by {getattr(found, 'name', None)!r}"
