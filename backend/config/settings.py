"""
Application settings loaded from environment variables and .env file.
"""
import ssl
import json
import logging
from typing import List
from pathlib import Path
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration settings."""

    # ==================== API Configuration ====================
    API_TITLE: str = Field(default="BRIDGE Form Processor API")
    API_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=6443)

    # ==================== SSL/TLS CONFIGURATION ====================
    USE_HTTPS: bool = Field(default=True, env="USE_HTTPS")
    SSL_CERT_FILE: str = Field(default="/app/certs/public.crt", env="SSL_CERT_FILE")
    SSL_KEY_FILE: str = Field(default="/app/certs/private.key", env="SSL_KEY_FILE")
    SSL_VERIFY: bool = Field(default=False, env="SSL_VERIFY")

    # ==================== CORS ====================
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "https://bridge.kemri-wellcome.org"]
    )
    CORS_CREDENTIALS: bool = Field(default=True)
    CORS_METHODS: List[str] = Field(default=["*"])
    CORS_HEADERS: List[str] = Field(default=["*"])
    EXPOSE_HEADERS: List[str] = Field(default=["*"])

    # ==================== MongoDB ====================
    MONGODB_URL: str = Field(default="mongodb://root:password@localhost:27017")
    MONGODB_HOST: str = Field(default="localhost", env="MONGODB_HOST")
    MONGODB_PORT: int = Field(default=27017, env="MONGODB_PORT")
    MONGODB_USERNAME: str = Field(default="root", env="MONGODB_USERNAME")
    MONGODB_PASSWORD: str = Field(default="pass", env="MONGODB_PASSWORD")
    MONGODB_AUTH_SOURCE: str = Field(default="admin", env="MONGODB_AUTH_SOURCE")
    MONGODB_DB_NAME: str = Field(default="bridge_form_processor", env="MONGODB_DB_NAME")
    MONGODB_DB_COLLECTION: str = Field(
        default="webui_form_processor_stats",
        env="MONGODB_DB_COLLECTION"
    )
    MONGODB_POOL_SIZE: int = Field(default=10, env="MONGODB_POOL_SIZE")
    MONGODB_MAX_IDLE_TIME: int = Field(default=45000, env="MONGODB_MAX_IDLE_TIME")
    MONGODB_TIMEOUT: int = Field(default=5000)  # milliseconds

    # ==================== MinIO S3 ====================
    MINIO_ENDPOINT: str = Field(default="localhost:9000")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin")
    MINIO_SECRET_KEY: str = Field(default="minioadmin")
    MINIO_BUCKET_NAME: str = Field(default="forms")
    MINIO_SECURE: bool = Field(default=False)
    MINIO_REGION: str = Field(default="us-east-1")

    # ==================== Qwen API (Docker Service) ====================
    QWEN_SERVICE_URL: str = Field(default="https://localhost:8443")
    QWEN_MODEL: str = Field(default="qwen-turbo")
    QWEN_REQUEST_TIMEOUT: int = Field(default=600)  # seconds
    QWEN_MAX_RETRIES: int = Field(default=3)

    # ==================== File Upload ====================
    MAX_FILE_SIZE: int = Field(default=15 * 1024 * 1024)  # 15MB
    ALLOWED_EXTENSIONS: List[str] = Field(
        default=["png"]
    )
    UPLOAD_TEMP_DIR: str = Field(default="/app/tmp/uploads")
    LOG_DIR: str = Field(default="/app/logs")

    # ==================== Prompts ====================
    PROMPTS_DIR: str = Field(default="/app/prompts")
    DEFAULT_PROMPT_FILE: str = Field(default="DEFAULT.txt")
    DEFAULT_PROMPT_FALLBACK: bool = Field(default=True)

    # ==================== Agents ====================
    AGENTS_DIR: str = Field(default="/app/agents")

    # ==================== Logging ====================
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # ==================== Session ====================
    SESSION_TIMEOUT_SECONDS: int = Field(default=3600) # 1 hour
    SESSION_CLEANUP_INTERVAL_SECONDS: int = Field(default=300)  # Clean up every 5 minutes

    # ==================== Form types ====================
    FORM_TYPES: List[str] = Field(
        default=["NAR"]
    )

    # ==================== Environment ====================
    ENVIRONMENT: str = Field(default="development")  # development, staging, production

    class Config:
        """Pydantic settings configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env

    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from JSON string or list"""
        if isinstance(v, str):
            try:
                # Remove quotes and parse JSON
                v = v.strip().strip("'\"")
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse CORS_ORIGINS JSON: {e}")
                # Fallback: treat as single origin
                return [v]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "https://bridge.kemri-wellcome.org"]

    @field_validator('CORS_HEADERS', mode='before')
    @classmethod
    def parse_cors_headers(cls, v):
        """Parse CORS_HEADERS from JSON string or list"""
        if isinstance(v, str):
            try:
                # Remove quotes and parse JSON
                v = v.strip().strip("'\"")
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse CORS_HEADERS JSON: {e}")
                # Fallback: treat as single origin
                return [v]
        elif isinstance(v, list):
            return v
        return ["*"]

    @field_validator('CORS_METHODS', mode='before')
    @classmethod
    def parse_cors_methods(cls, v):
        """Parse CORS_METHODS from JSON string or list"""
        if isinstance(v, str):
            try:
                # Remove quotes and parse JSON
                v = v.strip().strip("'\"")
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse CORS_METHODS JSON: {e}")
                # Fallback: treat as single origin
                return [v]
        elif isinstance(v, list):
            return v
        return ["GET", "POST"]

    @field_validator('EXPOSE_HEADERS', mode='before')
    @classmethod
    def parse_expose_headers(cls, v):
        """Parse EXPOSE_HEADERS from JSON string or list"""
        if isinstance(v, str):
            try:
                # Remove quotes and parse JSON
                v = v.strip().strip("'\"")
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse EXPOSE_HEADERS JSON: {e}")
                # Fallback: treat as single origin
                return [v]
        elif isinstance(v, list):
            return v
        return ["*"]

    @field_validator('FORM_TYPES', mode='before')
    @classmethod
    def parse_form_types(cls, v):
        """Parse FORM_TYPES from JSON string or list"""
        if isinstance(v, str):
            try:
                # Remove quotes and parse JSON
                v = v.strip().strip("'\"")
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse FORM_TYPES JSON: {e}")
                # Fallback: treat as single origin
                return [v]
        elif isinstance(v, list):
            return v
        return ["NAR"]

    def __init__(self, **data):
        """Initialize settings and log configuration."""
        super().__init__(**data)
        self.log_configuration()

    @field_validator('ALLOWED_EXTENSIONS', mode='before')
    @classmethod
    def parse_allowed_extensions(cls, v):
        """Parse ALLOWED_EXTENSIONS from JSON string or list"""
        if isinstance(v, str):
            try:
                # Remove quotes and parse JSON
                v = v.strip().strip("'\"")
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse ALLOWED_EXTENSIONS JSON: {e}")
                # Fallback: treat as single origin
                return [v]
        elif isinstance(v, list):
            return v
        return ["png"]

    def __init__(self, **data):
        """Initialize settings and log configuration."""
        super().__init__(**data)
        self.log_configuration()

    @staticmethod
    def _mask_url(url: str, show_chars: int = 3) -> str:
        """Mask sensitive parts of connection URLs."""
        if "://" not in url:
            return url

        protocol, rest = url.split("://", 1)

        # Handle format: user:password@host:port/path
        if "@" in rest:
            credentials, host_part = rest.rsplit("@", 1)
            masked_creds = credentials[:show_chars] + "*" * (len(credentials) - show_chars)
            return f"{protocol}://{masked_creds}@{host_part}"

        return f"{protocol}://{rest[:show_chars]}****"

    def get_mongodb_uri(self) -> str:
        """
        Build MongoDB connection URI with authentication.

        Handles special characters in password using URL encoding.

        Connection string format:
        mongodb://username:password@host:port/database?authSource=admin

        Returns:
            str: MongoDB connection URI

        Example:
            mongodb://admin:%40Dmin2o13%21@localhost:27017/bridge_webui_mvp?authSource=admin
        """
        # URL-encode password to handle special characters
        encoded_password = quote_plus(self.MONGODB_PASSWORD)
        encoded_username = quote_plus(self.MONGODB_USERNAME)

        uri = (
            f"mongodb://{encoded_username}:{encoded_password}@"
            f"{self.MONGODB_HOST}:{self.MONGODB_PORT}/"
            f"{self.MONGODB_DB_NAME}"
            f"?authSource={self.MONGODB_AUTH_SOURCE}"
            f"&maxPoolSize={self.MONGODB_POOL_SIZE}"
            f"&maxIdleTimeMS={self.MONGODB_MAX_IDLE_TIME}"
        )

        return uri

    def get_mongodb_uri_safe(self) -> str:
        """
        Get MongoDB URI with password masked for logging.

        Returns:
            str: MongoDB URI with password replaced by ****
        """
        encoded_username = quote_plus(self.MONGODB_USERNAME)
        uri = (
            f"mongodb://{encoded_username}:****@"
            f"{self.MONGODB_HOST}:{self.MONGODB_PORT}/"
            f"{self.MONGODB_DB_NAME}"
            f"?authSource={self.MONGODB_AUTH_SOURCE}"
        )
        return uri

    def get_minio_config(self) -> dict:
        """Get MinIO configuration dictionary."""
        return {
            "endpoint": self.MINIO_ENDPOINT,
            "access_key": self.MINIO_ACCESS_KEY,
            "secret_key": self.MINIO_SECRET_KEY,
            "bucket_name": self.MINIO_BUCKET_NAME,
            "secure": self.MINIO_SECURE,
            "region": self.MINIO_REGION,
        }

    def get_qwen_config(self) -> dict:
        """Get Qwen API configuration dictionary."""
        return {
            "service_url": self.QWEN_SERVICE_URL,
            "model": self.QWEN_MODEL,
            "timeout": self.QWEN_REQUEST_TIMEOUT,
            "max_retries": self.QWEN_MAX_RETRIES,
        }

    # ==================== SSL CONFIGURATION ====================
    def get_ssl_context(self) -> ssl.SSLContext | None:
        """
        Create SSL context for aiohttp client.
        Used for communicating with external services (Qwen, etc.) when HTTPS is enabled.

        Returns:
            ssl.SSLContext or None: SSL context for secure connections
        """
        if not self.USE_HTTPS:
            return None

        if self.SSL_VERIFY:
            # Use default context with certificate verification
            ssl_context = ssl.create_default_context()
            logger.info("✅ SSL context configured (certificate verification enabled)")
        else:
            # For self-signed certificates, disable SSL verification
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            logger.info("✅ SSL context configured (self-signed certificates allowed)")

        return ssl_context

    def get_uvicorn_ssl_config(self) -> tuple[str | None, str | None]:
        """
        Prepare SSL configuration for Uvicorn server.

        Returns:
            tuple: (ssl_keyfile, ssl_certfile) or (None, None) if HTTPS disabled

        Raises:
            FileNotFoundError: If certificate or key files are missing
        """
        if not self.USE_HTTPS:
            logger.info("ℹ️  HTTPS disabled - running on HTTP")
            return None, None

        cert_path = Path(self.SSL_CERT_FILE)
        key_path = Path(self.SSL_KEY_FILE)

        # Verify certificate exists
        if not cert_path.exists():
            raise FileNotFoundError(
                f"❌ SSL certificate not found: {cert_path.absolute()}\n"
                f"   Expected at: {cert_path.absolute()}\n"
                f"   Please ensure public.crt is in the certs folder"
            )

        # Verify key exists
        if not key_path.exists():
            raise FileNotFoundError(
                f"❌ SSL key not found: {key_path.absolute()}\n"
                f"   Expected at: {key_path.absolute()}\n"
                f"   Please ensure private.key is in the certs folder"
            )

        # Verify file permissions (key should not be world-readable)
        key_stat = key_path.stat()
        if key_stat.st_mode & 0o077:
            logger.warning(
                f"⚠️  Warning: Private key may have overly permissive permissions: "
                f"{oct(key_stat.st_mode)}"
            )

        logger.info("✅ SSL certificates validated:")
        logger.info(f"   📜 Certificate: {cert_path.absolute()}")
        logger.info(f"   🔑 Key: {key_path.absolute()}")
        logger.info(f"   🔒 Verification: {'Enabled' if self.SSL_VERIFY else 'Disabled (self-signed)'}")

        return str(key_path), str(cert_path)

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"

    # ==================== LOGGING CONFIGURATION ====================
    def log_configuration(self) -> None:
        """Log configuration settings (with masked secrets)."""
        logger.info("=" * 60)
        logger.info("📋 Configuration Summary")
        logger.info("=" * 60)

        logger.info(f"Environment: {self.ENVIRONMENT}")

        # API Configuration
        logger.info("🔌 API Configuration:")
        logger.info(f"   Host: {self.API_HOST}")
        logger.info(f"   Port: {self.API_PORT}")
        logger.info(f"   HTTPS: {'Enabled' if self.USE_HTTPS else 'Disabled'}")
        logger.info(f"   Debug: {self.DEBUG}")

        # SSL Configuration
        logger.info("🔐 SSL/TLS Configuration:")
        logger.info(f"   HTTPS Enabled: {self.USE_HTTPS}")
        logger.info(f"   Certificate File: {self.SSL_CERT_FILE}")
        logger.info(f"   Key File: {self.SSL_KEY_FILE}")
        logger.info(f"   Verify Certificates: {self.SSL_VERIFY}")

        # MongoDB Configuration
        logger.info("🗄️  MongoDB Configuration:")
        logger.info(f"   Host: {self.MONGODB_HOST}:{self.MONGODB_PORT}")
        logger.info(f"   Database: {self.MONGODB_DB_NAME}")
        logger.info(f"   Collection: {self.MONGODB_DB_COLLECTION}")
        logger.info(f"   Auth Source: {self.MONGODB_AUTH_SOURCE}")
        logger.info(f"   Pool Size: {self.MONGODB_POOL_SIZE}")
        logger.info(f"   Max Idle Time: {self.MONGODB_MAX_IDLE_TIME}ms")

        # MinIO Configuration
        logger.info("🪣 MinIO Configuration:")
        logger.info(f"   Endpoint: {self.MINIO_ENDPOINT}")
        logger.info(f"   Bucket: {self.MINIO_BUCKET_NAME}")
        logger.info(f"   Secure: {self.MINIO_SECURE}")
        logger.info(f"   Region: {self.MINIO_REGION}")

        # Qwen Configuration
        logger.info("🤖 Qwen LLM Configuration:")
        logger.info(f"   Service URL: {self.QWEN_SERVICE_URL}")
        logger.info(f"   Model: {self.QWEN_MODEL}")
        logger.info(f"   Timeout: {self.QWEN_REQUEST_TIMEOUT}s")
        logger.info(f"   Max Retries: {self.QWEN_MAX_RETRIES}")

        # File Upload Configuration
        logger.info("📁 File Upload Configuration:")
        logger.info(f"   Max Size: {self.MAX_FILE_SIZE}MB")
        logger.info(f"   Allowed Extensions: {', '.join(self.ALLOWED_EXTENSIONS)}")

        # CORS Configuration
        logger.info("🌐 CORS Configuration:")
        logger.info(f"   Origins: {', '.join(self.CORS_ORIGINS[:20])}...")
        logger.info(f"   Credentials: {self.CORS_CREDENTIALS}")

        logger.info("=" * 60)


# Create singleton instance
settings = Settings()
