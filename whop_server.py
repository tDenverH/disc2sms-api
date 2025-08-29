from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whop_routes import router as whop_router
from subscriber_routes import router as sub_router

app = FastAPI()

# ✅ CORS for Whop production + local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://0uugdccam2vlgq5fg6y9.apps.whop.com",  # your Hosted App origin
        "http://localhost:3000",                       # local dev
        "http://127.0.0.1:3000"                        # local dev alt
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ Mount routers
app.include_router(whop_router)
app.include_router(sub_router)
