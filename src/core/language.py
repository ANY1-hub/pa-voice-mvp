"""Language heuristics for TTS voice selection and skill replies."""

from __future__ import annotations

import re

_HU_CHARS = set("őűŐŰ")
_DE_CHARS = set("äöüÄÖÜß")
_HU_WORDS = re.compile(
    r"\b(hogy|nem|egy|és|vagy|ez|az|igen|köszönöm|szia|tudom|rólam|kérem)\b",
    re.IGNORECASE,
)
_DE_WORDS = re.compile(
    r"\b(und|der|die|das|ich|nicht|ist|ein|eine|mit|für|auf)\b",
    re.IGNORECASE,
)


def heuristic_language(text: str) -> str | None:
    """Return a language code from function words, or None.

    Unique letters are handled in ``detect_response_language`` so a single
    ambiguous word cannot override an STT/UI hint.
    """
    if _HU_WORDS.search(text):
        return "hu"
    if _DE_WORDS.search(text):
        return "de"
    return None


def detect_response_language(text: str, hint: str | None = None) -> str:
    """Guess language for TTS / skill replies.

    Unique letters (őű / äöüß) beat a stale hint so a German reply is not
    spoken with the English voice. A UI/STT hint otherwise wins over a single
    function word such as German ``mit`` or English ``van``.

    Args:
        text: User or assistant text to inspect.
        hint: Optional language code from STT (``"en"``, ``"de"``, ``"hu"``).

    Returns:
        One of ``"en"``, ``"de"``, ``"hu"``.
    """
    if any(c in _HU_CHARS for c in text):
        return "hu"
    if any(c in _DE_CHARS for c in text):
        return "de"

    if hint:
        code = hint.lower().strip()[:2]
        if code in {"en", "de", "hu"}:
            return code

    return heuristic_language(text) or "en"
