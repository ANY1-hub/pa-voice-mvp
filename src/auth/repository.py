"""User repository – MongoDB access for authentication."""

from motor.motor_asyncio import AsyncIOMotorCollection

from src.db.mongodb import mongo_document
from src.models.user import User


class UserRepository:
    """CRUD operations for the users collection."""

    def __init__(self, collection: AsyncIOMotorCollection | None = None) -> None:
        """Initialize the repository.

        Args:
            collection: MongoDB collection to use. Pass ``None`` for unit tests
                that should not touch the database.
        """
        self.collection = collection

    async def create(self, user: User, *, extra: dict | None = None) -> User:
        """Insert a new user.

        Args:
            user: Fully constructed ``User`` model to persist.
            extra: Optional extra fields stored on the document (e.g.
                ``bootstrap_slot`` for the first SuperUser).

        Returns:
            The same ``User`` instance after successful insert.

        Raises:
            RuntimeError: If no collection is configured.
            DuplicateKeyError: If the email already exists (unique index).
        """
        if self.collection is None:
            raise RuntimeError("Database not connected")
        await self.collection.insert_one(mongo_document(user, extra=extra))
        return user

    async def get_by_email(self, email: str) -> User | None:
        """Find a user by email (case-insensitive).

        Args:
            email: Email address to look up.

        Returns:
            Matching ``User``, or ``None`` if not found / no collection.
        """
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"email": email.lower()})
        if doc is None:
            return None
        doc.pop("_id", None)
        return User.model_validate(doc)

    async def get_by_id(self, user_id: str) -> User | None:
        """Find a user by UUID.

        Args:
            user_id: User ID (UUID string).

        Returns:
            Matching ``User``, or ``None`` if not found / no collection.
        """
        if self.collection is None:
            return None
        doc = await self.collection.find_one({"id": user_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return User.model_validate(doc)

    async def count(self) -> int:
        """Return the number of users in the collection.

        Returns:
            Document count, or 0 if no collection is configured.
        """
        if self.collection is None:
            return 0
        return await self.collection.count_documents({})

    async def list_users(self, limit: int = 100) -> list[User]:
        """Return users ordered by creation time (oldest first).

        Args:
            limit: Maximum number of users to return.

        Returns:
            List of ``User`` models (empty when no collection).
        """
        if self.collection is None:
            return []
        cursor = self.collection.find().sort("created_at", 1).limit(limit)
        users: list[User] = []
        async for doc in cursor:
            doc.pop("_id", None)
            users.append(User.model_validate(doc))
        return users

    async def update(
        self,
        user_id: str,
        *,
        is_active: bool | None = None,
        is_superuser: bool | None = None,
    ) -> User | None:
        """Update selected fields on a user.

        Args:
            user_id: Target user UUID.
            is_active: New active flag (ignored if None).
            is_superuser: New superuser flag (ignored if None).

        Returns:
            Updated ``User``, or ``None`` if not found / no collection.
        """
        if self.collection is None:
            return None
        update_fields: dict = {}
        if is_active is not None:
            update_fields["is_active"] = is_active
        if is_superuser is not None:
            update_fields["is_superuser"] = is_superuser
        if not update_fields:
            return await self.get_by_id(user_id)

        result = await self.collection.find_one_and_update(
            {"id": user_id},
            {"$set": update_fields},
            return_document=True,
        )
        if result is None:
            return None
        result.pop("_id", None)
        return User.model_validate(result)

    async def update_password(
        self,
        user_id: str,
        *,
        hashed_password: str,
        must_change_password: bool = False,
    ) -> User | None:
        if self.collection is None:
            return None
        result = await self.collection.find_one_and_update(
            {"id": user_id},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "must_change_password": must_change_password,
                },
                "$inc": {"token_version": 1},
            },
            return_document=True,
        )
        if result is None:
            return None
        result.pop("_id", None)
        return User.model_validate(result)

    async def set_display_name(self, user_id: str, display_name: str) -> User | None:
        """Store the preferred name Jarvis should use when addressing the user.

        Args:
            user_id: Target user UUID.
            display_name: Already-normalized preferred name.

        Returns:
            Updated ``User``, or ``None`` if not found / no collection.
        """
        if self.collection is None:
            return None
        result = await self.collection.find_one_and_update(
            {"id": user_id},
            {"$set": {"display_name": display_name}},
            return_document=True,
        )
        if result is None:
            return None
        result.pop("_id", None)
        return User.model_validate(result)

    async def set_timezone(self, user_id: str, timezone: str) -> User | None:
        """Store the user's IANA timezone for local clock-time reminders.

        Args:
            user_id: Target user UUID.
            timezone: Already-validated IANA name.

        Returns:
            Updated ``User``, or ``None`` if not found / no collection.
        """
        if self.collection is None:
            return None
        result = await self.collection.find_one_and_update(
            {"id": user_id},
            {"$set": {"timezone": timezone}},
            return_document=True,
        )
        if result is None:
            return None
        result.pop("_id", None)
        return User.model_validate(result)
