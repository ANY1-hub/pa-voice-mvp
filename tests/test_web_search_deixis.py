"""Bare deictic questions must not claim WebSearch; real lookups still do.

Slice-Brief 1 (2026-09-09): after a search-trigger strip, an empty or
deixis-only remainder (das / this / that / diese[sr]? / ez / az …) must
fall through to the LLM. Control twins with a real subject must still
route to web_search. NAME_RECALL identity questions must still be
excluded. Mutation of a global vocab delete of \"was ist\"/\"what is\"/
\"mi az\" would break the control twins.
"""

from __future__ import annotations

import pytest

from src.skills.registry import SkillRegistry
from src.skills.web_search.skill import WebSearchSkill


class FakeSearchClient:
    """Deterministic search client; last_query proves whether search ran."""

    def __init__(self) -> None:
        self.last_query: str | None = None
        self.calls = 0

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        self.calls += 1
        self.last_query = query
        return [
            {
                "title": "Example",
                "href": "https://example.com",
                "body": "snippet",
            }
        ]


def _skill() -> WebSearchSkill:
    return WebSearchSkill(client=FakeSearchClient())


@pytest.mark.parametrize(
    "utterance",
    [
        "Was ist das?",
        "Was ist das",
        "What is that?",
        "What is this?",
        "Mi az?",
        "Mi az",
        "Was ist diese?",
        "Was ist dieser?",
        "What is that",
        "What is this",
    ],
)
def test_can_handle_rejects_bare_deixis(utterance: str):
    """Bare deictic What/Was/Mi questions must not claim WebSearch (LLM fallthrough)."""
    assert _skill().can_handle(utterance) is False


@pytest.mark.parametrize(
    "utterance",
    [
        "Was ist RAG?",
        "What is the capital of Hungary?",
        "What is RAG?",
        "Wer ist Angela Merkel?",
        "Who is Albert Einstein?",
        "search for the capital of France",
    ],
)
def test_can_handle_keeps_real_lookup_subjects(utterance: str):
    """Real subjects after a What/Was/Who trigger must still claim WebSearch."""
    assert _skill().can_handle(utterance) is True


@pytest.mark.parametrize(
    "utterance",
    [
        "What is my name?",
        "Wie heiße ich?",
        "Mi a nevem?",
        "was ist mein name",
    ],
)
def test_can_handle_still_excludes_personal_identity(utterance: str):
    """NAME_RECALL identity questions must still be excluded from WebSearch."""
    assert _skill().can_handle(utterance) is False


def test_registry_bare_deixis_falls_through_to_llm():
    """Registry must not select web_search for bare deixis (orchestrator LLM path)."""
    registry = SkillRegistry()
    skill = _skill()
    registry.register(skill)

    assert registry.find_handler("Was ist das?") is None
    assert registry.find_handler("What is that?") is None
    assert registry.find_handler("Mi az?") is None


def test_registry_real_lookup_still_selects_web_search():
    """Control twin: a real subject must still resolve to web_search via the registry."""
    registry = SkillRegistry()
    skill = _skill()
    registry.register(skill)

    found = registry.find_handler("Was ist RAG?")
    assert found is skill
    found_en = registry.find_handler("What is the capital of Hungary?")
    assert found_en is skill


@pytest.mark.asyncio
async def test_execute_not_reached_for_bare_deixis_via_can_handle_gate():
    """If can_handle is False, execute must not be the routing path (client unused)."""
    client = FakeSearchClient()
    skill = WebSearchSkill(client=client)
    assert skill.can_handle("Was ist das?") is False
    assert client.calls == 0
    assert client.last_query is None
