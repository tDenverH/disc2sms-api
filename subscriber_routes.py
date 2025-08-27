import os, random, string, asyncpg, jwt
from fastapi import APIRouter, Form, Header, HTTPException
from twilio.rest import Client

router = APIRouter(prefix="/subscribers", tags=["subscribers"])

DB_URL = os.getenv("DATABASE_URL")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER")
twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

# Async DB connection
async def get_pool():
    return await asyncpg.create_pool(DB_URL, ssl="require")

def generate_code(length=6):
    return "".join(random.choices(string.digits, k=length))

def decode_whop_token(x_whop_user_token: str):
    """Decode and return whop_user_id from JWT."""
    claims = jwt.decode(
        x_whop_user_token,
        os.getenv("WHOP_PUBLIC_KEY_PEM", "").replace("\\n", "\n"),
        algorithms=["ES256"],
        audience=os.getenv("WHOP_APP_ID"),
        issuer="https://api.whop.com"
    )
    return claims.get("sub")

@router.post("/verify")
async def send_verification(
    phone: str = Form(...),
    email: str = Form(...),
    x_whop_user_token: str = Header(alias="x-whop-user-token")
):
    """Attach phone/email to Whop user + send SMS code."""
    whop_user_id = decode_whop_token(x_whop_user_token)
    if not whop_user_id:
        raise HTTPException(status_code=401, detail="Invalid Whop token")

    code = generate_code()
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO subscribers (whop_user_id, email, phone, token)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (whop_user_id) DO UPDATE
            SET email=$2, phone=$3, token=$4
        """, whop_user_id, email, phone, code)

    twilio_client.messages.create(
        body=f"Your Disc2SMS verification code is {code}",
        from_=TWILIO_FROM,
        to=phone,
    )
    return {"status": "code_sent"}

@router.post("/confirm")
async def confirm_verification(
    code: str = Form(...),
    x_whop_user_token: str = Header(alias="x-whop-user-token")
):
    """Check code and mark subscriber verified."""
    whop_user_id = decode_whop_token(x_whop_user_token)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT token FROM subscribers WHERE whop_user_id=$1", whop_user_id
        )
        if not row or row["token"] != code:
            raise HTTPException(status_code=400, detail="Invalid code")

        await conn.execute("""
            UPDATE subscribers
            SET verified_at=NOW()
            WHERE whop_user_id=$1
        """, whop_user_id)

    return {"status": "verified"}

@router.post("/alerts")
async def set_alerts(
    alerts: str = Form(...),
    x_whop_user_token: str = Header(alias="x-whop-user-token")
):
    """Set sportsbook alert preferences for Whop user."""
    whop_user_id = decode_whop_token(x_whop_user_token)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE subscribers
            SET alerts=$2
            WHERE whop_user_id=$1
        """, whop_user_id, alerts)

    return {"status": "alerts_set"}
