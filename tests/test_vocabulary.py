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
            assert len(phrases) >= 10, f"{lang}/{skill} has {len(phrases)}"
            assert len(set(p.lower() for p in phrases)) == len(phrases)


def test_name_questions_route_to_recall_not_web_search():
    """Identity questions must not be stolen by the 'what is' web-search trigger."""
    registry = _registry()
    for text in (
        "What is my name?",
        "what's my name",
        "I have asked what my name is",
        "Wie heiße ich?",
        "wie ist mein Name",
        "Mi a nevem?",
        "hogy hívnak",
    ):
        found = registry.find_handler(text)
        assert found is not None, text
        assert found.name == "active_recall", f"{text!r} went to {found.name}"


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
    assert len(data["skills"]["personal_facts"]) >= 10


def test_help_catalog_unknown_language_falls_back_to_english():
    """An unknown lang code must still return the English catalog."""
    catalog = help_catalog("xx")
    assert catalog["notes"][0].lower() == help_catalog("en")["notes"][0].lower()


def test_hungarian_inflected_and_gappy_reminders_route():
    """Agglutinating / gappy HU reminder utterances must still hit reminders."""
    registry = _registry()
    for text in (
        "emlékeztetnél holnap a fogorvosra",
        "állíts be kérlek egy emlékeztetőt a fogorvosra",
        "állíts be kérlek egy új emlékeztetőt",
        "állíts be kérlek egy újabb emlékeztetőt",
        "állíts be kérlek egy további emlékeztetőt",
        "mutasd az emlékeztetőimet",
        "emlekeztess holnap",
    ):
        found = registry.find_handler(text)
        assert found is not None, text
        assert found.name == "reminders", text


def test_german_reminder_create_is_not_stolen_by_recall():
    """'Erinnere mich an …' must create a reminder, not run Active Recall."""
    registry = _registry()
    found = registry.find_handler("Erinnere mich an den Zahnarzt morgen")
    assert found is not None
    assert found.name == "reminders"


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
