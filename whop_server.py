from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from whop_routes import router as whop_router
from subscriber_routes import router as sub_router

app = FastAPI()

# --- CORS Setup ---
origins = [
    "https://disc2sms-whop-app-production.up.railway.app",  # frontend direct
    "https://whop.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.whop\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount Routers ---
app.include_router(whop_router)
app.include_router(sub_router)
