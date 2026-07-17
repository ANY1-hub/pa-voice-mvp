from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://admin:secret@localhost:27017/?authSource=admin")

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db_client = MongoDB()

async def connect_to_mongo():
    db_client.client = AsyncIOMotorClient(MONGODB_URI)
    db_client.db = db_client.client["jarvis_db"]
    # We will initialize vector search indexes here in later phases

async def close_mongo_connection():
    if db_client.client:
        db_client.client.close()