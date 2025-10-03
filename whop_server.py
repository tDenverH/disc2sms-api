from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whop_routes import router as whop_router
from subscriber_routes import router as sub_router
from manage_routes import router as manage_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://0uugdccam2vlgq5fg6y9.apps.whop.com",
        "https://tpgverify.disc2sms.com",
        "https://tpgverifycode.disc2sms.com",
        "https://disc2sms-whop-app-dev-production.up.railway.app",  # ADD THIS
        "https://disc2sms-whop-app-production.up.railway.app",  # ADD THIS TOO (for prod)
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],  # ADD "GET" for the manage endpoints
    allow_headers=["*"],
)

app.include_router(whop_router)
app.include_router(sub_router)
app.include_router(manage_router)
