from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI(
    title="AHOracle API",
    description="Read-only access to crowdsourced WoW Classic Era AH data",
    version="0.1.0"
)

# Allow the frontend to talk to this API from anywhere during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AHOracle API is running. Go to /docs for the Swagger UI."}