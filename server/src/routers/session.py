from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from ..core.session import SessionRepository
from ..utils import verify_turnstile_token, get_logger
from ..config import get_settings

logger = get_logger(__name__)

router = APIRouter(prefix="/session")

settings = get_settings()


class CreateSessionRequest(BaseModel):
    turnstile_token: str = Field(..., description="Cloudflare Turnstile token")


class CreateSessionResponse(BaseModel):
    session_id: str
    expires_at: str


@router.post("/create")
async def create_session(
    request: CreateSessionRequest, fastapi_request: Request
) -> CreateSessionResponse:
    """Create a new session after verifying Turnstile token."""
    if not settings.enable_turnstile:
        raise HTTPException(
            status_code=400, detail="Turnstile verification is disabled"
        )

    # Validate Turnstile token before creating session
    client_ip = fastapi_request.client.host if fastapi_request.client else None
    await verify_turnstile_token(request.turnstile_token, remoteip=client_ip or "")

    # Create new session (valid for 1 hour)
    session = SessionRepository.create_session(duration_hours=1)

    logger.info(f"Created session {session.id} for client {client_ip}")

    return CreateSessionResponse(
        session_id=session.id, expires_at=session.expires_at.isoformat()
    )


def verify_session(session_id: str | None) -> None:
    """Verify that a session is valid. Raises HTTPException if not."""
    if settings.enable_turnstile is False:
        return  # Skip verification if Turnstile is disabled

    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID is required")

    session = SessionRepository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if not session.is_valid():
        raise HTTPException(status_code=401, detail="Session has expired")
