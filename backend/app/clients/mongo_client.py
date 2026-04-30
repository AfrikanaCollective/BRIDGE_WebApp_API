# backend/app/clients/mongo_client.py
"""
MongoDB client for database operations.
Handles authentication with special characters in password.
"""

import logging
from typing import Optional, Dict, Any
from pymongo import MongoClient as PyMongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

logger = logging.getLogger(__name__)


class MongoClient:
    """MongoDB client wrapper with connection pooling."""

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

            # Test connection
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

    async def close(self):
        """Close MongoDB connection."""
        try:
            self.client.close()
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

    async def ping(self) -> bool:
        """
        Test database connection.

        Returns:
            bool: True if connected
        """
        try:
            self.client.admin.command("ping")
            logger.debug("✅ MongoDB ping successful")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB ping failed: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            dict: Health status including:
                - connected: bool
                - server_info: dict (if connected)
                - error: str (if not connected)

        Example:
            {
                "connected": true,
                "server_info": {
                    "version": "6.0.0",
                    "ok": 1
                }
            }
        """
        try:
            info = self.client.server_info()
            logger.debug(f"✅ MongoDB health check: {info}")
            return {
                "connected": True,
                "server_info": info,
            }
        except Exception as e:
            logger.error(f"❌ MongoDB health check failed: {e}")
            return {
                "connected": False,
                "error": str(e),
            }

    async def create_collection_if_not_exists(
        self,
        collection_name: str,
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Create collection if it doesn't exist.

        Args:
            collection_name: Collection name
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if created or already exists
        """
        try:
            db = self.get_database(db_name)

            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
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
        indexes: Dict[str, Any],
        db_name: Optional[str] = None,
    ) -> bool:
        """
        Create indexes on collection.

        Args:
            collection_name: Collection name
            indexes: Dictionary of index definitions
            db_name: Database name (default: self.db_name)

        Returns:
            bool: True if successful

        Example:
            indexes = {
                "timestamp": -1,
                "form_type": 1,
            }
            await client.create_indexes("results", indexes)
        """
        try:
            collection = self.get_collection(collection_name, db_name)

            for field_name, direction in indexes.items():
                collection.create_index([(field_name, direction)])
                logger.info(f"✅ Created index: {collection_name}.{field_name}")

            return True

        except Exception as e:
            logger.error(f"❌ Error creating indexes: {e}")
            return False
