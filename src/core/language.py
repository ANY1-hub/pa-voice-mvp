"""Language heuristics for TTS voice selection and skill replies."""

from __future__ import annotations

import re

_HU_CHARS = set("őűŐŰ")
_DE_CHARS = set("äöüÄÖÜß")
_HU_WORDS = re.compile(
    r"\b(hogy|nem|van|egy|és|vagy|mit|ez|az|igen|köszönöm)\b",
    re.IGNORECASE,
)
_DE_WORDS = re.compile(
    r"\b(und|der|die|das|ich|nicht|ist|ein|eine|mit|für|auf)\b",
    re.IGNORECASE,
)


def heuristic_language(text: str) -> str | None:
    """Return a language code from unique chars / function words, or None."""
    if any(c in _HU_CHARS for c in text):
        return "hu"
    if any(c in _DE_CHARS for c in text):
        return "de"
    if _HU_WORDS.search(text):
        return "hu"
    if _DE_WORDS.search(text):
        return "de"
    return None


def detect_response_language(text: str, hint: str | None = None) -> str:
    """Guess language for TTS / skill replies.

    Strong character/word evidence in ``text`` beats a stale hint so a German
    reply is not spoken with the English voice. An explicit hint still wins
    when the text is ambiguous.

    Args:
        text: User or assistant text to inspect.
        hint: Optional language code from STT (``"en"``, ``"de"``, ``"hu"``).

    Returns:
        One of ``"en"``, ``"de"``, ``"hu"``.
    """
    heuristic = heuristic_language(text)
    if heuristic in {"de", "hu"}:
        return heuristic

    if hint:
        code = hint.lower().strip()[:2]
        if code in {"en", "de", "hu"}:
            return code

    return heuristic or "en"
