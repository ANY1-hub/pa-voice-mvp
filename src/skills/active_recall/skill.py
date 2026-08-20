"""ActiveRecallSkill – answer explicit "what do you know about X" questions from Semantic Memory."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.models.memory import SemanticMemoryFact
from src.skills.base import Skill, SkillResult
from src.skills.replies import reply_language, t
from src.skills.vocabulary import (
    ACTIVE_RECALL,
    ACTIVE_RECALL_EXTRA,
    NAME_RECALL_PHRASES,
    compile_phrase_regex,
)

logger = logging.getLogger(__name__)

_TRIGGER_RE = compile_phrase_regex(ACTIVE_RECALL, extra=ACTIVE_RECALL_EXTRA)
_NAME_RE = compile_phrase_regex(extra=NAME_RECALL_PHRASES)

_FILLER_RE = re.compile(
    r"^(about|über|an|zu|von|regarding|concerning)\s+",
    re.IGNORECASE,
)

_REPLIES: dict[str, dict[str, str]] = {
    "en": {
        "no_memory": "I have no long-term memory available right now.",
        "lookup_fail": "Sorry, I could not look that up right now.",
        "empty_topic": "I don't have anything stored about '{query}' yet.",
        "empty_all": "I don't have any personal facts stored yet.",
        "header_topic": "Here's what I know about {query}:",
        "header_you": "Here's what I know about you:",
    },
    "de": {
        "no_memory": "Ich habe gerade kein Langzeitgedächtnis.",
        "lookup_fail": "Sorry, ich konnte das gerade nicht nachschlagen.",
        "empty_topic": "Dazu habe ich noch nichts gespeichert: '{query}'.",
        "empty_all": "Ich habe noch keine persönlichen Fakten gespeichert.",
        "header_topic": "Das weiß ich über {query}:",
        "header_you": "Das weiß ich über dich:",
    },
    "hu": {
        "no_memory": "Most nincs elérhető hosszú távú memóriám.",
        "lookup_fail": "Sajnos most nem tudtam ezt megnézni.",
        "empty_topic": "Erről még nincs tárolt infóm: '{query}'.",
        "empty_all": "Még nincsenek személyes tényeid tárolva.",
        "header_topic": "Ezt tudom erről: {query}:",
        "header_you": "Ezt tudom rólad:",
    },
}


class ActiveRecallSkill(Skill):
    """Explicit active recall of personal facts stored in Semantic Memory.

    Triggers on clear recall intents and returns ranked facts without going
    through the full LLM path. Keeps the Orchestrator thin.
    """

    name = "active_recall"

    def __init__(self, semantic_memory: SemanticMemory | None = None) -> None:
        self.semantic_memory = semantic_memory

    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        text = user_text.strip()
        if not text:
            return False
        return bool(_TRIGGER_RE.search(text))

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        query = self._extract_query(user_text)
        lang = reply_language(user_text, deps)

        if self.semantic_memory is None:
            return SkillResult(
                response_text=t(_REPLIES, lang, "no_memory"),
                handled=True,
            )

        try:
            facts = await self.semantic_memory.search(query=query, limit=6)
        except Exception:
            logger.exception("Active recall search failed")
            return SkillResult(
                response_text=t(_REPLIES, lang, "lookup_fail"),
                handled=True,
            )

        return self._format_response(query, facts, lang)

    def _extract_query(self, user_text: str) -> str:
        """Strip trigger phrases and light fillers; return the topic."""
        if _NAME_RE.search(user_text):
            return ""
        text = user_text.strip()
        # Remove the first matching trigger phrase
        text = _TRIGGER_RE.sub("", text, count=1).strip(" :?,-").strip()
        text = _FILLER_RE.sub("", text).strip()
        return text

    def _format_response(
        self,
        query: str,
        facts: list[SemanticMemoryFact],
        lang: str,
    ) -> SkillResult:
        if not facts:
            if query:
                msg = t(_REPLIES, lang, "empty_topic", query=query)
            else:
                msg = t(_REPLIES, lang, "empty_all")
            return SkillResult(response_text=msg, handled=True)

        lines = [f"- {f.content}" for f in facts]
        body = "\n".join(lines)

        you_tokens = {"me", "mich", "mir", "rólam", "nekem"}
        if query and query.lower() not in you_tokens:
            header = t(_REPLIES, lang, "header_topic", query=query)
        else:
            header = t(_REPLIES, lang, "header_you")

        return SkillResult(
            response_text=f"{header}\n{body}",
            handled=True,
        )
