# backend/server.py
"""
SSL-enabled Uvicorn server configuration.
Handles SSL certificate loading and server startup.
"""
import sys
import logging
import uvicorn
from pathlib import Path
from main import app
from config.settings import settings

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path(f"{settings.LOG_DIR}/app.log").absolute()),
        ],
    )


def run_server() -> None:
    """
    Start Uvicorn server with SSL configuration.

    Raises:
        FileNotFoundError: If SSL certificates are missing
    """
    configure_logging()

    try:
        # Get SSL configuration
        ssl_keyfile, ssl_certfile = settings.get_uvicorn_ssl_config()

        # Prepare Uvicorn configuration
        config = uvicorn.Config(
            app=app,
            host=settings.API_HOST,
            port=settings.API_PORT,
            log_level=settings.LOG_LEVEL.lower(),
            access_log=True,
            use_colors=True,
        )

        # Add SSL configuration if enabled
        if settings.USE_HTTPS:
            config.ssl_keyfile = ssl_keyfile
            config.ssl_certfile = ssl_certfile
            logger.info(f"🔒 HTTPS enabled on port {settings.API_PORT}")
        else:
            logger.info(f"🔓 HTTP enabled on port {settings.API_PORT}")

        # Create and run server
        server = uvicorn.Server(config)
        server.run()

    except FileNotFoundError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server()
