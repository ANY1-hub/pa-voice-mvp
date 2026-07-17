"""MongoDB connection management using Motor (async)."""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import get_settings


class MongoDB:
    """Simple holder for the global MongoDB client and database."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


db_client = MongoDB()


async def connect_to_mongo() -> None:
    """Establish the connection to MongoDB and select the database."""
    settings = get_settings()
    db_client.client = AsyncIOMotorClient(settings.mongodb_uri)
    db_client.db = db_client.client[settings.mongodb_db_name]
    # Vector search indexes will be initialized here in later phases


async def close_mongo_connection() -> None:
    """Close the MongoDB connection if it is open."""
    if db_client.client is not None:
        db_client.client.close()
