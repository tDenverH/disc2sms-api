# subscriber_routes.py
from fastapi import APIRouter, Form, HTTPException
import os, re
from typing import List

router = APIRouter()

def to_e164(us_phone: str) -> str:
    digits = re.sub(r"\D", "", us_phone or "")
    if not digits:
        return ""
    if not digits.startswith("1"):
        digits = "1" + digits
    return f"+{digits}"

@router.post("/webhook")
async def send_code(
    phone: str = Form(...),
    email: str | None = Form(None),
    token: str | None = Form(None),
):
    phone_e164 = to_e164(phone)
    if len(phone_e164) < 12:
        raise HTTPException(status_code=400, detail="Invalid phone")

    # Fail fast if envs missing
    required = {
        "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID"),
        "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN"),
        # Use either Messaging Service SID or FROM number
        "TWILIO_MESSAGING_SERVICE_SID_OR_FROM": (
            os.getenv("TWILIO_MESSAGING_SERVICE_SID") or os.getenv("TWILIO_FROM_NUMBER")
        ),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing env vars: {', '.join(missing)}")

    # TODO: generate+store code, send via Twilio
    return {"ok": True}

@router.post("/verify")
async def verify_code(
    code: str = Form(...),
    token: str | None = Form(None),
):
    # TODO: lookup by token, compare code, mark verified
    return {"ok": True}

@router.post("/alerts")
async def set_alerts(
    token: str = Form(...),
    alerts: List[str] = Form(default=[]),  # repeated "alerts" fields map to list[str]
):
    # TODO: persist alerts for subscriber identified by token
    return {"ok": True, "alerts": alerts}
