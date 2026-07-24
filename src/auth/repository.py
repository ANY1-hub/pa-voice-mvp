"""User repository – MongoDB access for authentication."""

from motor.motor_asyncio import AsyncIOMotorCollection

from src.models.user import User


class UserRepository:
    """CRUD operations for the users collection."""

    def __init__(self, collection: AsyncIOMotorCollection | None = None) -> None:
        """Initialize the repository.

        Args:
            collection: MongoDB collection to use. Pass None for unit tests
                        that should not touch the database.
        """
        self.collection = collection

    async def create(self, user: User) -> User:
        """Insert a new user. Raises if email already exists (unique index)."""
        if self.collection is None:
            raise RuntimeError("Database not connected")
        await self.collection.insert_one(user.model_dump(mode="json"))
        return user

    async def get_by_email(self, email: str) -> User | None:
        """Find a user by email (case-insensitive)."""
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"email": email.lower()})
        if doc is None:
            return None
        doc.pop("_id", None)
        return User.model_validate(doc)

    async def get_by_id(self, user_id: str) -> User | None:
        """Find a user by UUID."""
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"id": user_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return User.model_validate(doc)
