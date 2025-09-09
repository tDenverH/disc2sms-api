from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os, random, string, datetime
import asyncpg
import secrets
import string
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
# Helpers
# -------------------
def normalize_phone(us_phone: str) -> str:
    """Very basic US normalizer: '5179301393' -> '+15179301393'."""
    p = "".join(ch for ch in us_phone if ch.isdigit())
    if len(p) == 11 and p.startswith("1"):
        return f"+{p}"
    if len(p) == 10:
        return f"+1{p}"
    # otherwise return as-is; Twilio will complain if invalid
    return us_phone

# -------------------
# REQUEST MODELS
# -------------------
class VerifyRequest(BaseModel):
    whop_user_id: str
    phone: str

from typing import Optional

class TelegramLinkRequest(BaseModel):
    whop_user_id: str

class TelegramVerifyRequest(BaseModel):
    token: str
    telegram_user_id: int
    telegram_username: Optional[str] = None

class ConfirmRequest(BaseModel):
    code: str
    whop_user_id: Optional[str] = None
    phone: Optional[str] = None

class AlertsRequest(BaseModel):
    whop_user_id: str
    alerts: List[str]
    delivery_method: Optional[str] = "sms"  # Add this field



# -------------------
# 1. VERIFY PHONE
# -------------------
@router.post("/subscribers/verify")
async def verify_subscriber(req: VerifyRequest, db=Depends(get_db)):
    code = "".join(random.choices(string.digits, k=6))
    phone_norm = normalize_phone(req.phone)

    # Upsert by whop_user_id
    await db.execute(
    """
    INSERT INTO subscribers (whop_user_id, phone, verification_code, verified_at, created_at)
    VALUES ($1, $2, $3, NULL, NOW())
    ON CONFLICT (whop_user_id)
    DO UPDATE SET phone = EXCLUDED.phone,
                  verification_code = EXCLUDED.verification_code,
                  verified_at = NULL
    """,
    req.whop_user_id, phone_norm, code
)

    try:
        twilio_client.messages.create(
            body=f"Your Disc2SMS verification code is {code}",
            from_=TWILIO_FROM,
            to=phone_norm
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Twilio error: {str(e)}")

    return {"ok": True, "whop_user_id": req.whop_user_id}

@router.post("/subscribers/telegram-link")
async def generate_telegram_link(req: TelegramLinkRequest, db=Depends(get_db)):
    """Generate a unique Telegram deep link for user verification"""
    
    # Generate unique verification token
    verification_token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    
    # Check if user already exists in telegram_subscribers
    existing_user = await db.fetchrow(
        "SELECT whop_user_id FROM telegram_subscribers WHERE whop_user_id = $1",
        req.whop_user_id
    )
    
    if existing_user:
        # Update existing user with new token
        await db.execute(
            """
            UPDATE telegram_subscribers 
            SET telegram_verification_token = $2
            WHERE whop_user_id = $1
            """,
            req.whop_user_id, verification_token
        )
    else:
        # Create new telegram subscriber record with token
        await db.execute(
            """
            INSERT INTO telegram_subscribers (whop_user_id, telegram_verification_token, created_at)
            VALUES ($1, $2, NOW())
            """,
            req.whop_user_id, verification_token
        )
    
    # Generate Telegram deep link
    bot_username = os.environ.get("TELEGRAM_BOT_USERNAME", "YourBotUsername")
    telegram_link = f"https://t.me/{bot_username}?start={verification_token}"
    
    return {"telegram_link": telegram_link, "token": verification_token}

@router.post("/subscribers/telegram-verify")
async def verify_telegram_user(req: TelegramVerifyRequest, db=Depends(get_db)):
    """Verify Telegram user via token from deep link"""
    
    if not req.token or not req.telegram_user_id:
        raise HTTPException(status_code=400, detail="Token and telegram_user_id required")
    
    # Find subscriber by verification token
    row = await db.fetchrow(
        "SELECT whop_user_id FROM telegram_subscribers WHERE telegram_verification_token = $1",
        req.token
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Invalid verification token")
    
    # Update subscriber with Telegram info
    await db.execute(
        """
        UPDATE telegram_subscribers 
        SET telegram_user_id = $2,
            telegram_chat_id = $2,
            telegram_username = $3,
            verified_at = NOW(),
            telegram_verification_token = NULL,
            updated_at = NOW()
        WHERE whop_user_id = $1
        """,
        row['whop_user_id'],
        req.telegram_user_id,
        req.telegram_username
    )
    
    return {"ok": True, "whop_user_id": row['whop_user_id']}

@router.post("/subscribers/telegram-alerts")
async def save_telegram_alerts(req: AlertsRequest, db=Depends(get_db)):
    """Save alert preferences for Telegram user"""
    
    # Update alerts for telegram subscriber
    await db.execute(
        """
        UPDATE telegram_subscribers
        SET alerts = $2, updated_at = NOW()
        WHERE whop_user_id = $1
        """,
        req.whop_user_id,
        req.alerts
    )
    
    return {"ok": True, "alerts": req.alerts, "delivery_method": "telegram"}



# -------------------
# 2. CONFIRM CODE
# -------------------
@router.post("/subscribers/confirm")
async def confirm_subscriber(req: ConfirmRequest, db=Depends(get_db)):
    # Find the row by whop_user_id OR by phone
    row = None
    if req.whop_user_id:
        row = await db.fetchrow(
            "SELECT whop_user_id, verification_code FROM subscribers WHERE whop_user_id=$1",
            req.whop_user_id,
        )
    elif req.phone:
        row = await db.fetchrow(
            "SELECT whop_user_id, verification_code FROM subscribers WHERE phone=$1",
            req.phone,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    if row["verification_code"] != req.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    await db.execute(
        """
        UPDATE subscribers
           SET verified_at = $2,
               verification_code = NULL
         WHERE whop_user_id = $1
        """,
        row["whop_user_id"],
        datetime.datetime.utcnow(),
    )

    # IMPORTANT: return the id so the frontend can navigate with it
    return {"ok": True, "whop_user_id": row["whop_user_id"]}

# -------------------
# 3. SAVE ALERTS
# -------------------
# -------------------
# 3. UNIFIED ALERTS ENDPOINT
# -------------------
@router.post("/subscribers/alerts")
async def save_alerts(req: AlertsRequest, db=Depends(get_db)):
    """Save alert preferences - handles SMS, Telegram, or both"""
    
    delivery_method = req.delivery_method or "sms"
    
    # Handle SMS alerts (existing subscribers table)
    if delivery_method in ["sms", "both"]:
        # Check if SMS subscriber exists
        sms_exists = await db.fetchrow(
            "SELECT whop_user_id FROM subscribers WHERE whop_user_id = $1",
            req.whop_user_id
        )
        
        if sms_exists:
            await db.execute(
                """
                UPDATE subscribers
                SET alerts = $2
                WHERE whop_user_id = $1
                """,
                req.whop_user_id,
                req.alerts
            )
    
    # Handle Telegram alerts (telegram_subscribers table)
    if delivery_method in ["telegram", "both"]:
        # Check if Telegram subscriber exists
        telegram_exists = await db.fetchrow(
            "SELECT whop_user_id FROM telegram_subscribers WHERE whop_user_id = $1",
            req.whop_user_id
        )
        
        if telegram_exists:
            await db.execute(
                """
                UPDATE telegram_subscribers
                SET alerts = $2, updated_at = NOW()
                WHERE whop_user_id = $1
                """,
                req.whop_user_id,
                req.alerts
            )
        else:
            # Create placeholder telegram subscriber (they'll verify later)
            await db.execute(
                """
                INSERT INTO telegram_subscribers (whop_user_id, alerts, created_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (whop_user_id) DO UPDATE SET
                alerts = EXCLUDED.alerts,
                updated_at = NOW()
                """,
                req.whop_user_id,
                req.alerts
            )
    
    return {"ok": True, "alerts": req.alerts, "delivery_method": delivery_method}