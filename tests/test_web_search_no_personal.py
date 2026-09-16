"""Slice-Brief 10: WebSearch replies must not include a personal SM block.

No EN/DE/HU personal headers (``Based on what I know about you`` /
``Basierend auf dem, was ich über dich weiß`` / ``A rólad tudottak alapján``)
and no SM fact bullets. Web results (+ honest empty/fail) only.
ActiveRecall about-you remains the personal-fact surface (control twin).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.memory import SemanticMemoryFact
from src.skills.active_recall.skill import ActiveRecallSkill
from src.skills.web_search.skill import WebSearchSkill

_NOW = datetime(2026, 9, 16, 8, 0, tzinfo=UTC)
_TRAINING = "User has a training deadline on Friday."
_PERSONAL_HEADERS = (
    "based on what i know about you",
    "basierend auf dem, was ich über dich weiß",
    "a rólad tudottak alapján",
)


class FakeSearchClient:
    def __init__(self) -> None:
        self.results = [
            {
                "title": "Retrieval-augmented generation",
                "href": "https://example.com/rag",
                "body": "RAG combines retrieval with generation.",
            }
        ]
        self.last_query: str | None = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        self.last_query = query
        return self.results[:max_results]


def _sm_with_training() -> MagicMock:
    mock_sem = MagicMock()
    fact = SemanticMemoryFact(
        user_id="u1",
        content=_TRAINING,
        importance_score=0.8,
        entities_involved=[],
        created_at=_NOW,
        last_accessed=_NOW,
    )
    mock_sem.search = AsyncMock(return_value=[fact])
    return mock_sem


def _assert_no_personal_block(text: str) -> None:
    lower = text.casefold()
    for header in _PERSONAL_HEADERS:
        assert header not in lower, f"personal header leaked: {header!r} in {text!r}"
    assert "training deadline" not in lower, f"SM fact leaked into web reply: {text!r}"
    assert _TRAINING.casefold() not in lower


@pytest.mark.asyncio
async def test_web_search_omits_personal_sm_block_english():
    """Web search with SM facts must not print personal header or fact text."""
    skill = WebSearchSkill(
        client=FakeSearchClient(), semantic_memory=_sm_with_training()
    )
    result = await skill.execute(
        user_text="search for RAG retrieval augmented generation",
        user_id="u1",
        language="en",
    )
    assert result.handled is True
    _assert_no_personal_block(result.response_text)
    assert "web results" in result.response_text.casefold()
    assert "retrieval-augmented" in result.response_text.casefold()


@pytest.mark.asyncio
async def test_web_search_omits_personal_sm_block_german():
    """German web search must not use the DE personal header or SM bullets."""
    skill = WebSearchSkill(
        client=FakeSearchClient(), semantic_memory=_sm_with_training()
    )
    result = await skill.execute(
        user_text="suche nach KI Retrieval Augmented Generation",
        user_id="u1",
        language="de",
    )
    assert result.handled is True
    _assert_no_personal_block(result.response_text)
    assert (
        "web-ergebnisse" in result.response_text.casefold()
        or "ergebnisse" in result.response_text.casefold()
    )


@pytest.mark.asyncio
async def test_web_search_results_header_still_present_control():
    """Control twin: when results exist, the web-results listing remains."""
    skill = WebSearchSkill(
        client=FakeSearchClient(), semantic_memory=_sm_with_training()
    )
    result = await skill.execute(
        user_text="look up quantum computing",
        user_id="u1",
        language="en",
    )
    assert result.handled is True
    lower = result.response_text.casefold()
    assert "web results" in lower
    assert "example.com/rag" in lower or "retrieval" in lower
    _assert_no_personal_block(result.response_text)


@pytest.mark.asyncio
async def test_active_recall_still_shows_personal_facts_control():
    """Control twin: ActiveRecall about-you still surfaces real personal facts."""
    mock_sem = _sm_with_training()
    skill = ActiveRecallSkill(semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="What do you know about me?",
        user_id="u1",
        display_name="Ákosh",
        language="en",
    )
    assert result.handled is True
    assert "training deadline" in result.response_text.casefold()
