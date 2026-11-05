from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

app = FastAPI(
    title="AHOracle API",
    description="Read-only access to crowdsourced WoW Classic Era AH data",
    version="0.1.0",
)

# Dev-only CORS. Wildcard + allow_credentials is technically invalid per the
# CORS spec (browsers reject "Access-Control-Allow-Origin: *" when credentials
# are sent). It works here because the frontend uses plain fetch() with no
# cookies — but if you ever add auth, switch to an explicit origin list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "AHOracle API is running. Go to /docs for the Swagger UI.",
    }