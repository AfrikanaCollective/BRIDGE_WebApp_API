# backend/app/main.py
"""
FastAPI application with lifespan management and service injection.
Properly initializes MongoDB with authentication.
Redis has been removed from the tech stack.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.clients.mongo_client import MongoClient
from app.clients.minio_client import MinIOClient
from app.services.form_processor import FormProcessor
from app.services.storage_service import StorageService
from app.routes import upload, history, health

logger = logging.getLogger(__name__)

_services = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""

    # ==================== STARTUP ====================
    logger.info("🚀 Starting up application...")

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
            health = await mongo_client.health_check()
            if health["connected"]:
                logger.info(f"✅ MongoDB authenticated: {settings.MONGODB_AUTH_SOURCE}")
                logger.info(f"   Server: {health['server_info'].get('version', 'unknown')}")
                logger.info(f"   Database: {settings.MONGODB_DB_NAME}")
                logger.info(f"   Collection: {settings.MONGODB_DB_COLLECTION}")
            else:
                raise Exception(f"MongoDB health check failed: {health.get('error')}")

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

            form_processor = FormProcessor(
                storage_service=storage_service
            )

            logger.info("✅ Services initialized successfully")

        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            raise

        # ==================== STORE SERVICE INSTANCES ====================
        _services["mongo"] = mongo_client
        _services["minio"] = minio_client
        _services["storage"] = storage_service
        _services["form_processor"] = form_processor

        # ==================== INJECT INTO ROUTES ====================
        upload.form_processor = form_processor
        upload.storage_service = storage_service
        history.mongo_client = mongo_client
        health.services = _services

        logger.info("✅ All services initialized and injected into routes")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}", exc_info=True)
        raise

    yield

    # ==================== SHUTDOWN ====================
    logger.info("🛑 Shutting down application...")

    try:
        if "mongo" in _services:
            await _services["mongo"].close()
            logger.info("✅ MongoDB connection closed")

        if "minio" in _services:
            await _services["minio"].close()
            logger.info("✅ MinIO connection closed")

        logger.info("✅ All services closed gracefully")

    except Exception as e:
        logger.error(f"❌ Shutdown error: {e}")


def create_app() -> FastAPI:
    """Create FastAPI application."""

    app = FastAPI(
        title=settings.API_TITLE,
        version=settings.API_VERSION,
        description="Bridge Form Processor - Medical form processing pipeline",
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # ==================== CORS MIDDLEWARE ====================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )

    # ==================== ROUTES ====================
    app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
    app.include_router(history.router, prefix="/api/history", tags=["history"])
    app.include_router(health.router, prefix="/api/health", tags=["health"])

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
