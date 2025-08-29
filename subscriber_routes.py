from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import os, random, string, datetime
import asyncpg
from twilio.rest import Client

router = APIRouter()

# -------------------
# DB CONNECTION
# -------------------
async def get_db():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
    finally:
        await conn.close()

# -------------------
# TWILIO CLIENT
# -------------------
twilio_client = Client(
    os.environ["TWILIO_ACCOUNT_SID"],
    os.environ["TWILIO_AUTH_TOKEN"]
)
TWILIO_FROM = os.environ["TWILIO_PHONE_NUMBER"]

# -------------------
# REQUEST MODELS
# -------------------
class VerifyRequest(BaseModel):
    userId: str
    phone: str

class ConfirmRequest(BaseModel):
    userId: str
    code: str

class AlertsRequest(BaseModel):
    userId: str
    alerts: List[str]

# -------------------
# 1. VERIFY PHONE
# -------------------
@router.post("/subscribers/verify")
async def verify_subscriber(req: VerifyRequest, db=Depends(get_db)):
    # Generate a 6-digit verification code
    code = "".join(random.choices(string.digits, k=6))

    # Save phone + code in DB (overwrite if exists)
    await db.execute("""
        INSERT INTO subscribers (whop_user_id, phone, verification_code, verified_at)
        VALUES ($1, $2, $3, NULL)
        ON CONFLICT (whop_user_id)
        DO UPDATE SET phone=$2, verification_code=$3, verified_at=NULL
    """, req.userId, req.phone, code)

    # Send SMS via Twilio
    try:
        twilio_client.messages.create(
            body=f"Your Disc2SMS verification code is {code}",
            from_=TWILIO_FROM,
            to=req.phone
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")

    return {"message": "Verification SMS sent"}

# -------------------
# 2. CONFIRM CODE
# -------------------
@router.post("/subscribers/confirm")
async def confirm_subscriber(req: ConfirmRequest, db=Depends(get_db)):
    row = await db.fetchrow("""
        SELECT verification_code FROM subscribers WHERE whop_user_id=$1
    """, req.userId)

    if not row or row["verification_code"] != req.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Mark as verified
    await db.execute("""
        UPDATE subscribers
        SET verified_at=$2, verification_code=NULL
        WHERE whop_user_id=$1
    """, req.userId, datetime.datetime.utcnow())

    return {"message": "Phone confirmed"}

# -------------------
# 3. SAVE ALERTS
# -------------------
@router.post("/subscribers/alerts")
async def save_alerts(req: AlertsRequest, db=Depends(get_db)):
    # Store alerts (string array in Postgres)
    await db.execute("""
        UPDATE subscribers
        SET alerts=$2
        WHERE whop_user_id=$1
    """, req.userId, req.alerts)

    return {"message": "Alerts saved"}
