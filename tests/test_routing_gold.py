"""Routing gold set: expected skill (or llm) for EN/DE/HU utterances."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.skills.active_recall.skill import ActiveRecallSkill
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill
from src.skills.web_search.skill import WebSearchSkill

_GOLD = Path(__file__).parent / "eval" / "routing_gold.json"


def _registry() -> SkillRegistry:
    """Same registration order as production (recall first)."""
    registry = SkillRegistry()
    registry.register(ActiveRecallSkill())
    registry.register(NotesSkill(repository=NoteRepository(user_id="gold")))
    registry.register(RemindersSkill(repository=ReminderRepository(user_id="gold")))
    registry.register(WebSearchSkill())
    return registry


def _cases() -> list[pytest.ParameterSet]:
    payload = json.loads(_GOLD.read_text(encoding="utf-8"))
    params: list[pytest.ParameterSet] = []
    for case in payload["cases"]:
        marks = []
        if case.get("xfail"):
            marks.append(
                pytest.mark.xfail(
                    reason=case.get("reason", "future matcher"),
                    strict=False,
                )
            )
        params.append(pytest.param(case, id=case["id"], marks=marks))
    return params


@pytest.mark.parametrize("case", _cases())
def test_routing_gold_matches_expected_skill(case: dict) -> None:
    """Gold utterance must route to the labeled skill (or llm if none)."""
    found = _registry().find_handler(case["text"])
    actual = found.name if found is not None else "llm"
    assert actual == case["expected"]
