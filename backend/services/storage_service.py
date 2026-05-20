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

    @property
    def db(self):
        """Get MongoDB database instance."""
        return self.mongo.client[self.db_name]

    @property
    def collection(self):
        """Get MongoDB collection instance."""
        return self.db[self.collection_name]

    async def get_records(
            self,
            page: int = 1,
            limit: int = 20,
            filters: dict = None,
    ) -> dict:
        """
        Retrieve paginated records from MongoDB.

        Args:
            page: Page number (1-indexed)
            limit: Records per page
            filters: Optional filters (form_type, status, etc.)

        Returns:
            Dictionary with 'records' list and 'total' count
        """
        try:
            if filters is None:
                filters = {}

            skip = (page - 1) * limit

            # Count total matching documents
            total = await self.collection.count_documents(filters)

            # Fetch paginated records
            cursor = self.collection.find(filters).skip(skip).limit(limit).sort("created_at", -1)
            records = await cursor.to_list(length=limit)

            return {
                "records": records,
                "total": total,
                "page": page,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"Error fetching records: {e}", exc_info=True)
            raise


    def record_to_dict(self, record: dict) -> dict:
        """
        Convert MongoDB record to response dictionary.

        Maps MongoDB's '_id' field to 'id' for Pydantic model compatibility.
        """
        if record is None:
            return None

        return {
            "id": str(record.get("_id", "")),
            "processing_id": record.get("processing_id", ""),
            "form_type": record.get("form_type", ""),
            "case_id": record.get("case_id", ""),
            "status": record.get("status", ""),
            "confidence": record.get("confidence"),
            "created_at": record.get("created_at", ""),
            "updated_at": record.get("updated_at", ""),
            "file_url": record.get("file_url"),
            "error_message": record.get("error_message"),
            "extracted_data": record.get("extracted_data"),
        }


    async def get_record_by_processing_id(self,processing_id: str) -> Optional[dict]:
        """
        Retrieve a single record by processing_id.
        """
        try:
            record = await self.collection.find_one({"processing_id": processing_id})
            return self.record_to_dict(record)
        except Exception as e:
            logger.error(f"❌ Failed to fetch record {processing_id}: {e}", exc_info=True)
            raise


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
            inserted_id = self.collection.insert_one(doc).inserted_id

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

            doc = self.collection.find_one({"_id": ObjectId(doc_id)})

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
            query = {}
            if form_type:
                query["form_type"] = form_type.upper()

            results = list(
                self.collection.find(query)
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
            result = self.collection.delete_one({"_id": ObjectId(doc_id)})

            if result.deleted_count > 0:
                logger.info(f"✅ Deleted result: {doc_id}")
                return True

            logger.warning(f"⚠️  Document not found: {doc_id}")
            return False

        except Exception as e:
            logger.error(f"❌ Error deleting result: {e}", exc_info=True)
            return False


    async def get_statistics(self) -> dict:
        """Get aggregate statistics."""
        try:
            pipeline = [
                {
                    "$facet": {
                        "total": [{"$count": "count"}],
                        "by_status": [
                            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                        ],
                        "avg_confidence": [
                            {
                                "$match": {"status": "completed", "confidence": {"$ne": None}}
                            },
                            {"$group": {"_id": None, "avg": {"$avg": "$confidence"}}}
                        ]
                    }
                }
            ]

            result = await self.collection.aggregate(pipeline).to_list(None)
            result = result[0] if result else {}

            total = result.get("total", [{}])[0].get("count", 0)
            by_status = {item["_id"]: item["count"] for item in result.get("by_status", [])}

            return {
                "total": total,
                "completed": by_status.get("completed", 0),
                "failed": by_status.get("failed", 0),
                "pending": by_status.get("pending", 0),
                "average_confidence": result.get("avg_confidence", [{}])[0].get("avg"),
                "completion_rate": (by_status.get("completed", 0) / total * 100) if total > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching statistics: {e}", exc_info=True)
            raise

    # ✅ FIX delete_record to use self.collection
    async def delete_record(self, processing_id: str) -> bool:
        """Delete a record and associated files."""
        try:
            result = await self.collection.delete_one({"processing_id": processing_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting record: {e}", exc_info=True)
            raise
