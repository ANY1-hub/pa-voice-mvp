"""Tests for personal-fact extraction from chat utterances."""

from unittest.mock import AsyncMock

import pytest

from src.services.memory_facts import (
    FACT_IMPORTANCE,
    extract_personal_facts,
    looks_personal,
)


def test_looks_personal_detects_first_person_cues():
    """Identity/preference phrasing must trigger extraction; greetings must not."""
    assert looks_personal("My name is Tony and I like espresso") is True
    assert looks_personal("Ich heiße Anna und mag dunkles Design") is True
    assert looks_personal("Hi there") is False
    assert looks_personal("What's on today?") is False


@pytest.mark.asyncio
async def test_extract_skips_llm_when_utterance_is_not_personal():
    """Greetings must not pay a second LLM call."""
    llm = AsyncMock()
    facts = await extract_personal_facts(llm, "Hello Jarvis")
    assert facts == []
    llm.generate_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_parses_json_facts_and_keeps_language():
    """Valid JSON facts must become ExtractedFact objects in the user language."""
    llm = AsyncMock()
    llm.generate_response.return_value = (
        '{"facts":[{"content":"User likes espresso","entities":["espresso"]}]}'
    )
    facts = await extract_personal_facts(llm, "I like espresso")
    assert len(facts) == 1
    assert facts[0].content == "User likes espresso"
    assert facts[0].entities == ["espresso"]
    assert facts[0].language == "en"
    assert FACT_IMPORTANCE >= 0.7


@pytest.mark.asyncio
async def test_extract_returns_empty_on_llm_failure():
    """Extractor must swallow LLM errors and return no facts."""
    llm = AsyncMock()
    llm.generate_response.side_effect = RuntimeError("boom")
    facts = await extract_personal_facts(llm, "My name is Tony")
    assert facts == []


@pytest.mark.asyncio
async def test_extract_ignores_malformed_payloads():
    """Non-list facts, non-dict items, tiny content, and bad entities are skipped."""
    llm = AsyncMock()
    llm.generate_response.return_value = '{"facts": "nope"}'
    assert await extract_personal_facts(llm, "I like tea") == []

    llm.generate_response.return_value = '{"facts":[1, {"content": "ab"}, {"content": "User likes tea", "entities": "x"}]}'
    facts = await extract_personal_facts(llm, "I like tea")
    assert len(facts) == 1
    assert facts[0].content == "User likes tea"
    assert facts[0].entities == []
