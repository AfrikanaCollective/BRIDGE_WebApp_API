# backend/clients/mongo_client.py
"""
MongoDB client for database operations.
Handles authentication with special characters in password.
Supports both sync and async health checks.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pymongo import MongoClient as PyMongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

logger = logging.getLogger(__name__)


class MongoClient:
    """MongoDB client wrapper with connection pooling and health checks."""

    def __init__(
        self,
        uri: str,
        db_name: str = "bridge_webui_mvp",
        server_selection_timeout: int = 5000,
        connect_timeout: int = 10000,
    ):
        """
        Initialize MongoDB client.

        Args:
            uri: MongoDB connection URI
                 Format: mongodb://user:password@host:port/db?authSource=admin
                 Password should be URL-encoded for special characters
            db_name: Default database name
            server_selection_timeout: Server selection timeout in ms
            connect_timeout: Connection timeout in ms

        Example:
            uri = "mongodb://user:password@localhost:27017/bridge_webui_mvp?authSource=admin"
            client = MongoClient(uri, "bridge_form_processor")
        """
        self.uri = uri
        self.db_name = db_name

        try:
            self.client = PyMongoClient(
                uri,
                serverSelectionTimeoutMS=server_selection_timeout,
                connectTimeoutMS=connect_timeout,
                socketTimeoutMS=30000,
                retryWrites=True,
                w="majority",
            )

            # Test connection immediately
            self.client.admin.command("ping")
            logger.info(f"✅ MongoDB connected: {db_name}")

        except ServerSelectionTimeoutError as e:
            logger.error(f"❌ MongoDB connection timeout: {e}")
            raise
        except OperationFailure as e:
            logger.error(f"❌ MongoDB authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ MongoDB connection error: {e}")
            raise

    # ==================== CONNECTION MANAGEMENT ====================
    @property
    def db(self):
        """
        ✅ FIXED: Get the default database instance.

        This property allows accessing the database as mongo_client.db
        which is what stats.py expects.

        Returns:
            pymongo.database.Database: Database instance for self.db_name

        Example:
            # In stats.py:
            db = mongo_client.db
            collection = db[settings.MONGODB_DB_COLLECTION]
        """
        return self.get_database()

    # ==================== CONNECTION MANAGEMENT ====================

    async def close(self):
        """
        Close MongoDB connection gracefully.

        Safe to call even if connection is already closed.
        """
        try:
            await asyncio.to_thread(self.client.close)
            logger.info("🔒 MongoDB connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing MongoDB: {e}")

    def get_database(self, db_name: Optional[str] = None):
        """
        Get database instance.

        Args:
            db_name: Database name (default: self.db_name)

        Returns:
            pymongo.database.Database: Database instance
        """
        return self.client[db_name or self.db_name]

    def get_collection(
        self,
        collection_name: str,
        db_name: Optional[str] = None,
    ):
        """
        Get collection instance.

        Args:
            collection_name: Collection name
            db_name: Database name (default: self.db_name)

        Returns:
            pymongo.collection.Collection: Collection instance
        """
        db = self.get_database(db_name)
        return db[collection_name]

    # ==================== HEALTH CHECKS ====================

    def server_info(self) -> Dict[str, Any]:
        """
        Get MongoDB server information (synchronous).

        This is the primary method used by health checks.
        Do NOT call this from async context directly - use asyncio.to_thread().

        Returns:
            dict: Server information including version, os, etc.

        Raises:
            pymongo.errors.OperationFailure: If command fails

        Example:
            # In sync context:
            info = client.server_info()

            # In async context:
            info = await asyncio.to_thread(client.server_info)
        """
        try:
            info = self.client.admin.command("serverStatus")
            logger.debug(f"✅ MongoDB server_info: v{info.get('version', 'unknown')}")
            return info
        except Exception as e:
            logger.error(f"❌ MongoDB server_info failed: {e}")
            raise

    async def ping(self, timeout: float = 5.0) -> bool:
        """
        Test database connection asynchronously.

        Args:
            timeout: Timeout in seconds

        Returns:
            bool: True if connected, False otherwise
        """
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self._sync_ping),
                timeout=timeout
            )
            logger.debug("✅ MongoDB ping successful")
            return True
        except asyncio.TimeoutError:
            logger.error("❌ MongoDB ping timeout")
            return False
        except Exception as e:
            logger.error(f"❌ MongoDB ping failed: {e}")
            return False

    def _sync_ping(self) -> None:
        """
        Synchronous ping operation.

        Helper method for async ping().
        """
        self.client.admin.command("ping")

    async def health_check(
        self,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check asynchronously.

        Runs server_info in thread pool to avoid blocking event loop.

        Args:
            timeout: Timeout in seconds for health check

        Returns:
            dict: Health status with keys:
                - connected: bool
                - server_info: dict (if connected)
                - version: str (MongoDB version)
                - error: str (if connection failed)
                - error_type: str (exception class name)

        Example:
            health = await client.health_check(timeout=5.0)
            if health["connected"]:
                print(f"MongoDB v{health['version']} is healthy")
            else:
                print(f"Error: {health['error']}")
        """
        try:
            # Run blocking server_info call in thread pool
            info = await asyncio.wait_for(
                asyncio.to_thread(self.server_info),
                timeout=timeout
            )

            version = info.get("version", "unknown")
            logger.debug(f"✅ MongoDB health check passed: v{version}")

            return {
                "connected": True,
                "server_info": info,
                "version": version,
                "error": None,
                "error_type": None,
            }

        except asyncio.TimeoutError:
            error_msg = f"Health check timeout ({timeout}s)"
            logger.error(f"❌ MongoDB: {error_msg}")
            return {
                "connected": False,
                "server_info": None,
                "version": None,
                "error": error_msg,
                "error_type": "TimeoutError",
            }

        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            logger.error(f"❌ MongoDB health check failed ({error_type}): {error_msg}")
            return {
                "connected": False,
                "server_info": None,
                "version": None,
                "error": error_msg,
                "error_type": error_type,
            }

    # ==================== COLLECTION MANAGEMENT ====================

    async def create_collection_if_not_exists(
        self,
        collection_name: str,
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Create collection if it doesn't exist.

        Runs in thread pool to avoid blocking event loop.

        Args:
            collection_name: Collection name
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if created or already exists, False on error
        """
        try:
            success = await asyncio.to_thread(
                self._sync_create_collection_if_not_exists,
                collection_name,
                db_name,
            )
            return success

        except Exception as e:
            logger.error(f"❌ Error creating collection: {e}")
            return False

    def _sync_create_collection_if_not_exists(
        self,
        collection_name: str,
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Synchronous helper for collection creation.
        """
        db = self.get_database(db_name)

        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            logger.info(f"✅ Created collection: {collection_name}")
        else:
            logger.debug(f"✅ Collection exists: {collection_name}")

        return True

    async def create_indexes(
        self,
        collection_name: str,
        indexes: Dict[str, int],
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Create indexes on collection.

        Runs in thread pool to avoid blocking event loop.

        Args:
            collection_name: Collection name
            indexes: Dictionary of {field_name: direction}
                     direction: 1 for ascending, -1 for descending
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if successful, False otherwise

        Example:
            indexes = {
                "timestamp": -1,      # Descending
                "form_type": 1,       # Ascending
                "case_id": 1,
                "status": 1,
            }
            success = await client.create_indexes("results", indexes)
        """
        try:
            success = await asyncio.to_thread(
                self._sync_create_indexes,
                collection_name,
                indexes,
                db_name,
            )
            return success

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            return False

    def _sync_create_indexes(
        self,
        collection_name: str,
        indexes: Dict[str, int],
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Synchronous helper for index creation.
        """
        collection = self.get_collection(collection_name, db_name)

        for field_name, direction in indexes.items():
            try:
                collection.create_index([(field_name, direction)])
                logger.info(
                    f"✅ Created index: {collection_name}.{field_name} "
                    f"({'asc' if direction > 0 else 'desc'})"
                )
            except Exception as e:
                logger.warning(f"⚠️  Index may already exist: {field_name} ({e})")

        return True

    # ==================== DATABASE OPERATIONS ====================

    async def insert_one(
        self,
        collection_name: str,
        document: Dict[str, Any],
        db_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Insert a single document.

        Args:
            collection_name: Collection name
            document: Document to insert
            db_name: Database name (default: self.db_name)

        Returns:
            str: Inserted document ID, or None if failed
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.get_collection(collection_name, db_name).insert_one(document)
            )
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"❌ Error inserting document: {e}")
            return None

    async def find_one(
        self,
        collection_name: str,
        query: Dict[str, Any],
        db_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single document.

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            db_name: Database name (default: self.db_name)

        Returns:
            dict: Document, or None if not found
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.get_collection(collection_name, db_name).find_one(query)
            )
            return result
        except Exception as e:
            logger.error(f"❌ Error finding document: {e}")
            return None

    async def find_many(
        self,
        collection_name: str,
        query: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort: Optional[list] = None,
        db_name: Optional[str] = None,
    ) -> list:
        """
        Find multiple documents with pagination.

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            skip: Number of documents to skip
            limit: Maximum documents to return
            sort: List of (field, direction) tuples
            db_name: Database name (default: self.db_name)

        Returns:
            list: Documents matching query
        """
        try:
            def _find():
                cursor = self.get_collection(collection_name, db_name).find(query)
                if sort:
                    cursor = cursor.sort(sort)
                return list(cursor.skip(skip).limit(limit))

            result = await asyncio.to_thread(_find)
            return result

        except Exception as e:
            logger.error(f"❌ Error finding documents: {e}")
            return []

    async def update_one(
        self,
        collection_name: str,
        query: Dict[str, Any],
        update: Dict[str, Any],
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Update a single document.

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            update: Update operations (should use MongoDB operators like $set)
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if document was updated

        Example:
            await client.update_one(
                "results",
                {"_id": ObjectId("...")},
                {"$set": {"status": "completed"}}
            )
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.get_collection(collection_name, db_name).update_one(
                    query,
                    update
                )
            )
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"❌ Error updating document: {e}")
            return False

    async def delete_one(
        self,
        collection_name: str,
        query: Dict[str, Any],
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Delete a single document.

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if document was deleted
        """
        try:
            result = await asyncio.to_thread(
                lambda: self.get_collection(collection_name, db_name).delete_one(query)
            )
            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"❌ Error deleting document: {e}")
            return False

    async def count_documents(
        self,
        collection_name: str,
        query: Dict[str, Any] = None,
        db_name: Optional[str] = None,
    ) -> int:
        """
        Count documents matching query.

        Args:
            collection_name: Collection name
            query: MongoDB query filter (default: {})
            db_name: Database name (default: self.db_name)

        Returns:
            int: Number of matching documents
        """
        try:
            count = await asyncio.to_thread(
                lambda: self.get_collection(collection_name, db_name).count_documents(
                    query or {}
                )
            )
            return count

        except Exception as e:
            logger.error(f"❌ Error counting documents: {e}")
            return 0
