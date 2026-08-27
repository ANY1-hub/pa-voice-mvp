"""Localized skill reply templates."""

from __future__ import annotations

from typing import Any

from src.core.language import detect_response_language


def reply_language(user_text: str, deps: dict[str, Any] | None = None) -> str:
    """Language for a skill reply: this utterance, names stripped, then hint."""
    hint = None
    ignore = None
    if deps:
        raw = deps.get("language")
        if isinstance(raw, str):
            hint = raw
        name = deps.get("display_name")
        if isinstance(name, str):
            ignore = name
    return detect_response_language(user_text, hint=hint, ignore=ignore)


def t(table: dict[str, dict[str, str]], lang: str, key: str, **kwargs: str) -> str:
    """Format a reply template in ``lang``, falling back to English."""
    pack = table.get(lang) or table["en"]
    template = pack.get(key) or table["en"][key]
    return template.format(**kwargs) if kwargs else template
