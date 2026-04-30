"""
Application settings loaded from environment variables and .env file.
"""
import logging
from typing import List
from pydantic import Field
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration settings."""

    # ==================== API Configuration ====================
    API_TITLE: str = Field(default="BRIDGE Form Processor API")
    API_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # ==================== CORS ====================
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "https://yourdomain.com"]
    )
    CORS_CREDENTIALS: bool = Field(default=True)
    CORS_METHODS: List[str] = Field(default=["*"])
    CORS_HEADERS: List[str] = Field(default=["*"])

    # ==================== MongoDB ====================
    MONGODB_URL: str = Field(default="mongodb://root:password@localhost:27017")
    MONGODB_DB_NAME: str = Field(default="bridge_form_processor")
    MONGODB_DB_COLLECTION: str = Field(default="webui_form_processor_stats")
    MONGODB_TIMEOUT: int = Field(default=5000)  # milliseconds
    MONGODB_HOST: str = Field(default="localhost", env="MONGODB_HOST")
    MONGODB_PORT: int = Field(default=27017, env="MONGODB_PORT")
    MONGODB_USERNAME: str = Field(default="admin", env="MONGODB_USERNAME")
    MONGODB_PASSWORD: str = Field(default="@Dmin2o13!", env="MONGODB_PASSWORD")
    MONGODB_AUTH_SOURCE: str = Field(default="admin", env="MONGODB_AUTH_SOURCE")
    MONGODB_DB_NAME: str = Field(default="bridge_form_processor", env="MONGODB_DB_NAME")
    MONGODB_DB_COLLECTION: str = Field(
        default="webui_form_processor_stats",
        env="MONGODB_DB_COLLECTION"
    )
    MONGODB_POOL_SIZE: int = Field(default=10, env="MONGODB_POOL_SIZE")
    MONGODB_MAX_IDLE_TIME: int = Field(default=45000, env="MONGODB_MAX_IDLE_TIME")

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
    UPLOAD_TEMP_DIR: str = Field(default="/tmp/uploads")
    LOG_DIR: str = Field(default="/tmp/logs")

    # ==================== Prompts ====================
    PROMPTS_DIR: str = Field(default="./prompts")
    DEFAULT_PROMPT_FILE: str = Field(default="DEFAULT.txt")
    DEFAULT_PROMPT_FALLBACK: bool = Field(default=True)

    # ==================== Agents ====================
    AGENTS_DIR: str = Field(default="./app/agents")

    # ==================== Logging ====================
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # ==================== Environment ====================
    ENVIRONMENT: str = Field(default="development")  # development, staging, production

    class Config:
        """Pydantic settings configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from .env

    def __init__(self, **data):
        """Initialize settings and log configuration."""
        super().__init__(**data)
        self._log_configuration()

    def _log_configuration(self):
        """Log loaded configuration (with sensitive fields masked)."""
        logger.info("=" * 80)
        logger.info("🔧 Application Settings Loaded")
        logger.info("=" * 80)

        # Settings to display (non-sensitive)
        public_settings = {
            "API_TITLE": self.API_TITLE,
            "API_VERSION": self.API_VERSION,
            "ENVIRONMENT": self.ENVIRONMENT,
            "DEBUG": self.DEBUG,
            "HOST": self.HOST,
            "PORT": self.PORT,
            "CORS_ORIGINS": self.CORS_ORIGINS,
            "MAX_FILE_SIZE": f"{self.MAX_FILE_SIZE / (1024*1024):.1f} MB",
            "QWEN_MODEL": self.QWEN_MODEL,
            "QWEN_SERVICE_URL": self.QWEN_SERVICE_URL,
            "MONGODB_URL": self._mask_url(self.MONGODB_URL),
            "REDIS_HOST": self.REDIS_HOST,
            "REDIS_PORT": self.REDIS_PORT,
            "MINIO_ENDPOINT": self.MINIO_ENDPOINT,
            "MINIO_BUCKET_NAME": self.MINIO_BUCKET_NAME,
            "UPLOAD_TEMP_DIR": self.UPLOAD_TEMP_DIR,
            "LOG_DIR": self.LOG_DIR,
        }

        for key, value in public_settings.items():
            logger.info(f"  {key:30} = {value}")

        logger.info("=" * 80)

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
            mongodb://admin:%40Dmin2o13%21@localhost:27017/bridge_form_processor?authSource=admin
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

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"


# Create singleton instance
settings = Settings()
