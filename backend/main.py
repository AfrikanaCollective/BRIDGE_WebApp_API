# backend/main.py
"""
FastAPI application with lifespan management and service injection.
Properly initializes MongoDB with authentication.

"""

import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middleware.session_middleware import SessionTrackingMiddleware

from config.settings import settings
from routes import upload, history, health, stats
from clients.mongo_client import MongoClient
from clients.minio_client import MinIOClient
from services.form_processor import FormProcessor
from services.storage_service import StorageService
from services.session_service import SessionService
from services.bulk_upload_service import BulkUploadService


logger = logging.getLogger(__name__)


# ✅ CHANGE 1: Create Services class for type safety
class Services:
    """Container for application services."""

    def __init__(
            self,
            mongo: MongoClient,
            minio: MinIOClient,
            storage: StorageService,
            form_processor: FormProcessor,
            session: SessionService,
            bulk_upload: BulkUploadService,
    ):
        self.mongo = mongo
        self.minio = minio
        self.storage = storage
        self.form_processor = form_processor
        self.session = session
        self.bulk_upload = bulk_upload

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""

    # ==================== STARTUP ====================
    logger.info("🚀 Starting up application...")

    mongo_client: Optional[MongoClient] = None
    minio_client: Optional[MinIOClient] = None
    storage_service: Optional[StorageService] = None
    form_processor: Optional[FormProcessor] = None
    session_service: Optional[SessionService] = None
    bulk_upload_service: Optional[BulkUploadService] = None

    try:
        # Log configuration (with masked secrets)
        settings.log_configuration()

        # ==================== MONGODB INITIALIZATION ====================
        logger.info("🗄️  Initializing MongoDB...")
        try:
            mongo_uri = settings.get_mongodb_uri()
            mongo_client = MongoClient(
                uri=mongo_uri,
                db_name=settings.MONGODB_DB_NAME,
            )

            # Test connection and authentication
            health_check = await mongo_client.health_check()
            if health_check["connected"]:
                logger.info(f"✅ MongoDB authenticated: {settings.MONGODB_AUTH_SOURCE}")
                logger.info(f"   Server: {health_check['server_info'].get('version', 'unknown')}")
                logger.info(f"   Database: {settings.MONGODB_DB_NAME}")
                logger.info(f"   Collection: {settings.MONGODB_DB_COLLECTION}")
            else:
                raise Exception(f"MongoDB health check failed: {health_check.get('error')}")

            # Ensure collection exists
            await mongo_client.create_collection_if_not_exists(
                settings.MONGODB_DB_COLLECTION
            )

            # Create indexes for optimal query performance
            indexes = {
                "timestamp": -1,
                "form_type": 1,
                "case_id": 1,
                "status": 1,
            }
            await mongo_client.create_indexes(
                settings.MONGODB_DB_COLLECTION,
                indexes
            )

        except Exception as e:
            logger.error(f"❌ MongoDB initialization failed: {e}")
            raise

        # ==================== MINIO INITIALIZATION ====================
        logger.info("🪣 Initializing MinIO...")
        try:
            minio_config = settings.get_minio_config()
            minio_client = MinIOClient(
                endpoint=minio_config["endpoint"],
                access_key=minio_config["access_key"],
                secret_key=minio_config["secret_key"],
                bucket_name=minio_config["bucket_name"],
                secure=minio_config["secure"],
                region=minio_config["region"],
            )

            # ✅ VERIFY: Check that client has list_buckets capability
            try:
                buckets = minio_client.client.list_buckets()  # Test call
                logger.info(f"✅ MinIO initialized with {len(buckets)} buckets")
            except Exception as e:
                logger.error(f"❌ MinIO initialization failed: {e}")
                raise

            # Ensure bucket exists
            await minio_client.ensure_bucket_exists()
            logger.info(f"✅ MinIO ready: {minio_config['bucket_name']}")

        except Exception as e:
            logger.error(f"❌ MinIO initialization failed: {e}")
            raise

        # ==================== SERVICE INITIALIZATION ====================
        logger.info("🔧 Initializing services...")
        try:
            storage_service = StorageService(
                mongo_client=mongo_client,
                minio_client=minio_client,
                db_name=settings.MONGODB_DB_NAME,
                collection_name=settings.MONGODB_DB_COLLECTION,
            )

            # ✅ CHANGE: Pass mongo_client to FormProcessor
            form_processor = FormProcessor(
                storage_service=storage_service,
                mongo_client=mongo_client,
            )

            bulk_upload_service = BulkUploadService(
                form_processor=form_processor,
                storage_service=storage_service,
            )

            logger.info("✅ Services initialized successfully")

        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            raise

        # ==================== SESSION SERVICE INITIALIZATION ====================
        logger.info("📋 Initializing SessionService...")
        try:
            session_service = SessionService(
                session_timeout_seconds=settings.SESSION_TIMEOUT_SECONDS
            )
            logger.info(
                f"✅ SessionService initialized "
                f"(timeout: {settings.SESSION_TIMEOUT_SECONDS}s)"
            )

        except Exception as e:
            logger.error(f"❌ SessionService initialization failed: {e}", exc_info=True)
            raise

        # ✅ CHANGE 2: Create Services instance and store in app.state
        services = Services(
            mongo=mongo_client,
            minio=minio_client,
            storage=storage_service,
            form_processor=form_processor,
            session=session_service,
            bulk_upload=bulk_upload_service,
        )

        app.state.services = services
        app.state.form_processor = form_processor
        app.state.storage = storage_service
        app.state.mongo = mongo_client
        app.state.minio = minio_client
        app.state.session_service = session_service
        app.state.bulk_upload = bulk_upload_service

        # ✅ CHANGE 3: Update route injection to use app.state
        # (Routes will access services via request.app.state)
        logger.info("✅ Services stored in app.state and ready for injection")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}", exc_info=True)
        raise

    yield

    # ==================== SHUTDOWN ====================
    logger.info("🛑 Shutting down application...")

    try:
        # ✅ CHANGE 4: Improved shutdown with proper null checks
        if mongo_client is not None:
            await mongo_client.close()
            logger.info("✅ MongoDB connection closed")

        if minio_client is not None:
            await minio_client.close()
            logger.info("✅ MinIO connection closed")

        # Clean up sessions
        if session_service is not None:
            expired_count = session_service.cleanup_expired_sessions()
            logger.info(f"✅ SessionService cleaned up: {expired_count} expired sessions")

        logger.info("✅ All services closed gracefully")

    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}", exc_info=True)


def create_app() -> FastAPI:
    """Create FastAPI application."""

    root_path = ""
    if settings.ENVIRONMENT == "production":
        root_path = settings.ROOT_PATH

    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="data BRIDGE LLM form Processor - Medical form processing pipeline",
        debug=settings.DEBUG,
        lifespan=lifespan,
        root_path=root_path,
        redirect_slashes=False,
    )

    # ==================== SESSION MIDDLEWARE ====================
    app.add_middleware(SessionTrackingMiddleware)

    # ==================== CORS MIDDLEWARE ====================
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=settings.CORS_METHODS,
            allow_headers=settings.CORS_HEADERS,
            expose_headers=settings.EXPOSE_HEADERS,
        )
    else:
        logger.warning("⚠️  CORS_ORIGINS is empty!")


    # ==================== ROUTES ====================
    app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
    app.include_router(history.router, prefix="/api/history", tags=["history"])
    app.include_router(health.router, prefix="/api/health", tags=["health"])
    app.include_router(stats.router, prefix="/api/stats", tags=["stats"])

    # ==================== ROOT ENDPOINT ====================
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": settings.API_TITLE,
            "version": settings.API_VERSION,
            "environment": settings.ENVIRONMENT,
            "status": "ready",
        }

    return app


# Global app instance
app = create_app()
