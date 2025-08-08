import httpx
from fastapi import HTTPException

from ..config import get_settings

settings = get_settings()


async def verify_turnstile_token(token: str, remoteip: str | None = None) -> bool:
    """
    Verify Cloudflare Turnstile token with Cloudflare API.
    Returns True if valid, else raises HTTPException.
    """
    data = {
        "secret": settings.turnstile_secret_key,
        "response": token,
    }
    if remoteip:
        data["remoteip"] = remoteip
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data
        )
        result = resp.json()
        if not result.get("success"):
            raise HTTPException(status_code=403, detail="Invalid Turnstile token.")
    return True
