# manage_routes.py
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import os, secrets
import asyncpg

router = APIRouter()

TOKEN_TTL_MIN = int(os.getenv("MANAGE_TOKEN_TTL_MIN", "30"))

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
# REQUEST MODELS
# -------------------
class ManageTokenRequest(BaseModel):
    whop_user_id: Optional[str] = None
    telegram_id: Optional[str] = None
    phone: Optional[str] = None

class AlertsBody(BaseModel):
    alerts: List[str]

# -------------------
# HELPERS
# -------------------
async def find_subscriber_identifier(conn: asyncpg.Connection, *, whop_user_id=None, telegram_id=None, phone=None):
    """Find subscriber by any identifier and return the identifier to store"""
    if whop_user_id:
        # Check subscribers table by whop_user_id
        r = await conn.fetchrow("SELECT whop_user_id FROM subscribers WHERE whop_user_id=$1", whop_user_id)
        if r: 
            return ("whop", r["whop_user_id"])
    if telegram_id:
        # Check telegram_subscribers table by telegram_chat_id
        r = await conn.fetchrow("SELECT telegram_chat_id FROM telegram_subscribers WHERE telegram_chat_id=$1", int(telegram_id))
        if r: 
            return ("telegram", str(r["telegram_chat_id"]))
    if phone:
        # Check subscribers table by phone
        r = await conn.fetchrow("SELECT phone FROM subscribers WHERE phone=$1", phone)
        if r: 
            return ("phone", r["phone"])
    return None

async def require_token(conn: asyncpg.Connection, token: str):
    """Validate token and return subscriber data"""
    row = await conn.fetchrow("""
        SELECT subscriber_identifier, expires_at
        FROM manage_tokens
        WHERE token=$1
    """, token)
    
    if not row:
        raise HTTPException(status_code=404, detail="Invalid token")
    
    if row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")
    
    identifier = row["subscriber_identifier"]
    
    # Determine which table to query based on identifier format
    # Phone: starts with +, Telegram: all digits, Whop: alphanumeric
    if identifier.startswith("+"):
        # Phone number - check subscribers table
        sub = await conn.fetchrow("SELECT alerts FROM subscribers WHERE phone=$1", identifier)
    elif identifier.isdigit():
        # Telegram chat ID - check telegram_subscribers table
        sub = await conn.fetchrow("SELECT alerts FROM telegram_subscribers WHERE telegram_chat_id=$1", int(identifier))
    else:
        # Whop user ID - check subscribers table
        sub = await conn.fetchrow("SELECT alerts FROM subscribers WHERE whop_user_id=$1", identifier)
    
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    return {
        "subscriber_identifier": identifier,
        "alerts": sub["alerts"] or []
    }

# -------------------
# ROUTES
# -------------------
@router.post("/manage/token")
async def create_manage_token(body: ManageTokenRequest, db=Depends(get_db)):
    """Generate a magic link token for managing alerts"""
    result = await find_subscriber_identifier(
        db, 
        whop_user_id=body.whop_user_id, 
        telegram_id=body.telegram_id, 
        phone=body.phone
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    subscriber_type, identifier = result
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MIN)
    
    # Store token in database
    await db.execute(
        "INSERT INTO manage_tokens(token, subscriber_identifier, expires_at) VALUES($1, $2, $3)",
        token, identifier, expires
    )
    
    # Build link
    base = os.getenv("MANAGE_LINK_BASE", "").rstrip("/")
    link = f"{base}?token={token}" if base else token
    
    return {
        "token": token,
        "link": link,
        "expires_at": expires.isoformat()
    }

@router.get("/manage/preferences")
async def get_preferences(token: str = Query(...), db=Depends(get_db)):
    """Get current alert preferences for a token"""
    row = await require_token(db, token)
    return {"alerts": row["alerts"] or []}

@router.post("/manage/preferences")
async def set_preferences(token: str = Query(...), body: AlertsBody = None, db=Depends(get_db)):
    """Update alert preferences"""
    row = await require_token(db, token)
    identifier = row["subscriber_identifier"]
    
    # Update the correct table based on identifier type
    if identifier.startswith("+"):
        # Phone number - update subscribers table
        await db.execute(
            "UPDATE subscribers SET alerts=$1 WHERE phone=$2",
            body.alerts if body else [],
            identifier
        )
    elif identifier.isdigit():
        # Telegram chat ID - update telegram_subscribers table
        await db.execute(
            "UPDATE telegram_subscribers SET alerts=$1 WHERE telegram_chat_id=$2",
            body.alerts if body else [],
            int(identifier)
        )
    else:
        # Whop user ID - update subscribers table
        await db.execute(
            "UPDATE subscribers SET alerts=$1 WHERE whop_user_id=$2",
            body.alerts if body else [],
            identifier
        )
    
    return {"ok": True, "alerts": body.alerts if body else []}