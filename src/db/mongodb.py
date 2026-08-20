"""MongoDB connection management using Motor (async)."""

import re

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pydantic import BaseModel

from src.core.config import get_settings


def contains_regex(query: str) -> dict[str, str]:
    """Case-insensitive substring filter safe for user-supplied text.

    Metacharacters in ``query`` are escaped so they cannot become a Mongo
    regular expression (ReDoS / over-matching).
    """
    return {"$regex": re.escape(query), "$options": "i"}


def mongo_document(model: BaseModel, extra: dict | None = None) -> dict:
    """Dump a model for insert so Mongo ``_id`` is the application UUID.

    Empty-database / greenfield: one identifier, no ObjectId leak.
    """
    doc = model.model_dump(mode="json")
    app_id = doc.get("id")
    if app_id:
        doc["_id"] = app_id
    if extra:
        doc.update(extra)
    return doc


async def _ensure_unique_id_index(collection: AsyncIOMotorCollection) -> None:
    """Unique, non-sparse index on application ``id``.

    Recreates the index once if it was sparse or missing. Documents without
    ``id`` are dropped (greenfield: no production data to keep).
    """
    indexes = await collection.index_information()
    existing = indexes.get("id_1")
    if existing and existing.get("unique") and not existing.get("sparse"):
        return
    await collection.delete_many({"$or": [{"id": {"$exists": False}}, {"id": None}]})
    if existing:
        await collection.drop_index("id_1")
    await collection.create_index("id", unique=True)


class MongoDB:
    """Simple holder for the global MongoDB client and database.

    Attributes:
        client: Async Motor client, or ``None`` before connect / after close.
        db: Selected database handle, or ``None`` before connect / after close.
    """

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


db_client = MongoDB()


async def connect_to_mongo() -> None:
    """Establish the connection to MongoDB and select the database.

    Also ensures a unique index on ``users.email`` (idempotent).
    """
    settings = get_settings()
    db_client.client = AsyncIOMotorClient(settings.mongodb_uri)
    db_client.db = db_client.client[settings.mongodb_db_name]

    # Ensure unique index on users.email (idempotent)
    await db_client.db["users"].create_index("email", unique=True)
    # At most one bootstrap SuperUser, even under a concurrent first-register race.
    await db_client.db["users"].create_index(
        "bootstrap_slot",
        unique=True,
        partialFilterExpression={"bootstrap_slot": {"$exists": True}},
    )
    # Drop working-memory items after expires_at (set on write, 48h).
    await db_client.db["working_memory"].create_index(
        "expires_at", expireAfterSeconds=0
    )
    await db_client.db["reminders"].create_index(
        [("status", 1), ("fired_at", 1), ("due_at", 1)]
    )
    for coll in (
        "users",
        "working_memory",
        "semantic_memory",
        "notes",
        "reminders",
    ):
        await _ensure_unique_id_index(db_client.db[coll])

    # Vector search indexes will be initialized here in later phases


async def close_mongo_connection() -> None:
    """Close the MongoDB connection if it is open."""
    if db_client.client is not None:
        db_client.client.close()
