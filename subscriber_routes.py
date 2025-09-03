# subscriber_routes.py
from fastapi import APIRouter, Form, HTTPException
import os, re

router = APIRouter()

def to_e164(us_phone: str) -> str:
    digits = re.sub(r"\D", "", us_phone or "")
    if not digits:
        return ""
    if not digits.startswith("1"):
        digits = "1" + digits
    return f"+{digits}"

@router.post("/webhook")   # send verification SMS
async def send_code(
    phone: str = Form(...),
    email: str | None = Form(None),
    token: str | None = Form(None),
):
    # Basic validation
    phone_e164 = to_e164(phone)
    if len(phone_e164) < 12:
        raise HTTPException(status_code=400, detail="Invalid phone")

    # Env checks (fail fast with a readable message)
    required = {
        "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID"),
        "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN"),
        # use either Messaging Service SID or FROM number (pick your setup)
        "TWILIO_MESSAGING_SERVICE_SID": os.getenv("TWILIO_MESSAGING_SERVICE_SID")
        or os.getenv("TWILIO_FROM_NUMBER"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing env vars: {', '.join(missing)}")

    # TODO: create & store code, send via Twilio using the env above
    # return a simple OK so the UI can proceed
    return {"ok": True}

@router.post("/verify")    # confirm the code
async def verify_code(
    code: str = Form(...),
    token: str | None = Form(None),
):
    # TODO: lookup pending verification by token, compare code, mark verified
    return {"ok": True}

@router.post("/alerts")    # save alert preferences
async def set_alerts(
    token: str = Form(...),
    # If your form sends many checkboxes with the *same* name (e.g., alerts),
    # FastAPI can collect them as a list when using the "alerts" key multiple times.
    alerts: list[str] = Form(default=[]),
):
    # TODO: persist alerts for the subscriber identified by token
    return {"ok": True, "alerts": alerts}
