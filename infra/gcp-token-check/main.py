"""Minimal Cloud Run service showing the Cognito token check.

Teammates add their own routes and protect them the same way as /me:

    @app.post("/some-route")
    def handler(user: dict = Depends(get_current_user)):
        ...
"""

import os

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth import get_current_user
from match import router as match_router

app = FastAPI(title="EcoGuard GCP API")
app.include_router(match_router)


@app.exception_handler(RequestValidationError)
def bad_request(_: Request, __: RequestValidationError) -> JSONResponse:
    """Report malformed bodies as 400 (the contract with the AWS side)."""
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})

# Comma-separated list of frontend origins, e.g. "http://localhost:5173".
allowed_origins = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict:
    """Public, for Cloud Run health checks. Must not expose any data."""
    return {"status": "ok"}


@app.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    """Protected test route: returns who the verified token belongs to."""
    return {
        "sub": user["sub"],
        "email": user.get("email"),
        "given_name": user.get("given_name"),
        "family_name": user.get("family_name"),
        "token_use": user["token_use"],
    }
