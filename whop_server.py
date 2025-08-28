from fastapi import FastAPI
from whop_routes import router as whop_router
from subscriber_routes import router as sub_router

app = FastAPI(title="Disc2SMS Whop App")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount Whop authentication routes (/api/me)
app.include_router(whop_router)

# Mount subscriber verification & alert routes
app.include_router(sub_router)

@app.get("/")
async def root():
    return {"message": "Disc2SMS Whop App is running!"}
