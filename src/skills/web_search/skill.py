"""WebSearchSkill – memory-augmented web search via DuckDuckGo."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.memory.semantic_memory import SemanticMemory
from src.skills.base import Skill, SkillResult
from src.skills.web_search.client import DuckDuckGoClient, SearchClient

logger = logging.getLogger(__name__)

_SEARCH_PATTERNS = re.compile(
    r"\b("
    r"search|google|look up|lookup|find out|what is|who is|what's|"
    r"suche|finde|nachschlagen|was ist|wer ist|"
    r"keress|keresés|mi az|ki az"
    r")\b",
    re.IGNORECASE,
)

_TRIGGER_PHRASES = [
    # longer phrases first – order matters
    r"^(search for|look up|find out|google for|suche nach|finde heraus|keress rá| keresd meg)\s*",
    r"^(search|google|look up|lookup|find out|suche|finde|keress|"
    r"what is|who is|what's|was ist|wer ist|mi az|ki az)\s*",
]


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
        return bool(_SEARCH_PATTERNS.search(text))

    async def execute(
        self,
        user_text: str,
        user_id: str,
        **deps: Any,
    ) -> SkillResult:
        query = self._extract_query(user_text)
        if len(query) < 2:
            return SkillResult(
                response_text="I need a clearer search query.",
                handled=True,
            )
        return await self._run_search(query)

    def _extract_query(self, user_text: str) -> str:
        """Remove known trigger phrases, return the remaining substance."""
        text = user_text.strip()
        for pat in _TRIGGER_PHRASES:
            text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()
        return text.strip(" :,-?")

    async def _run_search(self, query: str) -> SkillResult:
        """Fetch personal context + web results and build the reply."""
        personal_bits = await self._fetch_personal_context(query)
        results = await self._fetch_web_results(query)

        if results is None:
            return SkillResult(
                response_text="Sorry, the web search failed. Please try again later.",
                handled=True,
            )
        if not results:
            return SkillResult(
                response_text=f"I could not find any results for “{query}”.",
                handled=True,
            )

        response_text = self._format_response(query, personal_bits, results)
        summary = await self._maybe_write_summary(query, results)

        return SkillResult(
            response_text=response_text,
            handled=True,
            memory_writes=[{"content": summary, "importance": 0.45}] if summary else [],
        )

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
    ) -> str:
        lines: list[str] = []
        if personal_bits:
            lines.append("Based on what I know about you:")
            for bit in personal_bits[:2]:
                lines.append(f"• {bit[:120]}")
            lines.append("")

        lines.append(f"Web results for “{query}”:")
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

    async def _maybe_write_summary(
        self,
        query: str,
        results: list[dict[str, str]],
    ) -> str | None:
        top_title = results[0].get("title") or query
        summary = f"User searched for “{query}”. Top result: {top_title[:120]}"
        if self.semantic_memory is None:
            return summary
        try:
            await self.semantic_memory.add_fact(
                fact=summary,
                importance=0.45,
                entities=["web_search", "search"],
            )
        except Exception:
            logger.exception("Failed to write search summary to semantic memory")
        return summary
