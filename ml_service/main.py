"""Rhodesli ML Service — Standalone FastAPI service for face detection."""

import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ml_service.config import EXECUTION_ENVIRONMENT, ML_SERVICE_TOKEN

VERSION = "0.1.0"

app = FastAPI(title="Rhodesli ML Service", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_start_time: float = 0.0

security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Verify bearer token for protected endpoints."""
    if credentials.credentials != ML_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


@app.on_event("startup")
async def startup_event():
    global _start_time
    _start_time = time.time()


@app.get("/health")
async def health():
    """Health check endpoint. Public — no auth required."""
    from ml_service.detect import is_model_loaded

    uptime = time.time() - _start_time if _start_time else 0.0
    return {
        "status": "ok",
        "version": VERSION,
        "models_loaded": is_model_loaded(),
        "execution_environment": EXECUTION_ENVIRONMENT,
        "uptime_seconds": round(uptime, 1),
    }


# Import and include detect router after app is created
from ml_service.detect import router as detect_router  # noqa: E402

app.include_router(detect_router)
