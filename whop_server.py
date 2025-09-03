from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whop_routes import router as whop_router
from subscriber_routes import router as sub_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://0uugdccam2vlgq5fg6y9.apps.whop.com",
        "https://tpgverify.disc2sms.com",
        "https://tpgverifycode.disc2sms.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(whop_router)
app.include_router(sub_router)
