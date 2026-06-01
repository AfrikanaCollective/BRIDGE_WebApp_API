# backend/services/storage_service.py
"""
Storage service that handles persistence to MongoDB and MinIO.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from pathlib import Path
from bson import ObjectId

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

    async def get_by_image_filename(self, image_filename: str) -> Optional[
        dict]:
        """
        Get document by image_filename.

        Args:
            image_filename: The image filename

        Returns:
            Document dict or None
        """
        try:
            doc = await self.collection.find_one(
                {"image_filename": image_filename}
            )
            return self.record_to_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error fetching by image_filename: {e}")
            return None

    async def file_exists_in_minio(self, s3_key: str) -> bool:
        """
        Check if file exists in MinIO.

        Args:
            s3_key: S3 object name (key)

        Returns:
            True if file exists in MinIO
        """
        try:
            logger.info(f"🔍 Checking MinIO for: {s3_key} in bucket {self.minio.bucket_name}")
            exists = self.minio.file_exists(s3_key, self.minio.bucket_name)
            if exists:
                logger.info(f"✅ File exists in MinIO: {s3_key}")
            return exists
        except Exception as e:
            logger.error(f"❌ Error checking MinIO: {e}")
            return False

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
            coverage = result.get("coverage", 0.0)
            status = "failed" if coverage == 0.0 else "success"
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
                "status": status,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "processing_time_llm_seconds": result.get("processing_time_llm_seconds"),
                "processing_time_agent_seconds": result.get("processing_time_agent_seconds"),
                "coverage": coverage,
                "completeness": result.get("completeness"),
                "error_message": None,
                "extracted_data": result.get("extracted_data"),
            }

            # Add optional metadata
            if metadata:
                doc.update(metadata)

            # ============================================================
            # UPSERT LOGIC: Check if record with filename already exists
            # ============================================================
            existing_record = await self.collection.find_one(
                {"image_filename": image_filename}
            )

            if existing_record:
                # ============================================================
                # UPDATE EXISTING RECORD
                # ============================================================
                existing_id = existing_record.get("_id")

                # Preserve created_at from original record
                doc["created_at"] = existing_record.get("created_at", now.isoformat())

                # Preserve processing_id if it exists
                processing_id = existing_record.get("processing_id")
                if processing_id:
                    doc["processing_id"] = processing_id

                logger.info(
                    f"🔄 UPDATING existing record for filename: {image_filename} "
                    f"(id={existing_id})"
                )

                try:
                    update_result = await self.collection.update_one(
                        {"_id": existing_id},
                        {"$set": doc}
                    )

                    if update_result.modified_count > 0:
                        logger.info(
                            f"✅ Updated MongoDB record: {existing_id} "
                            f"(matched={update_result.matched_count}, "
                            f"modified={update_result.modified_count})"
                        )
                    else:
                        logger.warning(
                            f"⚠️  Record matched but not modified: {existing_id}"
                        )

                    inserted_id = existing_id

                except Exception as e:
                    logger.error(f"❌ Error updating record: {e}", exc_info=True)
                    return None

            else:
                # ============================================================
                # CREATE NEW RECORD
                # ============================================================
                logger.info(
                    f"✨ CREATING new record for filename: {image_filename}"
                )

                try:
                    insert_result = await self.collection.insert_one(doc)
                    inserted_id = insert_result.inserted_id

                    logger.info(f"✅ Inserted new MongoDB record: {inserted_id}")

                    # ✅ SET processing_id to match _id
                    await self.collection.update_one(
                        {"_id": inserted_id},
                        {"$set": {"processing_id": str(inserted_id)}}
                    )

                except Exception as e:
                    logger.error(f"❌ Error inserting record: {e}", exc_info=True)
                    return None

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
            logger.error(f"❌ Error fetching statistics: {e}", exc_info=True)
            raise

    async def delete_record(self, record_id: str) -> Dict[str, Any]:
        """
        Delete a record with triple-lookup strategy.

        Attempts to find and delete a record using three query strategies:
        1. Try ObjectId lookup on _id
        2. Try string lookup on _id
        3. Try lookup on processing_id field

        Returns detailed status dict for API response.

        Args:
            record_id: The record ID (can be ObjectId string or processing_id)

        Returns:
            Dict with success status, message, and cleanup results
        """
        logger.info(f"🔍 DELETE REQUEST: record_id={record_id}")

        record = None
        query_used = None

        try:
            # ============================================================
            # STRATEGY 1: Lookup by _id as ObjectId
            # ============================================================
            try:
                if ObjectId.is_valid(record_id):
                    object_id = ObjectId(record_id)
                    record = await self.collection.find_one({"_id": object_id})
                    if record:
                        query_used = f"ObjectId(_id={record_id})"
                        logger.info(f"✅ FOUND via ObjectId lookup: {query_used}")
            except Exception as e:
                logger.warning(f"⚠️  ObjectId lookup failed: {e}")

            # ============================================================
            # STRATEGY 2: Lookup by _id as string
            # ============================================================
            if not record:
                try:
                    record = await self.collection.find_one({"_id": record_id})
                    if record:
                        query_used = f"string _id={record_id}"
                        logger.info(f"✅ FOUND via string _id lookup: {query_used}")
                except Exception as e:
                    logger.warning(f"⚠️  String _id lookup failed: {e}")

            # ============================================================
            # STRATEGY 3: Lookup by processing_id field
            # ============================================================
            if not record:
                try:
                    record = await self.collection.find_one({"processing_id": record_id})
                    if record:
                        query_used = f"processing_id={record_id}"
                        logger.info(f"✅ FOUND via processing_id lookup: {query_used}")
                except Exception as e:
                    logger.warning(f"⚠️  processing_id lookup failed: {e}")

            # ============================================================
            # Record not found after all strategies
            # ============================================================
            if not record:
                logger.error(f"❌ Record not found with any query strategy: {record_id}")
                return {
                    "success": False,
                    "message": f"Record not found: {record_id}",
                    "record_id": record_id,
                    "strategies_tried": [
                        "ObjectId(_id)",
                        "string _id",
                        "processing_id field"
                    ]
                }

            # ============================================================
            # Extract IDs and metadata for deletion & cleanup
            # ============================================================
            actual_id = record.get("_id")
            processing_id = record.get("processing_id", str(actual_id))
            image_filename = record.get("image_filename")
            form_type = record.get("form_type", "unknown")

            logger.info(f"📋 RECORD FOUND (query: {query_used})")
            logger.info(f"   _id={actual_id}, processing_id={processing_id}, image={image_filename}")

            # ============================================================
            # Delete from MongoDB
            # ============================================================
            try:
                result = await self.collection.delete_one({"_id": actual_id})
                if result.deleted_count == 0:
                    logger.error(f"❌ MongoDB delete failed for _id={actual_id}")
                    return {
                        "success": False,
                        "message": "Failed to delete record from database",
                        "record_id": record_id
                    }
                logger.info(f"✅ MongoDB deletion successful: deleted_count={result.deleted_count}")
            except Exception as e:
                logger.error(f"❌ MongoDB deletion error: {e}")
                return {
                    "success": False,
                    "message": f"Database deletion error: {str(e)}",
                    "record_id": record_id
                }

            # ============================================================
            # Cleanup MinIO/S3 assets
            # ============================================================
            cleanup_results = []

            # Delete original image file
            if image_filename:
                try:
                    await self.minio.delete_object(image_filename)
                    logger.info(f"🗑️  Deleted MinIO object: {image_filename}")
                    cleanup_results.append({
                        "file": image_filename,
                        "type": "image",
                        "deleted": True
                    })
                except Exception as e:
                    logger.warning(f"⚠️  Failed to delete MinIO object {image_filename}: {e}")
                    cleanup_results.append({
                        "file": image_filename,
                        "type": "image",
                        "deleted": False,
                        "error": str(e)
                    })

            # Delete result JSON file
            result_json_filename = f"{processing_id}_result.json"
            try:
                await self.minio.delete_object(result_json_filename)
                logger.info(f"🗑️  Deleted MinIO object: {result_json_filename}")
                cleanup_results.append({
                    "file": result_json_filename,
                    "type": "json_result",
                    "deleted": True
                })
            except Exception as e:
                logger.warning(f"⚠️  Failed to delete MinIO object {result_json_filename}: {e}")
                cleanup_results.append({
                    "file": result_json_filename,
                    "type": "json_result",
                    "deleted": False,
                    "error": str(e)
                })

            logger.info(f"✨ Record deletion complete: {record_id}")

            # ============================================================
            # Success response
            # ============================================================
            return {
                "success": True,
                "message": "Record and associated files deleted successfully",
                "record_id": record_id,
                "actual_id": str(actual_id),
                "processing_id": processing_id,
                "form_type": form_type,
                "query_strategy": query_used,
                "mongodb_deleted": True,
                "cleanup_results": cleanup_results
            }

        except Exception as e:
            logger.error(f"❌ Unexpected error during deletion: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}",
                "record_id": record_id
            }
