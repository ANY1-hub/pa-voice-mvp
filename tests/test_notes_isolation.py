"""Two-user tenant isolation and prefix-only note-body strip (chat HTTP)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_llm_adapter, get_stt_adapter, get_tts_adapter
from src.main import app
from src.skills.notes.repository import NoteRepository
from tests.isolation_users import mongo_collection, run_async, two_ready_users

CONTENT_A = "water the basil on the kitchen window"
CONTENT_B = "order rye bread from the bakery"


@pytest.fixture
def notes_chat_client(client: TestClient):
    """Real orchestrator; stub only STT/TTS/LLM so text notes do not load voice models."""
    app.dependency_overrides[get_stt_adapter] = lambda: MagicMock()
    app.dependency_overrides[get_tts_adapter] = lambda: None
    app.dependency_overrides[get_llm_adapter] = lambda: None
    yield client
    for dep in (get_stt_adapter, get_tts_adapter, get_llm_adapter):
        app.dependency_overrides.pop(dep, None)


def _chat(client: TestClient, headers: dict, text: str, language: str) -> str:
    response = client.post(
        "/api/v1/chat/text",
        headers=headers,
        json={"text": text, "language": language},
    )
    assert response.status_code == 200, response.text
    return response.json()["response"]


def test_notes_chat_list_is_isolated_between_two_real_users(
    notes_chat_client: TestClient,
):
    """B's chat list has B's content not A's; A's list has A's not B's (control twin)."""
    client = notes_chat_client
    user_a, user_b = two_ready_users(client)

    _chat(client, user_a.headers, f"save a note: {CONTENT_A}", "en")
    _chat(client, user_b.headers, f"save a note: {CONTENT_B}", "en")

    response_b = _chat(client, user_b.headers, "show my notes", "en")
    assert CONTENT_B in response_b
    assert CONTENT_A not in response_b

    response_a = _chat(client, user_a.headers, "show my notes", "en")
    assert CONTENT_A in response_a
    assert CONTENT_B not in response_a


def test_note_repository_list_does_not_return_other_user_documents(client: TestClient):
    """NoteRepository.list_notes bound to B's real user_id must omit A's documents."""
    user_a, user_b = two_ready_users(client)

    async def _seed_and_list() -> tuple[list[str], list[str], list[str]]:
        async with mongo_collection("notes") as coll:
            repo_a = NoteRepository(user_id=user_a.user_id, collection=coll)
            repo_b = NoteRepository(user_id=user_b.user_id, collection=coll)
            await repo_a.create(content=CONTENT_A)
            await repo_b.create(content=CONTENT_B)
            listed_b = await repo_b.list_notes(limit=50)
            listed_a = await repo_a.list_notes(limit=50)
            search_b = await repo_b.list_notes(limit=50, query=CONTENT_A)
            return (
                [n.content for n in listed_b],
                [n.content for n in listed_a],
                [n.content for n in search_b],
            )

    contents_b, contents_a, search_b = run_async(_seed_and_list())
    assert CONTENT_B in contents_b
    assert CONTENT_A not in contents_b
    assert CONTENT_A in contents_a
    assert CONTENT_B not in contents_a
    assert CONTENT_A not in search_b


def test_notes_chat_keeps_interior_note_and_isolates_it(notes_chat_client: TestClient):
    """A body containing 'note' must be stored intact; B's list must not include that body."""
    client = notes_chat_client
    user_a, user_b = two_ready_users(client)
    body_with_note = "the bank note is in the drawer"
    body_b = "the train ticket is under the mug"
    mangled = "the bank  is in the drawer"

    echoed_a = _chat(client, user_a.headers, f"save a note: {body_with_note}", "en")
    _chat(client, user_b.headers, f"save a note: {body_b}", "en")

    listed_a = _chat(client, user_a.headers, "show my notes", "en")
    listed_b = _chat(client, user_b.headers, "show my notes", "en")

    assert body_with_note in echoed_a
    assert body_with_note in listed_a
    assert "bank note" in listed_a
    assert mangled not in listed_a
    assert body_b not in listed_a

    assert body_b in listed_b
    assert body_with_note not in listed_b
    assert "bank note" not in listed_b


def test_notes_chat_en_hyphenated_note_stays_intact_and_isolated(
    notes_chat_client: TestClient,
):
    """After leading 'note:', echoed and listed body keeps hyphenated NOTE; B must not see A's body."""
    client = notes_chat_client
    user_a, user_b = two_ready_users(client)
    suffix = uuid.uuid4().hex[:8]
    intact = f"ALPHA-SECRET-NOTE-A-{suffix}"
    mangled = f"ALPHA-SECRET--A-{suffix}"

    echoed_a = _chat(client, user_a.headers, f"note: {intact}", "en")
    _chat(client, user_b.headers, f"save a note: {CONTENT_B}", "en")
    listed_a = _chat(client, user_a.headers, "show my notes", "en")
    listed_b = _chat(client, user_b.headers, "show my notes", "en")

    assert intact in echoed_a
    assert "NOTE" in echoed_a
    assert mangled not in echoed_a
    assert intact in listed_a
    assert "NOTE" in listed_a
    assert mangled not in listed_a
    assert CONTENT_B not in listed_a

    assert CONTENT_B in listed_b
    assert intact not in listed_b


def test_notes_chat_de_keeps_interior_notiz_and_isolates_it(
    notes_chat_client: TestClient,
):
    """After a leading DE notiz trigger, echo and DE list keep interior notiz; B must not see A's body."""
    client = notes_chat_client
    user_a, user_b = two_ready_users(client)
    body_a = "innen steht noch eine notiz von Anna"
    body_b = "der Zugticket liegt unter der Tasse"

    echoed_a = _chat(client, user_a.headers, f"notiere das: {body_a}", "de")
    _chat(client, user_b.headers, f"notiere das: {body_b}", "de")
    listed_a = _chat(client, user_a.headers, "meine notizen", "de")
    listed_b = _chat(client, user_b.headers, "notizen zeigen", "de")

    assert body_a in echoed_a
    assert "notiz" in echoed_a
    assert body_a in listed_a
    assert "notiz" in listed_a
    assert body_b not in listed_a

    assert body_b in listed_b
    assert body_a not in listed_b


def test_notes_chat_hu_keeps_interior_jegyzet_and_isolates_it(
    notes_chat_client: TestClient,
):
    """After a leading HU jegyzet trigger, echo and HU list keep interior jegyzet; B must not see A's body."""
    client = notes_chat_client
    user_a, user_b = two_ready_users(client)
    body_a = "a jegyzet a fiokban van"
    body_b = "a vonatjegy a bogre alatt van"

    echoed_a = _chat(client, user_a.headers, f"jegyzeteld: {body_a}", "hu")
    _chat(client, user_b.headers, f"jegyzeteld: {body_b}", "hu")
    listed_a = _chat(client, user_a.headers, "mutasd a jegyzeteimet", "hu")
    listed_b = _chat(client, user_b.headers, "listazd a jegyzeteket", "hu")

    assert body_a in echoed_a
    assert "jegyzet" in echoed_a
    assert body_a in listed_a
    assert "jegyzet" in listed_a
    assert body_b not in listed_a

    assert body_b in listed_b
    assert body_a not in listed_b
