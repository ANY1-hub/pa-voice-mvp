"""Slice-Brief 3: recent WM turns must reach the LLM as chat roles.

Working Memory already stores ``User:`` / ``Jarvis:`` lines. Assembled
LLM messages must include those turns as ``role:user`` / ``role:assistant``
(chronological, capped) before the current user message — not only as
flat system bullets. Semantic Memory facts stay in the untrusted system
block. Reply-language instruction stays after that untrusted system
context (last-wins).

Mutation: flattening history only into system bullets (or omitting roles)
must go red. Control twin: empty WM stays system + current user; SM facts
are not promoted to assistant roles.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.orchestrator import ChatOrchestrator, reply_language_instruction

# Distinctive prior-turn token (live debt: bot claimed it could not see this).
_PRIOR_JOKE_WORD = "hidegni"


def _wm_item(content: str) -> MagicMock:
    item = MagicMock()
    item.content = content
    return item


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate_response.return_value = "Hello from Jarvis."
    return llm


@pytest.fixture
def mock_tts():
    tts = AsyncMock()
    tts.synthesize.return_value = b"fake-wav-bytes"
    return tts


@pytest.fixture
def mock_working_memory():
    wm = AsyncMock()
    wm.retrieve.return_value = []
    wm.add.return_value = None
    wm.user_id = "user-a"
    return wm


@pytest.fixture
def mock_semantic_memory():
    sm = AsyncMock()
    sm.search.return_value = []
    sm.user_id = "user-a"
    return sm


def _messages(mock_llm: AsyncMock) -> list[dict[str, str]]:
    return mock_llm.generate_response.await_args.args[0]


def _role_contents(messages: list[dict[str, str]], role: str) -> list[str]:
    return [m["content"] for m in messages if m.get("role") == role]


@pytest.mark.asyncio
async def test_prior_wm_turns_appear_as_user_and_assistant_roles(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Prior User:/Jarvis: WM lines must become role:user / role:assistant messages."""
    # retrieve is newest-first (as production WM); assembly must still be chronological.
    mock_working_memory.retrieve.return_value = [
        _wm_item(f"Jarvis: That word was {_PRIOR_JOKE_WORD}."),
        _wm_item(f"User: Remember the joke word {_PRIOR_JOKE_WORD}"),
    ]
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="What was the joke word?")

    messages = _messages(mock_llm)
    assert messages[0]["role"] == "system"
    assert messages[-1] == {
        "role": "user",
        "content": "What was the joke word?",
    }

    history = messages[1:-1]
    assert history == [
        {"role": "user", "content": f"Remember the joke word {_PRIOR_JOKE_WORD}"},
        {"role": "assistant", "content": f"That word was {_PRIOR_JOKE_WORD}."},
    ]


@pytest.mark.asyncio
async def test_prior_joke_word_is_not_only_a_system_bullet(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Concrete prior-turn content must appear in a non-system role message."""
    mock_working_memory.retrieve.return_value = [
        _wm_item(f"Jarvis: Haha, {_PRIOR_JOKE_WORD} is funny."),
        _wm_item(f"User: The secret joke word is {_PRIOR_JOKE_WORD}"),
    ]
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="What was the joke word from earlier?")

    messages = _messages(mock_llm)
    system = messages[0]["content"]
    # Property: prior-turn content must be in a chat role, not only system bullets.
    assert any(
        m["role"] in ("user", "assistant") and _PRIOR_JOKE_WORD in m["content"]
        for m in messages
    )
    assert "Recent conversation context:" not in system


@pytest.mark.asyncio
async def test_history_roles_are_chronological_oldest_first(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Even if WM retrieve returns newest-first, role history must be oldest-first."""
    mock_working_memory.retrieve.return_value = [
        _wm_item("Jarvis: Second reply"),
        _wm_item("User: Second question"),
        _wm_item("Jarvis: First reply"),
        _wm_item("User: First question"),
    ]
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="Third question")

    history = _messages(mock_llm)[1:-1]
    assert [m["content"] for m in history] == [
        "First question",
        "First reply",
        "Second question",
        "Second reply",
    ]
    assert [m["role"] for m in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_empty_wm_stays_system_plus_current_user_only(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Honest empty-WM behaviour: no invented history roles."""
    mock_working_memory.retrieve.return_value = []
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="Hello alone")

    messages = _messages(mock_llm)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "Hello alone"}


@pytest.mark.asyncio
async def test_semantic_facts_stay_in_untrusted_system_block(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Personal SM facts remain wrapped untrusted system data, not chat roles."""
    fact = MagicMock()
    fact.content = "User is allergic to peanuts"
    mock_semantic_memory.search.return_value = [fact]
    mock_working_memory.retrieve.return_value = [
        _wm_item("Jarvis: Sure."),
        _wm_item("User: Hi"),
    ]
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="Any allergies I mentioned?")

    messages = _messages(mock_llm)
    system = messages[0]["content"]
    assert "User is allergic to peanuts" in system
    assert "untrusted" in system.lower()
    assert "Relevant personal facts" in system or "Personal context" in system
    assert "User is allergic to peanuts" not in "\n".join(
        _role_contents(messages, "assistant")
    )


@pytest.mark.asyncio
async def test_reply_language_instruction_still_last_wins_with_role_history(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Reply-language line stays in system after untrusted SM; history is roles."""
    fact = MagicMock()
    fact.content = "User prefers short answers"
    mock_semantic_memory.search.return_value = [fact]
    mock_working_memory.retrieve.return_value = [
        _wm_item("Jarvis: Got it. I'll stick to English from now on."),
        _wm_item("User: Please always speak English"),
    ]
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="Bitte antworte auf Deutsch. Wie geht es dir?")

    messages = _messages(mock_llm)
    system = messages[0]["content"]
    assert reply_language_instruction("de") in system
    assert system.index("Reply in German") > system.index("User prefers short answers")
    # Prior English promise is conversation data (assistant role), not a system lock alone.
    assistant_bits = "\n".join(_role_contents(messages, "assistant"))
    assert "stick to English" in assistant_bits


@pytest.mark.asyncio
async def test_wm_retrieve_still_capped_for_history_assembly(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """History assembly must keep the existing WM retrieve limit (8 items)."""
    mock_working_memory.retrieve.return_value = []
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="ping")

    mock_working_memory.retrieve.assert_awaited()
    assert mock_working_memory.retrieve.await_args.kwargs.get("limit") == 8


@pytest.mark.asyncio
async def test_working_memory_instance_stays_user_scoped(
    mock_llm, mock_tts, mock_working_memory, mock_semantic_memory
):
    """Orchestrator must keep using the injected user-scoped WM (tenant boundary)."""
    mock_working_memory.user_id = "tenant-ada"
    mock_working_memory.retrieve.return_value = [
        _wm_item("Jarvis: Ada only"),
        _wm_item("User: Ada secret"),
    ]
    orch = ChatOrchestrator(
        llm=mock_llm,
        tts=mock_tts,
        working_memory=mock_working_memory,
        semantic_memory=mock_semantic_memory,
    )

    await orch.process(text="remind me of my secret")

    mock_working_memory.retrieve.assert_awaited()
    assert orch.working_memory is mock_working_memory
    assert orch.working_memory.user_id == "tenant-ada"
    # Ada's prior content must appear as roles for this tenant's WM only.
    assert any(
        m["role"] == "user" and "Ada secret" in m["content"]
        for m in _messages(mock_llm)
    )
