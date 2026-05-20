# backend/clients/mongo_client.py
"""
MongoDB client for database operations using PyMongo async driver.
Handles authentication with special characters in password.
Supports async health checks and operations.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from pymongo import AsyncMongoClient

logger = logging.getLogger(__name__)


class MongoClient:
    """Async MongoDB client wrapper using PyMongo AsyncMongoClient with connection pooling and health checks."""

    def __init__(
        self,
        uri: str,
        db_name: str = "bridge_webui_mvp",
        server_selection_timeout: int = 5000,
        connect_timeout: int = 10000,
    ):
        """
        Initialize PyMongo AsyncMongoClient for MongoDB.

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

        # Initialize PyMongo AsyncMongoClient (native async driver)
        self.client = AsyncMongoClient(
            uri,
            serverSelectionTimeoutMS=server_selection_timeout,
            connectTimeoutMS=connect_timeout,
            socketTimeoutMS=30000,
            retryWrites=True,
            w="majority",
        )

        logger.info(f"✅ PyMongo AsyncMongoClient initialized for: {db_name}")

    # ==================== CONNECTION MANAGEMENT ====================

    @property
    def db(self):
        """
        ✅ Get the default async database instance.

        This property allows accessing the database as mongo_client.db
        which is what StorageService expects.

        Returns:
            AsyncDatabase: Async database instance for self.db_name

        Example:
            # In storage_service.py:
            db = mongo_client.db
            collection = db[settings.MONGODB_DB_COLLECTION]
        """
        return self.get_database()

    async def close(self):
        """
        Close MongoDB connection gracefully.

        Safe to call even if connection is already closed.
        """
        try:
            await self.client.close()
            logger.info("🔒 MongoDB connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing MongoDB: {e}")

    def get_database(self, db_name: Optional[str] = None):
        """
        Get async database instance.

        Args:
            db_name: Database name (default: self.db_name)

        Returns:
            AsyncDatabase: Async database instance
        """
        return self.client[db_name or self.db_name]

    def get_collection(
        self,
        collection_name: str,
        db_name: Optional[str] = None,
    ):
        """
        Get async collection instance.

        Args:
            collection_name: Collection name
            db_name: Database name (default: self.db_name)

        Returns:
            AsyncCollection: Async collection instance
        """
        db = self.get_database(db_name)
        return db[collection_name]

    # ==================== HEALTH CHECKS ====================

    async def server_info(self) -> Dict[str, Any]:
        """
        Get MongoDB server information (async).

        Returns:
            dict: Server information including version, os, etc.

        Raises:
            pymongo.errors.OperationFailure: If command fails

        Example:
            info = await client.server_info()
        """
        try:
            info = await self.client.admin.command("serverStatus")
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
                self.client.admin.command("ping"),
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

    async def health_check(
        self,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check asynchronously.

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
            # Run async server_info
            info = await asyncio.wait_for(
                self.server_info(),
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
        Create collection if it doesn't exist (async).

        Args:
            collection_name: Collection name
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if created or already exists, False on error
        """
        try:
            db = self.get_database(db_name)
            collections = await db.list_collection_names()

            if collection_name not in collections:
                await db.create_collection(collection_name)
                logger.info(f"✅ Created collection: {collection_name}")
            else:
                logger.debug(f"✅ Collection exists: {collection_name}")

            return True

        except Exception as e:
            logger.error(f"❌ Error creating collection: {e}")
            return False

    async def create_indexes(
        self,
        collection_name: str,
        indexes: Dict[str, int],
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Create indexes on collection (async).

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
            collection = self.get_collection(collection_name, db_name)

            for field_name, direction in indexes.items():
                try:
                    await collection.create_index([(field_name, direction)])
                    logger.info(
                        f"✅ Created index: {collection_name}.{field_name} "
                        f"({'asc' if direction > 0 else 'desc'})"
                    )
                except Exception as e:
                    logger.warning(f"⚠️  Index may already exist: {field_name} ({e})")

            return True

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            return False

    # ==================== DATABASE OPERATIONS ====================

    async def insert_one(
        self,
        collection_name: str,
        document: Dict[str, Any],
        db_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Insert a single document (async).

        Args:
            collection_name: Collection name
            document: Document to insert
            db_name: Database name (default: self.db_name)

        Returns:
            str: Inserted document ID, or None if failed
        """
        try:
            collection = self.get_collection(collection_name, db_name)
            result = await collection.insert_one(document)
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
        Find a single document (async).

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            db_name: Database name (default: self.db_name)

        Returns:
            dict: Document, or None if not found
        """
        try:
            collection = self.get_collection(collection_name, db_name)
            result = await collection.find_one(query)
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
        Find multiple documents with pagination (async).

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
            collection = self.get_collection(collection_name, db_name)
            cursor = collection.find(query)

            if sort:
                cursor = cursor.sort(sort)

            cursor = cursor.skip(skip).limit(limit)
            result = await cursor.to_list(length=limit)
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
        Update a single document (async).

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            update: Update operations (should use MongoDB operators like $set)
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if document was updated

        Example:
            from bson import ObjectId
            await client.update_one(
                "results",
                {"_id": ObjectId("...")},
                {"$set": {"status": "completed"}}
            )
        """
        try:
            collection = self.get_collection(collection_name, db_name)
            result = await collection.update_one(query, update)
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
        Delete a single document (async).

        Args:
            collection_name: Collection name
            query: MongoDB query filter
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if document was deleted
        """
        try:
            collection = self.get_collection(collection_name, db_name)
            result = await collection.delete_one(query)
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
        Count documents matching query (async).

        Args:
            collection_name: Collection name
            query: MongoDB query filter (default: {})
            db_name: Database name (default: self.db_name)

        Returns:
            int: Number of matching documents
        """
        try:
            collection = self.get_collection(collection_name, db_name)
            count = await collection.count_documents(query or {})
            return count

        except Exception as e:
            logger.error(f"❌ Error counting documents: {e}")
            return 0

    async def aggregate(
        self,
        collection_name: str,
        pipeline: list,
        db_name: Optional[str] = None,
    ) -> list:
        """
        Run aggregation pipeline (async).

        Args:
            collection_name: Collection name
            pipeline: MongoDB aggregation pipeline
            db_name: Database name (default: self.db_name)

        Returns:
            list: Aggregation results
        """
        try:
            collection = self.get_collection(collection_name, db_name)
            cursor = collection.aggregate(pipeline)
            result = await cursor.to_list(length=None)
            return result

        except Exception as e:
            logger.error(f"❌ Error running aggregation: {e}")
            return []
