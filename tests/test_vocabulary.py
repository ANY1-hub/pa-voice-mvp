"""Canonical trigger phrases must match the intended skill in EN/DE/HU."""

from fastapi.testclient import TestClient

from src.main import app
from src.services.memory_facts import looks_personal
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
        assert set(catalog) == {
            "notes",
            "reminders",
            "web_search",
            "active_recall",
            "personal_facts",
        }
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
            if skill == "personal_facts":
                continue
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
    assert "personal_facts" in data["skills"]
    assert len(data["skills"]["personal_facts"]) == 10


def test_help_catalog_unknown_language_falls_back_to_english():
    """An unknown lang code must still return the English catalog."""
    catalog = help_catalog("xx")
    assert catalog["notes"][0].lower() == help_catalog("en")["notes"][0].lower()


def test_personal_fact_phrases_are_not_stolen_by_skills():
    """Memory phrases must reach the LLM path, not Notes/Reminders/Search/Recall."""
    registry = _registry()
    for lang in ("en", "de", "hu"):
        for phrase in help_catalog(lang)["personal_facts"]:
            assert looks_personal(phrase) is True, phrase
            found = registry.find_handler(phrase)
            assert (
                found is None
            ), f"{lang!r} {phrase!r} stolen by {getattr(found, 'name', None)}"
