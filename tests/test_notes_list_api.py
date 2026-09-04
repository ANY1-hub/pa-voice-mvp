"""GET /api/v1/notes lists only the current user's notes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.skills.notes.repository import NoteRepository
from tests.isolation_users import mongo_collection, run_async, two_ready_users

CONTENT_A = "water the basil on the kitchen window"
CONTENT_B = "order rye bread from the bakery"


def test_list_notes_requires_auth(client: TestClient):
    """GET /notes without a JWT must be 401."""
    assert client.get("/api/v1/notes").status_code == 401


def test_list_notes_is_isolated_between_two_real_users(client: TestClient):
    """A's GET /notes must omit B's note; B's list must omit A's."""
    user_a, user_b = two_ready_users(client)

    async def _seed() -> None:
        async with mongo_collection("notes") as coll:
            await NoteRepository(user_id=user_a.user_id, collection=coll).create(
                content=CONTENT_A
            )
            await NoteRepository(user_id=user_b.user_id, collection=coll).create(
                content=CONTENT_B
            )

    run_async(_seed())

    listed_a = client.get("/api/v1/notes", headers=user_a.headers)
    listed_b = client.get("/api/v1/notes", headers=user_b.headers)
    assert listed_a.status_code == 200, listed_a.text
    assert listed_b.status_code == 200, listed_b.text

    contents_a = [item["content"] for item in listed_a.json()["notes"]]
    contents_b = [item["content"] for item in listed_b.json()["notes"]]
    assert CONTENT_A in contents_a
    assert CONTENT_B not in contents_a
    assert CONTENT_B in contents_b
    assert CONTENT_A not in contents_b
