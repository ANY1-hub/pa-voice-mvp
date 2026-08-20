"""WebSearchSkill – memory-augmented web search via DuckDuckGo."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.skills.base import Skill, SkillResult
from src.skills.replies import reply_language, t
from src.skills.vocabulary import (
    NAME_RECALL_PHRASES,
    WEB_SEARCH,
    WEB_SEARCH_EXTRA,
    compile_phrase_regex,
)
from src.skills.web_search.client import DuckDuckGoClient, SearchClient

logger = logging.getLogger(__name__)

_SEARCH_PATTERNS = compile_phrase_regex(WEB_SEARCH, extra=WEB_SEARCH_EXTRA)

# "what is" / "was ist" / "mi az" must not steal identity questions from recall.
_PERSONAL_IDENTITY = compile_phrase_regex(extra=NAME_RECALL_PHRASES)

_STRIP_PHRASES = sorted(
    {p for items in WEB_SEARCH.values() for p in items} | set(WEB_SEARCH_EXTRA),
    key=len,
    reverse=True,
)
_TRIGGER_PHRASES = [r"^" + re.escape(p) + r"\s*" for p in _STRIP_PHRASES]

_REPLIES: dict[str, dict[str, str]] = {
    "en": {
        "need_query": "I need a clearer search query.",
        "fail": "Sorry, the web search failed. Please try again later.",
        "no_results": "I could not find any results for “{query}”.",
        "personal": "Based on what I know about you:",
        "results": "Web results for “{query}”:",
    },
    "de": {
        "need_query": "Ich brauche eine klarere Suchanfrage.",
        "fail": "Sorry, die Websuche ist fehlgeschlagen. Bitte versuche es später.",
        "no_results": "Ich konnte keine Ergebnisse für „{query}“ finden.",
        "personal": "Basierend auf dem, was ich über dich weiß:",
        "results": "Web-Ergebnisse für „{query}“:",
    },
    "hu": {
        "need_query": "Kell egy egyértelműbb keresőkifejezés.",
        "fail": "Sajnos a webes keresés nem sikerült. Próbáld később.",
        "no_results": "Nem találtam találatot erre: „{query}”.",
        "personal": "A rólad tudottak alapján:",
        "results": "Webes találatok erre: „{query}”:",
    },
}


class WebSearchSkill(Skill):
    """Perform a web search and weave in personal Semantic Memory context."""

    name = "web_search"

    def __init__(
        self,
        client: SearchClient | None = None,
        semantic_memory: SemanticMemory | None = None,
    ) -> None:
        self.client = client or DuckDuckGoClient()
        self.semantic_memory = semantic_memory

    def can_handle(self, user_text: str, context: dict[str, Any] | None = None) -> bool:
        text = user_text.strip()
        if not text:
            return False
        if _PERSONAL_IDENTITY.search(text):
            return False
        return bool(_SEARCH_PATTERNS.search(text))

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        query = self._extract_query(user_text)
        lang = reply_language(user_text, deps)
        if len(query) < 2:
            return SkillResult(
                response_text=t(_REPLIES, lang, "need_query"),
                handled=True,
            )
        return await self._run_search(query, lang)

    def _extract_query(self, user_text: str) -> str:
        """Remove the first matching trigger prefix, return the remaining substance."""
        text = user_text.strip()
        for pat in _TRIGGER_PHRASES:
            stripped = re.sub(pat, "", text, count=1, flags=re.IGNORECASE).strip()
            if stripped != text:
                return stripped.strip(" :,-?")
        return text.strip(" :,-?")

    async def _run_search(self, query: str, lang: str) -> SkillResult:
        """Fetch personal context + web results and build the reply."""
        personal_bits = await self._fetch_personal_context(query)
        results = await self._fetch_web_results(query)

        if results is None:
            return SkillResult(
                response_text=t(_REPLIES, lang, "fail"),
                handled=True,
            )
        if not results:
            return SkillResult(
                response_text=t(_REPLIES, lang, "no_results", query=query),
                handled=True,
            )

        response_text = self._format_response(query, personal_bits, results, lang)
        return SkillResult(response_text=response_text, handled=True)

    async def _fetch_personal_context(self, query: str) -> list[str]:
        if self.semantic_memory is None:
            return []
        try:
            facts = await self.semantic_memory.search(query=query, limit=3)
            return [f.content for f in facts if f.content]
        except Exception:
            logger.exception("Failed to retrieve semantic context for search")
            return []

    async def _fetch_web_results(self, query: str) -> list[dict[str, str]] | None:
        try:
            return await self.client.search(query, max_results=5)
        except Exception:
            logger.exception("Web search failed")
            return None

    def _format_response(
        self,
        query: str,
        personal_bits: list[str],
        results: list[dict[str, str]],
        lang: str,
    ) -> str:
        lines: list[str] = []
        if personal_bits:
            lines.append(t(_REPLIES, lang, "personal"))
            for bit in personal_bits[:2]:
                lines.append(f"• {bit[:120]}")
            lines.append("")

        lines.append(t(_REPLIES, lang, "results", query=query))
        for i, r in enumerate(results[:4], 1):
            title = r.get("title") or "Result"
            body = (r.get("body") or "")[:100]
            href = r.get("href") or ""
            entry = f"{i}. {title}"
            if body:
                entry += f" – {body}"
            if href:
                entry += f" ({href})"
            lines.append(entry)
        return "\n".join(lines)
