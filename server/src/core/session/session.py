from datetime import datetime, timedelta, UTC
from pydantic import BaseModel
import time
import uuid


class Session(BaseModel):
    """Session model for tracking user sessions."""

    id: str
    created_at: datetime
    expires_at: datetime

    @classmethod
    def create_new(cls, duration_hours: int = 1) -> "Session":
        """Create a new session with specified duration."""
        now = datetime.fromtimestamp(time.time(), tz=UTC)
        return cls(
            id=str(uuid.uuid4()),
            created_at=now,
            expires_at=now + timedelta(hours=duration_hours),
        )

    def is_valid(self) -> bool:
        """Check if session is still valid (not expired and active)."""
        return datetime.fromtimestamp(time.time(), tz=UTC) < self.expires_at
