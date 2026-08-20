"""Unit tests for detect_response_language."""

import pytest

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
    """áéíóú are Hungarian in this trio and must select hu without ő/ű."""
    assert detect_response_language("Emlékeztess holnap a fogorvosra") == "hu"
    assert detect_response_language("jegyzeteld: tej", hint="en") == "hu"


def test_hungarian_hint_survives_shared_umlauts():
    """A Hungarian UI/STT hint must win when the only special letters are ö/ü."""
    assert detect_response_language("örülök", hint="hu") == "hu"
