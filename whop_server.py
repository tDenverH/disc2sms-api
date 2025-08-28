from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whop_routes import router as whop_router
from subscriber_routes import router as sub_router

app = FastAPI()

# --- Minimal CORS ---
# Only allow your Next.js frontend and (optionally) local dev.
origins = [
    "https://disc2sms-whop-app-production.up.railway.app",
    "http://localhost:3000",  # local dev frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount Routers ---
app.include_router(whop_router)
app.include_router(sub_router)
