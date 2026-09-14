"""REVIEWEXTERN P2-2: tenant finds must not COLLSCAN on user_id.

Slice-Brief 13: working_memory, notes, and reminders get an idempotent
user_id index at connect. semantic_memory already has user_id_1_content_1.

Mutation M1: skip create_index(\"user_id\") on those three → this test goes red.
Control: SM still has a user_id-prefixed unique pair; reminders keep the
scheduler compound (status, fired_at, due_at).
"""

from __future__ import annotations

from pymongo import MongoClient

from src.core.config import get_settings


def _index_keys(info: dict) -> list[list[tuple[str, int]]]:
    return [list(spec["key"]) for spec in info.values()]


def _has_user_id_prefix(info: dict) -> bool:
    return any(keys and keys[0][0] == "user_id" for keys in _index_keys(info))


def test_tenant_collections_have_user_id_index(client):
    """After lifespan connect, WM / notes / reminders index user_id.

    Mutation M1: omitting those three create_index calls must go red.
    """
    settings = get_settings()
    assert "test" in settings.mongodb_db_name.lower()
    sync = MongoClient(settings.mongodb_uri)
    try:
        db = sync[settings.mongodb_db_name]
        missing: list[str] = []
        for name in ("working_memory", "notes", "reminders"):
            info = db[name].index_information()
            if not _has_user_id_prefix(info):
                missing.append(f"{name}: {sorted(info)}")
        assert not missing, "user_id index missing: " + "; ".join(missing)
    finally:
        sync.close()


def test_existing_indexes_remain(client):
    """Control twin: SM unique pair and reminders scheduler compound stay."""
    settings = get_settings()
    sync = MongoClient(settings.mongodb_uri)
    try:
        db = sync[settings.mongodb_db_name]
        sm = db["semantic_memory"].index_information()
        assert "user_id_1_content_1" in sm
        rem = db["reminders"].index_information()
        keys = _index_keys(rem)
        assert [("status", 1), ("fired_at", 1), ("due_at", 1)] in keys
    finally:
        sync.close()
