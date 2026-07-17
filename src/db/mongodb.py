"""MongoDB connection management using Motor (async)."""

import os
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://admin:secret@localhost:27017/?authSource=admin",
)


class MongoDB:
    """Simple holder for the global MongoDB client and database."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


db_client = MongoDB()


async def connect_to_mongo() -> None:
    """Establish the connection to MongoDB and select the database."""
    db_client.client = AsyncIOMotorClient(MONGODB_URI)
    db_client.db = db_client.client["jarvis_db"]
    # Vector search indexes will be initialized here in later phases


async def close_mongo_connection() -> None:
    """Close the MongoDB connection if it is open."""
    if db_client.client is not None:
        db_client.client.close()
