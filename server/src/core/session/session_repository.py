from typing import Dict, Optional
from threading import Lock

from ...utils import get_logger
from .session import Session

logger = get_logger(__name__)


class SessionRepository:
    """In-memory session storage repository."""

    _sessions: Dict[str, Session] = {}
    _lock = Lock()

    @classmethod
    def create_session(cls, duration_hours: int = 1) -> Session:
        """Create a new session and store it in memory."""
        session = Session.create_new(duration_hours)

        with cls._lock:
            cls._sessions[session.id] = session
            logger.info(f"Created new session: {session.id}")

        return session

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        """Retrieve session by ID."""
        with cls._lock:
            session = cls._sessions.get(session_id)

            if session and not session.is_valid():
                # Clean up expired session
                del cls._sessions[session_id]
                logger.info(f"Removed expired session: {session_id}")
                return None

            return session

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """Remove all expired sessions from memory. Returns count of removed sessions."""
        removed_count = 0

        with cls._lock:
            expired_sessions = [
                session_id
                for session_id, session in cls._sessions.items()
                if not session.is_valid()
            ]

            for session_id in expired_sessions:
                del cls._sessions[session_id]
                removed_count += 1

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} expired sessions")

        return removed_count

    @classmethod
    def get_active_session_count(cls) -> int:
        """Get count of active sessions."""
        with cls._lock:
            return len([s for s in cls._sessions.values() if s.is_valid()])
