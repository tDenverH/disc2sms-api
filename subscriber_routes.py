from fastapi import APIRouter, Request, HTTPException, Form
import os, random
import asyncpg
from twilio.rest import Client

router = APIRouter()

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db():
    return await asyncpg.connect(DATABASE_URL)

# --- Twilio ---
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# --- Verify Phone (send SMS) ---
@router.post("/subscribers/verify")
async def verify_subscriber(request: Request, phone: str = Form(...)):
    # Whop token already validated upstream in whop_routes
    # Here we just handle phone + DB + SMS
    user_id = request.headers.get("x-whop-user-id")
    email = request.headers.get("x-whop-user-email")

    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    # Generate 6-digit code
    code = str(random.randint(100000, 999999))

    try:
        twilio_client.messages.create(
            body=f"Your Disc2SMS verification code is {code}",
            from_=TWILIO_PHONE_NUMBER,
            to=phone,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")

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


# --- Confirm Code ---
@router.post("/subscribers/confirm")
async def confirm_subscriber(request: Request, code: str = Form(...)):
    user_id = request.headers.get("x-whop-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

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


# --- Update Alerts ---
@router.post("/subscribers/alerts")
async def update_alerts(request: Request, alerts: list[str] = Form(...)):
    user_id = request.headers.get("x-whop-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    conn = await get_db()
    await conn.execute(
        "UPDATE subscribers SET alerts=$1 WHERE whop_user_id=$2",
        alerts, user_id
    )
    await conn.close()

    return {"status": "alerts_updated", "alerts": alerts}
