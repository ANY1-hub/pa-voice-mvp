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
    """Explicit language hint must override text heuristics."""
    # Text looks German, but hint must win
    assert detect_response_language("Das ist ein Test", hint=hint) == expected


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
