"""Unit tests for detect_response_language."""

import pytest

from src.core.language import load_hungarian_given_names
from src.services.orchestrator import detect_response_language


@pytest.mark.parametrize(
    "hint,expected",
    [
        ("en", "en"),
        ("de", "de"),
        ("hu", "hu"),
        ("EN", "en"),
        ("de-DE", "de"),
        ("hu_HU", "hu"),
    ],
)
def test_explicit_hint_wins(hint: str, expected: str):
    """Explicit language hint must win when the text is ambiguous."""
    assert detect_response_language("ok", hint=hint) == expected


def test_clear_reply_overrides_stale_hint():
    """A clearly German/Hungarian reply must not keep an English STT hint."""
    assert detect_response_language("Können wir später sprechen?", hint="en") == "de"
    assert detect_response_language("Szia, mi újság? Szép az idő.", hint="en") == "hu"


def test_hungarian_unique_chars():
    """Hungarian-specific characters must select 'hu'."""
    assert detect_response_language("Szia, mi újság? Szép az idő.") == "hu"


def test_german_umlauts():
    """German umlauts must select 'de'."""
    assert detect_response_language("Können wir später sprechen?") == "de"


def test_german_word_markers():
    """Common German function words must select 'de'."""
    assert detect_response_language("Ich bin bereit und das ist gut") == "de"


def test_german_utterance_beats_english_hint():
    """Autodetect: clearly German text must not stay English because of a hint."""
    assert detect_response_language("Ich bin bereit und das ist gut", hint="en") == "de"
    assert detect_response_language("Wie geht es dir?", hint="en") == "de"


def test_english_utterance_beats_german_hint():
    """Autodetect: clearly English text must not stay German because of a hint."""
    assert detect_response_language("Hello, how are you today?", hint="de") == "en"


def test_english_story_beats_stale_hungarian_hint():
    """Walk: an English story request must not keep a Whisper/session HU hint."""
    assert (
        detect_response_language("Tell me a short story about Leipzig", hint="hu")
        == "en"
    )


def test_short_hungarian_agenda_beats_english_hint():
    """Walk: 'Mi van ma?' has no unique letters and must still be Hungarian."""
    assert detect_response_language("Mi van ma?", hint="en") == "hu"
    assert detect_response_language("Mi van ma?") == "hu"


def test_german_note_trigger_beats_english_hint():
    """Walk: a DE note request after EN chat must not stay English."""
    assert detect_response_language("Notiz: kaufe Milch", hint="en") == "de"


def test_english_reminder_with_listed_name_beats_hungarian_hint():
    """Walk: Ákos in an English reminder must not select Hungarian."""
    text = "Remind me in two minutes to stretch, Ákos"
    assert detect_response_language(text, hint="hu") == "en"
    assert detect_response_language(text) == "en"


def test_hungarian_word_markers():
    """Common Hungarian function words must select 'hu'."""
    assert detect_response_language("Nem tudom, hogy mi van") == "hu"


def test_english_default():
    """Plain English text must default to 'en'."""
    assert detect_response_language("Hello, how are you today?") == "en"


def test_empty_text_defaults_to_en():
    """Empty text must default to 'en'."""
    assert detect_response_language("") == "en"


def test_unknown_hint_falls_through_to_heuristics():
    """Unknown hint must be ignored so character heuristics can decide."""
    # Unknown hint ignored → German umlauts decide
    assert detect_response_language("Schöne Grüße", hint="fr") == "de"


def test_german_mit_does_not_select_hungarian():
    """German 'mit' must not be classified as Hungarian, even without a hint."""
    assert detect_response_language("Meeting mit Anna") == "de"
    assert detect_response_language("Meeting mit Anna", hint="de") == "de"


def test_english_van_does_not_select_hungarian():
    """English 'van' must stay English, not Hungarian."""
    assert detect_response_language("I parked the van") == "en"
    assert detect_response_language("I parked the van", hint="en") == "en"


def test_hint_wins_over_a_single_function_word():
    """A UI/STT hint must beat one ambiguous function word without unique letters."""
    assert detect_response_language("ok mit", hint="de") == "de"
    assert detect_response_language("ok", hint="hu") == "hu"


def test_hungarian_with_shared_umlauts_is_not_german():
    """ö/ü exist in both languages; Hungarian text must not become German."""
    assert detect_response_language("Köszönöm") == "hu"
    assert detect_response_language("Köszönöm", hint="hu") == "hu"
    assert detect_response_language("Köszönöm", hint="en") == "hu"


def test_hungarian_acute_accents_select_hungarian():
    """áéíóú in Hungarian words (not names) must select hu without ő/ű."""
    assert detect_response_language("Emlékeztess holnap a fogorvosra") == "hu"
    assert detect_response_language("jegyzeteld: tej", hint="en") == "hu"


def test_listed_hungarian_name_does_not_select_hungarian_in_english():
    """Listed names with áéíóú must not switch an English reply to HU TTS."""
    reply = "Got it, Ákosh! I'll stick to English from now on."
    assert detect_response_language(reply, hint="en") == "en"
    assert detect_response_language(reply) == "en"


def test_unlisted_display_name_is_ignored_when_passed():
    """A display name not on the list must still be strippable via ignore."""
    assert (
        detect_response_language(
            "Hello Áxel, how are you today?",
            hint="en",
            ignore="Áxel",
        )
        == "en"
    )
    assert detect_response_language("Hello Áxel, how are you today?", hint="en") == "hu"


def test_hungarian_hint_survives_shared_umlauts():
    """A Hungarian UI/STT hint must win when the only special letters are ö/ü."""
    assert detect_response_language("örülök", hint="hu") == "hu"


def test_hungarian_given_name_lists_are_accented_top_100():
    """Male and female lists must each hold 100 names containing Hungarian accents."""
    letters = set("áéíóúöüőűÁÉÍÓÚÖÜŐŰ")
    male, female = load_hungarian_given_names()
    assert len(male) == 100
    assert len(female) == 100
    assert len(set(n.casefold() for n in male)) == 100
    assert len(set(n.casefold() for n in female)) == 100
    assert not set(n.casefold() for n in male) & set(n.casefold() for n in female)
    for name in (*male, *female):
        assert any(c in letters for c in name), name
    assert "Ákosh" in male
    assert "Ákos" in male
    assert "Mária" in female
