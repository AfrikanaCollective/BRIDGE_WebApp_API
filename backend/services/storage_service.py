# backend/services/storage_service.py
"""
Storage service that handles persistence to MongoDB and MinIO.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from config.settings import settings
from clients.mongo_client import MongoClient
from clients.minio_client import MinIOClient

logger = logging.getLogger(__name__)


class StorageService:
    """Handles persistence to MongoDB and MinIO."""

    def __init__(
        self,
        mongo_client: MongoClient,
        minio_client: MinIOClient,
        db_name: str = settings.MONGODB_DB_NAME,
        collection_name: str = settings.MONGODB_DB_COLLECTION,
    ):
        """
        Initialize storage service.

        Args:
            mongo_client: MongoDB client instance
            minio_client: MinIO client instance
            db_name: MongoDB database name
            collection_name: MongoDB collection name
        """
        self.mongo = mongo_client
        self.minio = minio_client
        self.db_name = db_name
        self.collection_name = collection_name

        logger.info(
            f"💾 Storage service initialized: "
            f"MongoDB({db_name}.{collection_name}), MinIO"
        )

    async def save_form_processing_result(
        self,
        result: Dict[str, Any],
        image_filename: str,
        form_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Save form processing result to MongoDB and MinIO.

        Saves both JSON response and metadata to MongoDB,
        and stores full result as JSON in MinIO.

        Args:
            result: Processing result from form_processor
            image_filename: Original image filename
            form_type: Form type (ITF, NAR, etc.)
            metadata: Additional metadata to store

        Returns:
            str: Document ID in MongoDB, or None if failed

        Example result structure:
        {
            "response": "...",
            "raw_json": {...},
            "cleaned_json": {...},
            "case_summary": "...",
            "model": "qwen-turbo",
            "metrics": {...},
            "agent_processed": True,
        }
        """
        try:
            # Build document for MongoDB
            doc = {
                "timestamp": datetime.utcnow(),
                "image_filename": image_filename,
                "form_type": form_type,
                "response_preview": result.get("response", "")[:500],
                "raw_json_preview": json.dumps(result.get("raw_json", {}))[:500],
                "cleaned_json": result.get("cleaned_json", {}),
                "case_summary": result.get("case_summary", ""),
                "model": result.get("model", "unknown"),
                "agent_processed": result.get("agent_processed", False),
                "metrics": result.get("metrics", {}),
                "status": "success",
            }

            # Add optional metadata
            if metadata:
                doc.update(metadata)

            # Save to MongoDB
            db = self.mongo.client[self.db_name]
            collection = db[self.collection_name]
            inserted_id = collection.insert_one(doc).inserted_id

            logger.info(f"✅ Saved to MongoDB: {inserted_id}")

            # Save full result as JSON to MinIO
            stem = Path(image_filename).stem
            s3_key = f"form-results/{form_type.lower()}/{stem}.json"

            success = await self.minio.upload_bytes(
                data=json.dumps(result, indent=2, ensure_ascii=False).encode(),
                object_name=s3_key,
                content_type="application/json",
                metadata={
                    "form-type": form_type,
                    "image-filename": image_filename,
                    "mongo-id": str(inserted_id),
                },
            )

            if success:
                logger.info(f"✅ Saved full result to MinIO: {s3_key}")
            else:
                logger.warning(f"⚠️  Failed to save to MinIO: {s3_key}")

            return str(inserted_id)

        except Exception as e:
            logger.error(f"❌ Error saving result: {e}", exc_info=True)
            return None

    async def save_form_document(
        self,
        file_path: str,
        form_type: str,
        case_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Save original form document (image) to MinIO.

        Args:
            file_path: Path to the form document
            form_type: Form type (ITF, NAR, etc.)
            case_id: Optional case ID for organization

        Returns:
            str: S3 key of uploaded file, or None if failed
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                logger.error(f"❌ File not found: {file_path}")
                return None

            # Build S3 key
            if case_id:
                s3_key = f"form-documents/{form_type.lower()}/{case_id}/{file_path.name}"
            else:
                s3_key = f"form-documents/{form_type.lower()}/{file_path.name}"

            # Upload to MinIO
            success = await self.minio.upload_file(
                file_path=str(file_path),
                object_name=s3_key,
                metadata={
                    "form-type": form_type,
                    "original-name": file_path.name,
                    "case-id": case_id or "unknown",
                },
            )

            if success:
                return s3_key
            return None

        except Exception as e:
            logger.error(f"❌ Error saving document: {e}", exc_info=True)
            return None

    async def get_form_result(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve form processing result from MongoDB.

        Args:
            doc_id: MongoDB document ID

        Returns:
            dict: Document data, or None if not found
        """
        try:
            from bson import ObjectId

            db = self.mongo.client[self.db_name]
            collection = db[self.collection_name]

            doc = collection.find_one({"_id": ObjectId(doc_id)})

            if doc:
                # Convert ObjectId to string for JSON serialization
                doc["_id"] = str(doc["_id"])
                return doc

            logger.warning(f"⚠️  Document not found: {doc_id}")
            return None

        except Exception as e:
            logger.error(f"❌ Error retrieving result: {e}", exc_info=True)
            return None

    async def list_form_results(
        self,
        form_type: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        """
        List recent form processing results.

        Args:
            form_type: Filter by form type (optional)
            limit: Maximum number of results

        Returns:
            list: Form processing results
        """
        try:
            db = self.mongo.client[self.db_name]
            collection = db[self.collection_name]

            query = {}
            if form_type:
                query["form_type"] = form_type.upper()

            results = list(
                collection.find(query)
                .sort("timestamp", -1)
                .limit(limit)
            )

            # Convert ObjectIds to strings
            for doc in results:
                doc["_id"] = str(doc["_id"])

            return results

        except Exception as e:
            logger.error(f"❌ Error listing results: {e}", exc_info=True)
            return []

    async def delete_form_result(self, doc_id: str) -> bool:
        """
        Delete form processing result from MongoDB.

        Args:
            doc_id: MongoDB document ID

        Returns:
            bool: True if deleted
        """
        try:
            from bson import ObjectId

            db = self.mongo.client[self.db_name]
            collection = db[self.collection_name]

            result = collection.delete_one({"_id": ObjectId(doc_id)})

            if result.deleted_count > 0:
                logger.info(f"✅ Deleted result: {doc_id}")
                return True

            logger.warning(f"⚠️  Document not found: {doc_id}")
            return False

        except Exception as e:
            logger.error(f"❌ Error deleting result: {e}", exc_info=True)
            return False
