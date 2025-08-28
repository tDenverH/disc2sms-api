from fastapi import APIRouter, Request, HTTPException, Form
from pydantic import BaseModel
import jwt
import os
import random
from twilio.rest import Client
import asyncpg

router = APIRouter()

# --- Environment Variables ---
WHOP_APP_ID = os.getenv("WHOP_APP_ID")
WHOP_PUBLIC_KEY_PEM = os.getenv("WHOP_PUBLIC_KEY_PEM")

DATABASE_URL = os.getenv("DATABASE_URL")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# --- Helper: verify Whop token ---
def verify_whop_token(request: Request):
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
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# --- Database Helper ---
async def get_db():
    return await asyncpg.connect(DATABASE_URL)

# --- Routes ---

@router.get("/api/me")
async def get_me(request: Request):
    payload = verify_whop_token(request)
    return {
        "user_id": payload["sub"],
        "email": payload.get("email"),
    }


@router.post("/subscribers/verify")
async def verify_subscriber(request: Request, phone: str = Form(...)):
    payload = verify_whop_token(request)
    user_id = payload["sub"]
    email = payload.get("email")

    # Generate 6-digit code
    code = str(random.randint(100000, 999999))

    try:
        # Send SMS via Twilio
        twilio_client.messages.create(
            body=f"Your Disc2SMS verification code is {code}",
            from_=TWILIO_PHONE_NUMBER,
            to=phone,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")

    # Save pending verification in DB
    conn = await get_db()
    await conn.execute(
        """
        INSERT INTO subscribers (whop_user_id, email, phone, verification_code)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (whop_user_id)
        DO UPDATE SET phone=$3, verification_code=$4
        """,
        user_id, email, phone, code
    )
    await conn.close()

    return {"status": "verification_sent"}


@router.post("/subscribers/confirm")
async def confirm_subscriber(request: Request, code: str = Form(...)):
    payload = verify_whop_token(request)
    user_id = payload["sub"]

    conn = await get_db()
    row = await conn.fetchrow(
        "SELECT verification_code FROM subscribers WHERE whop_user_id=$1",
        user_id
    )

    if not row or row["verification_code"] != code:
        await conn.close()
        raise HTTPException(status_code=400, detail="Invalid verification code")

    await conn.execute(
        """
        UPDATE subscribers
        SET verified_at=NOW(), verification_code=NULL
        WHERE whop_user_id=$1
        """,
        user_id
    )
    await conn.close()

    return {"status": "verified"}


class AlertsModel(BaseModel):
    alerts: list[str]

@router.post("/subscribers/alerts")
async def update_alerts(request: Request, body: AlertsModel):
    payload = verify_whop_token(request)
    user_id = payload["sub"]

    conn = await get_db()
    await conn.execute(
        "UPDATE subscribers SET alerts=$1 WHERE whop_user_id=$2",
        body.alerts, user_id
    )
    await conn.close()

    return {"status": "alerts_updated", "alerts": body.alerts}
