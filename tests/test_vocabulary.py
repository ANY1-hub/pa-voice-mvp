"""Canonical trigger phrases must match the intended skill in EN/DE/HU."""

from fastapi.testclient import TestClient

from src.main import app
from src.skills.active_recall.skill import ActiveRecallSkill
from src.skills.notes.repository import NoteRepository
from src.skills.notes.skill import NotesSkill
from src.skills.registry import SkillRegistry
from src.skills.reminders.repository import ReminderRepository
from src.skills.reminders.skill import RemindersSkill
from src.skills.vocabulary import help_catalog
from src.skills.web_search.skill import WebSearchSkill


def _registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(ActiveRecallSkill())
    registry.register(NotesSkill(repository=NoteRepository(user_id="u1")))
    registry.register(RemindersSkill(repository=ReminderRepository(user_id="u1")))
    registry.register(WebSearchSkill())
    return registry


def test_help_catalog_has_ten_phrases_per_skill_per_language():
    """Each language must expose exactly ten spoken phrases per skill."""
    for lang in ("en", "de", "hu"):
        catalog = help_catalog(lang)
        assert set(catalog) == {"notes", "reminders", "web_search", "active_recall"}
        for skill, phrases in catalog.items():
            assert len(phrases) == 10, f"{lang}/{skill} has {len(phrases)}"
            assert len(set(p.lower() for p in phrases)) == 10


def test_help_phrases_are_claimed_by_the_matching_skill():
    """Every catalog phrase must route to the skill it is listed under."""
    registry = _registry()
    expected = {
        "notes": "notes",
        "reminders": "reminders",
        "web_search": "web_search",
        "active_recall": "active_recall",
    }
    for lang in ("en", "de", "hu"):
        catalog = help_catalog(lang)
        for skill, phrases in catalog.items():
            for phrase in phrases:
                found = registry.find_handler(phrase)
                assert found is not None, f"{lang!r} {phrase!r} unmatched"
                assert (
                    found.name == expected[skill]
                ), f"{lang!r} {phrase!r} went to {found.name}, expected {skill}"


def test_phrases_endpoint_returns_selected_language_only():
    """Help API must return one language at a time."""
    client = TestClient(app)
    response = client.get("/api/v1/skills/phrases", params={"lang": "de"})
    assert response.status_code == 200
    data = response.json()
    assert data["lang"] == "de"
    assert "merk dir" in " ".join(data["skills"]["notes"]).lower()
    assert "remember this" not in " ".join(data["skills"]["notes"]).lower()
