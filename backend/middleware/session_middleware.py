# backend/middleware/session_middleware.py
"""
Middleware to track active user sessions.
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SessionTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track user sessions on each request.

    - Creates session on first request
    - Updates activity on subsequent requests
    - Cleans expired sessions periodically
    """

    COOKIE_NAME = "session_id"
    EXCLUDED_PATHS = {
        "/api/health",
        "/docs",
        "/openapi.json",
        "/favicon.ico"
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and track session.

        Args:
            request: FastAPI request
            call_next: Next middleware/route

        Returns:
            Response with session cookie
        """
        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        try:
            session_service = getattr(request.app.state, 'session_service', None)

            if not session_service:
                return await call_next(request)

            # Get session ID from cookie
            session_id = request.cookies.get(self.COOKIE_NAME)

            # Get client info
            ip_address = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")

            # Create or update session
            if not session_id:
                # New session
                session_id = session_service.create_session(
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                logger.debug(f"🆕 Created session: {session_id} from {ip_address}")
            else:
                # Update existing session
                action = f"{request.method} {request.url.path}"
                updated = session_service.update_session_activity(session_id, action)

                if not updated:
                    # Session expired, create new one
                    session_id = session_service.create_session(
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    logger.debug(f"🔄 Session expired, created new: {session_id}")

            # Process request
            response = await call_next(request)

            # Add session cookie to response
            response.set_cookie(
                key=self.COOKIE_NAME,
                value=session_id,
                max_age=3600,  # 1 hour
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )

            return response

        except Exception as e:
            logger.error(f"❌ Session tracking error: {e}", exc_info=True)
            return await call_next(request)
