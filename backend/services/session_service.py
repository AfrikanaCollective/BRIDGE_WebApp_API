# backend/services/session_service.py
"""
In-memory session tracking service for active users.

Tracks user engagement across the platform without external dependencies.
"""

import logging
from typing import Dict, Optional, Any, Set
from datetime import datetime, UTC, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)


class UserSession:
    """Represents an active user session."""

    def __init__(
            self,
            session_id: str,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None
    ):
        """
        Initialize user session.

        Args:
            session_id: Unique session identifier
            user_id: Optional user identifier
            ip_address: Client IP address
            user_agent: Browser user agent string
        """
        self.session_id = session_id
        self.user_id = user_id or f"anonymous_{uuid4().hex[:8]}"
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.created_at = datetime.now(UTC)
        self.last_activity = datetime.now(UTC)
        self.page_views = 1
        self.actions: list = []

    def update_activity(self, action: Optional[str] = None):
        """
        Update last activity timestamp.

        Args:
            action: Optional action description
        """
        self.last_activity = datetime.now(UTC)
        self.page_views += 1
        if action:
            self.actions.append({
                "action": action,
                "timestamp": self.last_activity.isoformat()
            })

    def get_duration_seconds(self) -> float:
        """Get session duration in seconds."""
        return (self.last_activity - self.created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "duration_seconds": self.get_duration_seconds(),
            "page_views": self.page_views,
            "actions_count": len(self.actions),
            "recent_actions": self.actions[-5:] if self.actions else []
        }


class SessionService:
    """
    Manages active user sessions in memory.

    Tracks:
    - Active sessions by user
    - Session duration and engagement
    - User activity patterns
    - Concurrent user count
    """

    def __init__(self, session_timeout_seconds: int = 3600):
        """
        Initialize session service.

        Args:
            session_timeout_seconds: Time before session expires (default: 1 hour)
        """
        self.sessions: Dict[str, UserSession] = {}
        self.session_timeout_seconds = session_timeout_seconds
        self.unique_users: Set[str] = set()
        logger.info(
            f"📋 Session service initialized "
            f"(timeout: {session_timeout_seconds}s)"
        )

    def create_session(
            self,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None
    ) -> str:
        """
        Create a new user session.

        Args:
            user_id: Optional user identifier
            ip_address: Client IP address
            user_agent: Browser user agent

        Returns:
            str: Session ID (can be stored in cookie)
        """
        session_id = str(uuid4())
        session = UserSession(session_id, user_id, ip_address, user_agent)

        self.sessions[session_id] = session
        self.unique_users.add(session.user_id)

        logger.debug(
            f"✅ Session created: {session_id} | User: {session.user_id} | "
            f"Active sessions: {len(self.sessions)} | Unique users: {len(self.unique_users)}"
        )

        return session_id

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            UserSession or None if not found/expired
        """
        session = self.sessions.get(session_id)

        if not session:
            return None

        # Check if session expired
        age = (datetime.now(UTC) - session.last_activity).total_seconds()
        if age > self.session_timeout_seconds:
            self.end_session(session_id)
            return None

        return session

    def update_session_activity(
            self,
            session_id: str,
            action: Optional[str] = None
    ) -> bool:
        """
        Update session activity (heartbeat).

        Args:
            session_id: Session identifier
            action: Optional action description

        Returns:
            bool: True if session updated
        """
        session = self.get_session(session_id)

        if not session:
            return False

        session.update_activity(action)
        return True

    def end_session(self, session_id: str) -> bool:
        """
        End a user session.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if session was removed
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            del self.sessions[session_id]

            logger.debug(
                f"✅ Session ended: {session_id} | User: {session.user_id} | "
                f"Duration: {session.get_duration_seconds():.2f}s | "
                f"Remaining sessions: {len(self.sessions)}"
            )

            return True

        return False

    def get_active_sessions_count(self) -> int:
        """
        Get count of active sessions (non-expired).

        Returns:
            int: Number of active sessions
        """
        # Clean up expired sessions
        self.cleanup_expired_sessions()
        return len(self.sessions)

    def get_active_users_count(self) -> int:
        """
        Get count of unique active users.

        Returns:
            int: Number of unique users with active sessions
        """
        self.cleanup_expired_sessions()

        # Count unique users with active sessions
        active_user_ids = set()
        for session in self.sessions.values():
            active_user_ids.add(session.user_id)

        return len(active_user_ids)

    def get_all_active_sessions(self) -> list:
        """
        Get all active sessions.

        Returns:
            list: Session details
        """
        self.cleanup_expired_sessions()
        return [session.to_dict() for session in self.sessions.values()]

    def get_all_active_users(self) -> Dict[str, Any]:
        """
        Get all active users with session details.

        Returns:
            dict: Grouped by user_id with session information
        """
        self.cleanup_expired_sessions()

        users = {}
        for session in self.sessions.values():
            if session.user_id not in users:
                users[session.user_id] = {
                    "user_id": session.user_id,
                    "sessions": [],
                    "total_page_views": 0,
                    "total_actions": 0,
                    "first_seen": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat()
                }

            users[session.user_id]["sessions"].append(session.to_dict())
            users[session.user_id]["total_page_views"] += session.page_views
            users[session.user_id]["total_actions"] += len(session.actions)

        return users

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.

        Returns:
            int: Number of sessions removed
        """
        now = datetime.now(UTC)
        expired = []

        for session_id, session in self.sessions.items():
            age = (now - session.last_activity).total_seconds()
            if age > self.session_timeout_seconds:
                expired.append(session_id)

        for session_id in expired:
            self.end_session(session_id)

        if expired:
            logger.info(
                f"🧹 Cleaned up {len(expired)} expired sessions | "
                f"Active: {len(self.sessions)} | Users: {len(self.unique_users)}"
            )

        return len(expired)

    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive session statistics.

        Returns:
            dict: Stats including active users, duration, engagement
        """
        self.cleanup_expired_sessions()

        if not self.sessions:
            return {
                "active_sessions": 0,
                "active_users": 0,
                "total_page_views": 0,
                "average_session_duration_seconds": 0.0,
                "average_page_views_per_session": 0.0,
                "concurrent_users": 0
            }

        # Get unique active users
        active_user_ids = set()
        total_duration = 0.0
        total_page_views = 0

        for session in self.sessions.values():
            active_user_ids.add(session.user_id)
            total_duration += session.get_duration_seconds()
            total_page_views += session.page_views

        avg_duration = total_duration / len(self.sessions) if self.sessions else 0.0
        avg_views = total_page_views / len(self.sessions) if self.sessions else 0.0

        return {
            "active_sessions": len(self.sessions),
            "active_users": len(active_user_ids),
            "concurrent_users": len(active_user_ids),
            "total_page_views": total_page_views,
            "average_session_duration_seconds": round(avg_duration, 2),
            "average_page_views_per_session": round(avg_views, 2),
            "timestamp": datetime.now(UTC).isoformat()
        }
