# backend/services/storage_service.py
"""
Storage service that handles persistence to MongoDB and MinIO.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, UTC
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
            mongo_client: MongoDB client instance (Motor async client)
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
        """Get MongoDB database instance (async)."""
        return self.mongo.client[self.db_name]

    @property
    def collection(self):
        """Get MongoDB collection instance (async)."""
        return self.db[self.collection_name]

    def record_to_dict(self, record: Optional[dict]) -> Optional[dict]:
        """
        Convert MongoDB record (snake_case) to API format (camelCase).

        Maps all fields from MongoDB document to FormRecord schema.
        Handles None/missing fields gracefully.

        Args:
            record: MongoDB document dict

        Returns:
            Dictionary with camelCase keys ready for FormRecord model
        """
        if record is None:
            return None

        # ✅ COMPREHENSIVE FIELD MAPPING: MongoDB → API
        return {
            # ID mapping (critical)
            "id": str(record.get("_id", "")),

            # Timestamps
            "timestamp": record.get("timestamp"),
            "createdAt": record.get("created_at"),
            "updatedAt": record.get("updated_at"),

            # Metadata
            "imageFilename": record.get("image_filename"),
            "formType": record.get("form_type"),
            "caseId": record.get("case_id"),
            "pageNumber": record.get("page_number"),
            "fileSizeMb": record.get("file_size_mb"),

            # Processing metadata
            "status": record.get("status"),
            "model": record.get("model"),
            "agentProcessed": record.get("agent_processed", False),

            # Processing times
            "processingTimeLlmSeconds": record.get("processing_time_llm_seconds"),
            "processingTimeAgentSeconds": record.get("processing_time_agent_seconds"),

            # Content fields
            "rawJson": record.get("raw_json"),
            "cleanedJson": record.get("cleaned_json"),
            "caseSummary": record.get("case_summary"),

            # Metrics
            "metrics": record.get("metrics"),
            "coverage": record.get("coverage"),
            "completeness": record.get("completeness"),

            # Processing ID (use _id as fallback)
            "processingId": record.get("processing_id") or str(record.get("_id", "")),

            # Additional fields
            "fileUrl": record.get("file_url"),
            "errorMessage": record.get("error_message"),
            "extractedData": record.get("extracted_data"),
        }

    async def get_records(
            self,
            page: int = 1,
            limit: int = 20,
            filters: dict = None,
    ) -> dict:
        """
        Retrieve paginated records from MongoDB with full field mapping.

        Args:
            page: Page number (1-indexed)
            limit: Records per page
            filters: Optional filters (form_type, status, etc.)

        Returns:
            Dictionary with 'records' list (mapped to camelCase) and 'total' count
        """
        try:
            if filters is None:
                filters = {}

            skip = (page - 1) * limit

            logger.debug(f"📜 Querying MongoDB: filters={filters}, skip={skip}, limit={limit}")

            # ✅ Count total matching documents (async)
            total = await self.collection.count_documents(filters)

            # ✅ Fetch paginated records (async)
            cursor = self.collection.find(filters).skip(skip).limit(limit).sort("created_at", -1)
            raw_records = await cursor.to_list(length=limit)

            logger.debug(f"📦 Retrieved {len(raw_records)} raw records from MongoDB")

            # ✅ MAP EACH RECORD FROM snake_case TO camelCase
            mapped_records = []
            for raw_record in raw_records:
                try:
                    mapped = self.record_to_dict(raw_record)
                    if mapped:
                        mapped_records.append(mapped)
                        logger.debug(f"✅ Mapped record {mapped.get('id')}: {list(mapped.keys())}")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to map record: {e}", exc_info=True)
                    continue

            return {
                "records": mapped_records,
                "total": total,
                "page": page,
                "limit": limit,
            }
        except Exception as e:
            logger.error(f"❌ Error fetching records: {e}", exc_info=True)
            raise

    async def get_record_by_processing_id(self, processing_id: str) -> Optional[dict]:
        """
        Retrieve a single record by processing_id with full field mapping.
        """
        try:
            logger.debug(f"🔍 Searching for processing_id: {processing_id}")

            # ✅ Use await with async find_one
            record = await self.collection.find_one({"processing_id": processing_id})

            if not record:
                logger.warning(f"⚠️  Record not found for processing_id: {processing_id}")
                return None

            # ✅ MAP ALL FIELDS
            mapped = self.record_to_dict(record)
            logger.debug(f"✅ Mapped record: {list(mapped.keys()) if mapped else 'None'}")
            return mapped

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
        Stores in snake_case for consistency.
        """
        try:
            now = datetime.now(UTC)

            # Build document for MongoDB (snake_case)
            doc = {
                "timestamp": now.isoformat(),
                "image_filename": image_filename,
                "form_type": form_type,
                "raw_json": json.dumps(result.get("raw_json", {})),
                "cleaned_json": result.get("cleaned_json", {}),
                "case_summary": result.get("case_summary", ""),
                "model": result.get("model", "unknown"),
                "agent_processed": result.get("agent_processed", False),
                "metrics": result.get("metrics", {}),
                "status": "success",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                # ✅ ADD MISSING FIELDS
                "processing_time_llm_seconds": result.get("processing_time_llm_seconds"),
                "processing_time_agent_seconds": result.get("processing_time_agent_seconds"),
                "coverage": result.get("coverage"),
                "completeness": result.get("completeness"),
                "error_message": None,
                "extracted_data": result.get("extracted_data"),
            }

            # Add optional metadata
            if metadata:
                doc.update(metadata)

            # ✅ Use await with async insert_one
            insert_result = await self.collection.insert_one(doc)
            inserted_id = insert_result.inserted_id

            # ✅ SET processing_id if not already set
            if "processing_id" not in doc:
                await self.collection.update_one(
                    {"_id": inserted_id},
                    {"$set": {"processing_id": str(inserted_id)}}
                )

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
        Retrieve form processing result from MongoDB with mapping.
        """
        try:
            from bson import ObjectId

            # ✅ Use await with async find_one
            doc = await self.collection.find_one({"_id": ObjectId(doc_id)})

            if doc:
                return self.record_to_dict(doc)

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
        List recent form processing results with mapping.
        """
        try:
            query = {}
            if form_type:
                query["form_type"] = form_type.upper()

            # ✅ Use await with async find().to_list()
            cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
            raw_results = await cursor.to_list(length=limit)

            # ✅ MAP ALL RECORDS
            mapped_results = [
                self.record_to_dict(doc)
                for doc in raw_results
                if doc is not None
            ]

            return mapped_results

        except Exception as e:
            logger.error(f"❌ Error listing results: {e}", exc_info=True)
            return []

    async def delete_form_result(self, doc_id: str) -> bool:
        """
        Delete form processing result from MongoDB.
        """
        try:
            from bson import ObjectId
            # ✅ Use await with async delete_one
            result = await self.collection.delete_one({"_id": ObjectId(doc_id)})

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
                        "by_form_type": [
                            {"$group": {"_id": "$form_type", "count": {"$sum": 1}}}
                        ],
                        "avg_coverage": [
                            {
                                "$match": {"status": "success", "coverage": {"$ne": None}}
                            },
                            {"$group": {"_id": None, "avg": {"$avg": "coverage"}}}
                        ],
                        "avg_completeness": [
                            {
                                "$match": {"status": "success", "completeness": {"$ne": None}}
                            },
                            {"$group": {"_id": None, "avg": {"$avg": "completeness"}}}
                        ]
                    }
                }
            ]

            # ✅ Use await with async aggregate().to_list()
            cursor = self.collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            result = result[0] if result else {}

            total = result.get("total", [{}])[0].get("count", 0)
            by_status = {item["_id"]: item["count"] for item in result.get("by_status", [])}
            by_form_type = {item["_id"]: item["count"] for item in result.get("by_form_type", [])}

            return {
                "total": total,
                "byStatus": by_status,
                "byFormType": by_form_type,
                "successRate": (by_status.get("success", 0) / total * 100) if total > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Error fetching statistics: {e}", exc_info=True)
            raise

    async def delete_record(self, processing_id: str) -> bool:
        """
        ✅ FIXED: Delete a record by processing_id.
        Handles both ObjectId and string ID formats.
        """
        from bson import ObjectId

        logger.debug(f"🗑️  Deleting record: {processing_id}")

        try:
            # Try THREE query strategies:
            # 1. Direct ObjectId match (if _id is stored as ObjectId)
            # 2. String match (if _id is stored as string)
            # 3. processing_id field match (fallback)

            queries_to_try = []

            # Strategy 1: Try as ObjectId
            try:
                object_id = ObjectId(processing_id)
                queries_to_try.append({
                    "query": {"_id": object_id},
                    "description": f"_id as ObjectId"
                })
                logger.debug(f"🔍 Will try ObjectId query: {object_id}")
            except Exception as e:
                logger.debug(f"⚠️  Cannot convert to ObjectId: {e}")

            # Strategy 2: Try as string
            queries_to_try.append({
                "query": {"_id": processing_id},
                "description": f"_id as string"
            })
            logger.debug(f"🔍 Will try string _id query: {processing_id}")

            # Strategy 3: Try processing_id field
            queries_to_try.append({
                "query": {"processing_id": processing_id},
                "description": f"processing_id field"
            })
            logger.debug(f"🔍 Will try processing_id field query: {processing_id}")

            # Execute queries in order until one succeeds
            record = None
            successful_query = None

            for query_strategy in queries_to_try:
                logger.debug(f"📍 Attempting deletion using {query_strategy['description']}")
                record = await self.db.processing_records.find_one(query_strategy["query"])

                if record:
                    successful_query = query_strategy["query"]
                    logger.info(f"✅ Found record using {query_strategy['description']}")
                    break

            # If no record found with any strategy
            if not record:
                logger.warning(f"⚠️  Record not found with any query strategy: {processing_id}")
                logger.debug(f"   Tried ObjectId, string _id, and processing_id field queries")
                return False

            logger.debug(f"📦 Found record to delete: {record.get('_id')}")

            # Extract file references before deletion
            image_filename = record.get("image_filename")
            processing_id_from_doc = str(record.get("_id"))

            # Delete from MongoDB using the successful query
            result = await self.db.processing_records.delete_one(successful_query)

            if result.deleted_count == 0:
                logger.warning(f"⚠️  MongoDB deletion failed after find: {processing_id}")
                return False

            logger.info(f"✅ Deleted from MongoDB: {processing_id_from_doc}")

            # Clean up MinIO files (if S3 service available)
            try:
                if hasattr(self, 's3_service') and self.s3_service:
                    # Delete image file
                    if image_filename:
                        await self.s3_service.delete_file(image_filename)
                        logger.info(f"✅ Deleted S3 file: {image_filename}")

                    # Delete JSON result file
                    json_filename = f"{processing_id_from_doc}_result.json"
                    await self.s3_service.delete_file(json_filename)
                    logger.info(f"✅ Deleted S3 JSON: {json_filename}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to delete S3 files: {e}")
                # Don't fail the entire operation if S3 cleanup fails

            logger.info(f"✅ Record deletion complete: {processing_id_from_doc}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete record {processing_id}: {e}", exc_info=True)
            return False
