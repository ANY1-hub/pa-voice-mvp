"""Extract durable personal facts from a chat utterance (LLM JSON)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from src.core.language import detect_response_language
from src.services.llm.base import LLMAdapter
from src.skills.vocabulary import PERSONAL_FACTS, compile_phrase_regex

logger = logging.getLogger(__name__)

FACT_IMPORTANCE = 0.75
ADDRESS_FACT_PREFIX = "The user prefers to be addressed as"

# Cheap gate so greetings do not pay a second LLM call.
_PERSONAL_CUE = re.compile(
    r"\b("
    r"i am|i'm|i m|my |mine |i like|i love|i live|i work|i have|"
    r"ich bin|ich heiße|ich heisse|ich mag|ich liebe|mein |meine |"
    r"ich wohne|ich arbeite|"
    r"én |az én |a nevem|szeretek|lakom|dolgozom"
    r")\b",
    re.IGNORECASE,
)
_PERSONAL_PHRASE = compile_phrase_regex(PERSONAL_FACTS)

_EXTRACT_SYSTEM = """You extract durable personal facts the USER stated about themselves.
Return JSON only: {"facts":[{"content":"...","entities":["..."]}]}
Rules:
- Keep the fact in the user's original language. Do not translate.
- 0 to 3 facts. Identity, preferences, relationships, job, home, allergies, constraints.
- Skip greetings, questions, one-off tasks, reminders, and anything not about the user.
- content must be a short standalone sentence (e.g. "User likes oat milk").
- If nothing durable was stated, return {"facts":[]}.
"""


@dataclass(frozen=True)
class ExtractedFact:
    """One durable personal fact ready for Semantic Memory."""

    content: str
    entities: list[str]
    language: str


def looks_personal(text: str) -> bool:
    """True when the utterance likely contains a first-person personal fact."""
    text = text or ""
    return bool(_PERSONAL_CUE.search(text) or _PERSONAL_PHRASE.search(text))


async def extract_personal_facts(
    llm: LLMAdapter,
    user_text: str,
) -> list[ExtractedFact]:
    """Ask the LLM for personal facts. Empty list on failure or no facts."""
    if not looks_personal(user_text):
        return []

    language = detect_response_language(user_text)
    messages = [
        {"role": "system", "content": _EXTRACT_SYSTEM},
        {"role": "user", "content": user_text},
    ]
    try:
        raw = await llm.generate_response(
            messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(raw or "{}")
    except Exception:
        logger.exception("Personal-fact extraction failed")
        return []

    items = data.get("facts")
    if not isinstance(items, list):
        return []

    facts: list[ExtractedFact] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str) or len(content.strip()) < 4:
            continue
        entities = item.get("entities") or []
        if not isinstance(entities, list):
            entities = []
        names = [str(e).strip() for e in entities if str(e).strip()]
        facts.append(
            ExtractedFact(
                content=content.strip(),
                entities=names,
                language=language,
            )
        )
    return facts
