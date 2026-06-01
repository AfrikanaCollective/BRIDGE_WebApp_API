# backend/clients/minio_client.py
"""
MinIO S3 client for file storage.
"""

import io
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinIOClient:
    """MinIO S3 client wrapper."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        secure: bool = False,
        region: str = "us-east-1",
    ):
        """
        Initialize MinIO client.

        Args:
            endpoint: MinIO endpoint (e.g., "localhost:9000")
            access_key: Access key
            secret_key: Secret key
            bucket_name: Default bucket name
            secure: Use HTTPS (default: False)
            region: Region name (default: us-east-1)
        """
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.secure = secure
        self.region = region

        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )

        logger.info(f"🪣 MinIO client initialized: {endpoint}/{bucket_name}")

    async def ensure_bucket_exists(self, bucket_name: Optional[str] = None) -> bool:
        """
        Ensure bucket exists, create if not.

        Args:
            bucket_name: Bucket name (default: self.bucket_name)

        Returns:
            bool: True if bucket exists or was created
        """
        bucket = bucket_name or self.bucket_name

        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket, region=self.region)
                logger.info(f"✅ Created bucket: {bucket}")
            else:
                logger.debug(f"✅ Bucket exists: {bucket}")
            return True
        except S3Error as e:
            logger.error(f"❌ Error ensuring bucket: {e}")
            return False

    async def upload_file(
        self,
        file_path: str,
        object_name: str,
        bucket_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Upload file to MinIO.

        Args:
            file_path: Local file path
            object_name: S3 object name (key)
            bucket_name: Bucket name (default: self.bucket_name)
            metadata: Optional metadata headers

        Returns:
            bool: True if successful
        """
        bucket = bucket_name or self.bucket_name
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"❌ File not found: {file_path}")
            return False

        try:
            # Ensure bucket exists
            await self.ensure_bucket_exists(bucket)

            # Upload file
            self.client.fput_object(
                bucket,
                object_name,
                str(file_path),
                metadata=metadata,
            )

            logger.info(f"✅ Uploaded to S3: s3://{bucket}/{object_name}")
            return True

        except S3Error as e:
            logger.error(f"❌ Upload failed: {e}")
            return False

    def file_exists(self, object_name: str,
            bucket_name: Optional[str] = None, ) -> bool:
        """
        Check if file exists in MinIO.

        Args:
            object_name: S3 object name (key)
            bucket_name: Bucket name (default: self.bucket_name)

        Returns:
            bool: True if file exists
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.client.stat_object(bucket, object_name)
            logger.info(f"✅ File exists in S3: s3://{bucket}/{object_name}")
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.info(
                    f"❌ File not found in S3: s3://{bucket}/{object_name}")
                return False
            else:
                logger.error(f"❌ Error checking file existence: {e}")
                return False

    async def upload_bytes(
        self,
        data: bytes,
        object_name: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Upload bytes to MinIO.

        Args:
            data: Bytes to upload
            object_name: S3 object name (key)
            bucket_name: Bucket name (default: self.bucket_name)
            content_type: MIME type
            metadata: Optional metadata headers

        Returns:
            bool: True if successful
        """
        bucket = bucket_name or self.bucket_name

        try:
            # Ensure bucket exists
            await self.ensure_bucket_exists(bucket)

            # Create file-like object
            file_obj = io.BytesIO(data)

            # Upload
            self.client.put_object(
                bucket,
                object_name,
                file_obj,
                length=len(data),
                content_type=content_type,
                metadata=metadata,
            )

            logger.info(f"✅ Uploaded bytes to S3: s3://{bucket}/{object_name}")
            return True

        except S3Error as e:
            logger.error(f"❌ Upload failed: {e}")
            return False

    async def get_file(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Download file from MinIO.

        Args:
            object_name: S3 object name (key)
            bucket_name: Bucket name (default: self.bucket_name)

        Returns:
            bytes: File content, or None if error
        """
        bucket = bucket_name or self.bucket_name

        try:
            response = self.client.get_object(bucket, object_name)
            data = response.read()
            logger.info(f"✅ Downloaded from S3: s3://{bucket}/{object_name}")
            return data
        except S3Error as e:
            logger.error(f"❌ Download failed: {e}")
            return None

    async def get_presigned_url(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
        expiration: int = 3600,
    ) -> Optional[str]:
        """
        Get presigned URL for file access.

        Args:
            object_name: S3 object name (key)
            bucket_name: Bucket name (default: self.bucket_name)
            expiration: Expiration time in seconds (default: 3600)

        Returns:
            str: Presigned URL, or None if error
        """
        bucket = bucket_name or self.bucket_name

        try:
            url = self.client.get_presigned_url(
                "GET",
                bucket,
                object_name,
                expires=timedelta(seconds=expiration),
            )
            logger.debug(f"✅ Generated presigned URL: {url[:50]}...")
            return url
        except S3Error as e:
            logger.error(f"❌ Failed to generate presigned URL: {e}")
            return None

    async def delete_file(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
    ) -> bool:
        """
        Delete file from MinIO.

        Args:
            object_name: S3 object name (key)
            bucket_name: Bucket name (default: self.bucket_name)

        Returns:
            bool: True if successful
        """
        bucket = bucket_name or self.bucket_name

        try:
            self.client.remove_object(bucket, object_name)
            logger.info(f"✅ Deleted from S3: s3://{bucket}/{object_name}")
            return True
        except S3Error as e:
            logger.error(f"❌ Delete failed: {e}")
            return False

    async def list_buckets(self):
        """List all buckets"""
        try:
            buckets = self.client.list_buckets()
            return buckets
        except Exception as e:
            raise Exception(f"Failed to list buckets: {e}")

    async def list_objects(
        self,
        prefix: str = "",
        bucket_name: Optional[str] = None,
    ) -> list:
        """
        List objects in bucket.

        Args:
            prefix: Object name prefix filter
            bucket_name: Bucket name (default: self.bucket_name)

        Returns:
            list: Object names matching prefix
        """
        bucket = bucket_name or self.bucket_name
        objects = []

        try:
            for obj in self.client.list_objects(bucket, prefix=prefix):
                objects.append(obj.object_name)
            return objects
        except S3Error as e:
            logger.error(f"❌ List failed: {e}")
            return []

    async def close(self):
        """Close MinIO connection."""
        logger.info("🔒 MinIO client closed")
        # MinIO client doesn't need explicit cleanup
        pass
