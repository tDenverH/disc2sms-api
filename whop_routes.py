from fastapi import APIRouter, Request, HTTPException
import jwt
import os

router = APIRouter()

WHOP_APP_ID = os.getenv("WHOP_APP_ID")
WHOP_PUBLIC_KEY_PEM = os.getenv("WHOP_PUBLIC_KEY_PEM")

@router.get("/api/me")
async def get_me(request: Request):
    token = request.headers.get("x-whop-user-token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing Whop token")

    try:
        payload = jwt.decode(
            token,
            WHOP_PUBLIC_KEY_PEM,
            algorithms=["ES256"],
            audience=WHOP_APP_ID,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    return {
        "user_id": payload["sub"],
        "email": payload.get("email"),
    }
