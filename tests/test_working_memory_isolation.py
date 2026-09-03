"""Two-user tenant isolation for Working Memory over HTTP + JWT."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.isolation_users import two_ready_users


def _contents(body: dict) -> list[str]:
    return [item["content"] for item in body["data"]]


def test_working_memory_list_is_isolated_between_two_real_users(client: TestClient):
    """B's GET /memory/working must not include A's item; A's GET must include A's, not B's."""
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-WM-A-{token}"
    secret_b = f"BRAVO-SECRET-WM-B-{token}"

    created_a = client.post(
        "/api/v1/memory/working",
        headers=user_a.headers,
        json={"content": secret_a, "importance_score": 0.5},
    )
    created_b = client.post(
        "/api/v1/memory/working",
        headers=user_b.headers,
        json={"content": secret_b, "importance_score": 0.5},
    )
    assert created_a.status_code == 200, created_a.text
    assert created_b.status_code == 200, created_b.text

    listed_b = client.get("/api/v1/memory/working", headers=user_b.headers)
    assert listed_b.status_code == 200, listed_b.text
    contents_b = _contents(listed_b.json())
    assert secret_b in contents_b
    assert secret_a not in contents_b

    listed_a = client.get("/api/v1/memory/working", headers=user_a.headers)
    assert listed_a.status_code == 200, listed_a.text
    contents_a = _contents(listed_a.json())
    assert secret_a in contents_a
    assert secret_b not in contents_a


def test_working_memory_query_does_not_return_other_user_secret(client: TestClient):
    """B's query for A's secret is empty; B's query for B's own secret still returns (same test)."""
    user_a, user_b = two_ready_users(client)
    token = uuid.uuid4().hex[:8]
    secret_a = f"ALPHA-SECRET-WM-Q-A-{token}"
    secret_b = f"BRAVO-SECRET-WM-Q-B-{token}"

    assert (
        client.post(
            "/api/v1/memory/working",
            headers=user_a.headers,
            json={"content": secret_a, "importance_score": 0.5},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/memory/working",
            headers=user_b.headers,
            json={"content": secret_b, "importance_score": 0.5},
        ).status_code
        == 200
    )

    as_other = client.get(
        "/api/v1/memory/working",
        headers=user_b.headers,
        params={"query": secret_a},
    )
    assert as_other.status_code == 200, as_other.text
    leaked = _contents(as_other.json())
    assert secret_a not in leaked
    assert leaked == []

    as_own = client.get(
        "/api/v1/memory/working",
        headers=user_b.headers,
        params={"query": secret_b},
    )
    assert as_own.status_code == 200, as_own.text
    own_contents = _contents(as_own.json())
    assert secret_b in own_contents
    assert secret_a not in own_contents
