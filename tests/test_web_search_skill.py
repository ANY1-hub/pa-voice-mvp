"""Unit tests for WebSearchSkill (memory-augmented DuckDuckGo)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.skills.base import SkillResult
from src.skills.registry import SkillRegistry
from src.skills.web_search.skill import WebSearchSkill

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSearchClient:
    """Deterministic search client for unit tests."""

    def __init__(self, results: list[dict[str, str]] | None = None) -> None:
        if results is None:
            self.results = [
                {
                    "title": "Example Result",
                    "href": "https://example.com",
                    "body": "This is a short snippet about the topic.",
                }
            ]
        else:
            self.results = results
        self.last_query: str | None = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        self.last_query = query
        return self.results[:max_results]


# ---------------------------------------------------------------------------
# can_handle
# ---------------------------------------------------------------------------


def test_can_handle_search_intents():
    skill = WebSearchSkill(client=FakeSearchClient())
    assert skill.can_handle("search for the capital of France") is True
    assert skill.can_handle("google the weather tomorrow") is True
    assert skill.can_handle("look up quantum computing") is True
    assert skill.can_handle("what is the population of Berlin") is True
    assert skill.can_handle("suche nach dem Wetter") is True
    assert skill.can_handle("finde heraus was Jarvis bedeutet") is True
    assert skill.can_handle("keress rá a Python dokumentációra") is True
    assert skill.can_handle("just chatting about the weather") is False
    assert skill.can_handle("note: buy milk") is False


# ---------------------------------------------------------------------------
# execute – basic search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_returns_search_results():
    client = FakeSearchClient()
    skill = WebSearchSkill(client=client, semantic_memory=None)

    result = await skill.execute(
        user_text="search for the capital of France",
        user_id="u1",
    )

    assert isinstance(result, SkillResult)
    assert result.handled is True
    assert (
        "Example Result" in result.response_text
        or "example.com" in result.response_text
    )
    assert client.last_query is not None
    assert (
        "capital of France" in client.last_query.lower()
        or "france" in client.last_query.lower()
    )


@pytest.mark.asyncio
async def test_execute_empty_query_handled_gracefully():
    skill = WebSearchSkill(client=FakeSearchClient())
    result = await skill.execute(user_text="search for", user_id="u1")
    assert result.handled is True
    assert (
        "need" in result.response_text.lower()
        or "query" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_no_results():
    client = FakeSearchClient(results=[])
    skill = WebSearchSkill(client=client)

    result = await skill.execute(
        user_text="search for xyznonexistent123",
        user_id="u1",
    )
    assert result.handled is True
    assert (
        "no results" in result.response_text.lower()
        or "could not find" in result.response_text.lower()
    )


# ---------------------------------------------------------------------------
# Memory augmentation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_uses_semantic_memory_context():
    client = FakeSearchClient()
    mock_sem = MagicMock()
    mock_fact = MagicMock()
    mock_fact.content = "User prefers vegetarian food"
    mock_sem.search = AsyncMock(return_value=[mock_fact])
    mock_sem.add_fact = AsyncMock()

    skill = WebSearchSkill(client=client, semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="search for good restaurants in Berlin",
        user_id="u1",
    )

    assert result.handled is True
    mock_sem.search.assert_awaited()
    # Personal context should appear in the reply
    assert (
        "vegetarian" in result.response_text.lower()
        or "prefer" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_writes_summary_to_semantic_memory():
    client = FakeSearchClient()
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    mock_sem.add_fact = AsyncMock()

    skill = WebSearchSkill(client=client, semantic_memory=mock_sem)

    result = await skill.execute(
        user_text="search for Python asyncio",
        user_id="u1",
    )

    assert result.handled is True
    mock_sem.add_fact.assert_awaited_once()
    call_kwargs = mock_sem.add_fact.call_args.kwargs
    assert (
        "search" in call_kwargs["fact"].lower()
        or "python" in call_kwargs["fact"].lower()
    )


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_registry_finds_web_search():
    registry = SkillRegistry()
    skill = WebSearchSkill(client=FakeSearchClient())
    registry.register(skill)

    assert registry.get("web_search") is skill
    found = registry.find_handler("search for the latest news")
    assert found is skill
