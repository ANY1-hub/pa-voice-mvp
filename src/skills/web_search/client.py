"""Thin async wrapper around DuckDuckGo search (ddgs)."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class SearchClient(Protocol):
    """Protocol for web search backends (easy to mock)."""

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Return a list of result dicts with title, href, body."""
        ...


class DuckDuckGoClient:
    """Production client using the ``ddgs`` package."""

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Run a DuckDuckGo text search in a worker thread.

        Args:
            query: Search query.
            max_results: Maximum number of results to return.

        Returns:
            List of dicts with keys ``title``, ``href``, ``body``.
        """

        def _sync_search() -> list[dict[str, str]]:
            try:
                from ddgs import DDGS

                raw = DDGS().text(query, max_results=max_results)
                return [
                    {
                        "title": r.get("title") or "",
                        "href": r.get("href") or "",
                        "body": r.get("body") or "",
                    }
                    for r in raw
                ]
            except Exception:
                logger.exception("DuckDuckGo search failed")
                return []

        return await asyncio.to_thread(_sync_search)
