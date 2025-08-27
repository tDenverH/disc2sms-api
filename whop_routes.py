# whop_routes.py
import os
from typing import Optional
from fastapi import APIRouter, Header, HTTPException
import httpx
import jwt

router = APIRouter()

WHOP_APP_ID = os.getenv("WHOP_APP_ID", "").strip()
WHOP_PUBLIC_KEY_PEM = os.getenv("WHOP_PUBLIC_KEY_PEM", "").strip()
WHOP_API_KEY = os.getenv("WHOP_API_KEY", "").strip()
WHOP_EXPECTED_ISS = os.getenv("WHOP_EXPECTED_ISS", "urn:whopcom:exp-proxy")

async def _whop_fetch_email(user_id: str) -> Optional[str]:
    """Fetch user email via Whop App Users API (needs WHOP_API_KEY)."""
    if not WHOP_API_KEY:
        return None
    url = f"https://api.whop.com/v5/app/users/{user_id}"
    headers = {"Authorization": f"Bearer {WHOP_API_KEY}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        return data.get("email")
    return None

def _verify_whop_token(token: str) -> dict:
    """Verify x-whop-user-token (ES256), issuer, and audience."""
    if not WHOP_PUBLIC_KEY_PEM:
        raise HTTPException(status_code=500, detail="WHOP_PUBLIC_KEY_PEM not configured")
    if not WHOP_APP_ID:
        raise HTTPException(status_code=500, detail="WHOP_APP_ID not configured")
    try:
        payload = jwt.decode(
            token,
            WHOP_PUBLIC_KEY_PEM,
            algorithms=["ES256"],
            issuer=WHOP_EXPECTED_ISS,
            options={"require": ["iss", "sub", "aud"]},
        )
        if payload.get("aud") != WHOP_APP_ID:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        return payload
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Whop token: {str(e)}")

@router.get("/api/me")
async def api_me(x_whop_user_token: Optional[str] = Header(None)):
    """
    Return the current Whop-authenticated user:
      { "user_id": "...", "email": "..." }
    """
    if not x_whop_user_token:
        raise HTTPException(status_code=401, detail="Missing x-whop-user-token")

    payload = _verify_whop_token(x_whop_user_token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    email = payload.get("email") or await _whop_fetch_email(user_id)
    return {"user_id": user_id, "email": email}
