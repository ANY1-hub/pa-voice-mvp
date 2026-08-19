"""Unit tests for WebSearchSkill (memory-augmented DuckDuckGo)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
    """Skill must claim clear search utterances and reject unrelated chat."""
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
    """Happy path: a valid query must return formatted results and a cleaned query."""
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
    """Search intent without actual terms must not call the engine; ask for clarification instead."""
    skill = WebSearchSkill(client=FakeSearchClient())
    result = await skill.execute(user_text="search for", user_id="u1")
    assert result.handled is True
    assert (
        "need" in result.response_text.lower()
        or "query" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_no_results():
    """When the search backend returns an empty list, the skill must report that clearly."""
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
    """Relevant personal facts from Semantic Memory must appear in the reply."""
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
    assert (
        "vegetarian" in result.response_text.lower()
        or "prefer" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_german_search_replies_in_german():
    """German search utterances must use German framing around the results."""
    client = FakeSearchClient()
    skill = WebSearchSkill(client=client, semantic_memory=None)

    result = await skill.execute(
        user_text="suche nach dem Wetter in Berlin",
        user_id="u1",
        language="de",
    )
    assert result.handled is True
    assert (
        "Web-Ergebnisse" in result.response_text or "Ergebnisse" in result.response_text
    )
    assert "Web results for" not in result.response_text


@pytest.mark.asyncio
async def test_execute_writes_summary_to_semantic_memory():
    """After a successful search a short summary fact must be written to Semantic Memory."""
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
    """Skill must be findable by name and by intent through the SkillRegistry."""
    registry = SkillRegistry()
    skill = WebSearchSkill(client=FakeSearchClient())
    registry.register(skill)

    assert registry.get("web_search") is skill
    found = registry.find_handler("search for the latest news")
    assert found is skill


# ---------------------------------------------------------------------------
# Error / resilience paths
# ---------------------------------------------------------------------------


class RaisingSearchClient:
    """Search client that always fails – used to test skill error handling."""

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        raise RuntimeError("network down")


@pytest.mark.asyncio
async def test_execute_backend_failure_returns_friendly_message():
    """If the search backend crashes, the user must get a clear apology – not a stack trace."""
    skill = WebSearchSkill(client=RaisingSearchClient(), semantic_memory=None)

    result = await skill.execute(
        user_text="search for the capital of France",
        user_id="u1",
    )

    assert result.handled is True
    assert (
        "failed" in result.response_text.lower()
        or "sorry" in result.response_text.lower()
    )


@pytest.mark.asyncio
async def test_execute_continues_when_semantic_search_fails():
    """A broken Semantic Memory must not kill the web search – results still come back."""
    client = FakeSearchClient()
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(side_effect=RuntimeError("db timeout"))
    mock_sem.add_fact = AsyncMock()

    skill = WebSearchSkill(client=client, semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="search for good restaurants in Berlin",
        user_id="u1",
    )

    assert result.handled is True
    assert (
        "Example Result" in result.response_text
        or "example.com" in result.response_text
    )


@pytest.mark.asyncio
async def test_execute_continues_when_add_fact_fails():
    """If writing the search summary to memory fails, the user must still see the web results."""
    client = FakeSearchClient()
    mock_sem = MagicMock()
    mock_sem.search = AsyncMock(return_value=[])
    mock_sem.add_fact = AsyncMock(side_effect=RuntimeError("write denied"))

    skill = WebSearchSkill(client=client, semantic_memory=mock_sem)
    result = await skill.execute(
        user_text="search for Python asyncio",
        user_id="u1",
    )

    assert result.handled is True
    assert (
        "Example Result" in result.response_text
        or "example.com" in result.response_text
    )
    mock_sem.add_fact.assert_awaited_once()


# ---------------------------------------------------------------------------
# DuckDuckGoClient (production client, fully mocked – no network)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ddg_client_maps_results():
    """DuckDuckGoClient must map raw DDGS dicts into title/href/body and ignore extra keys."""
    from src.skills.web_search.client import DuckDuckGoClient

    raw = [
        {
            "title": "Python Docs",
            "href": "https://docs.python.org",
            "body": "Official documentation",
            "extra": "ignored",
        }
    ]

    with patch("src.skills.web_search.client.asyncio.to_thread") as mock_thread:
        # to_thread runs the sync function; we call it ourselves and return its result
        async def run_sync(fn):
            return fn()

        mock_thread.side_effect = run_sync

        with patch.dict("sys.modules", {"ddgs": MagicMock()}):
            import sys

            mock_ddgs_mod = sys.modules["ddgs"]
            mock_ddgs_inst = MagicMock()
            mock_ddgs_inst.text.return_value = raw
            mock_ddgs_mod.DDGS.return_value = mock_ddgs_inst

            client = DuckDuckGoClient()
            results = await client.search("python", max_results=3)

    assert len(results) == 1
    assert results[0] == {
        "title": "Python Docs",
        "href": "https://docs.python.org",
        "body": "Official documentation",
    }


@pytest.mark.asyncio
async def test_ddg_client_exception_propagates():
    """If the DDGS library raises, the client must propagate so the skill can report failure."""
    from src.skills.web_search.client import DuckDuckGoClient

    with patch("src.skills.web_search.client.asyncio.to_thread") as mock_thread:

        async def run_sync(fn):
            return fn()

        mock_thread.side_effect = run_sync

        with patch.dict("sys.modules", {"ddgs": MagicMock()}):
            import sys

            mock_ddgs_mod = sys.modules["ddgs"]
            mock_ddgs_inst = MagicMock()
            mock_ddgs_inst.text.side_effect = RuntimeError("ddgs boom")
            mock_ddgs_mod.DDGS.return_value = mock_ddgs_inst

            client = DuckDuckGoClient()
            with pytest.raises(RuntimeError, match="ddgs boom"):
                await client.search("anything")
