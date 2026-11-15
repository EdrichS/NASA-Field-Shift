"""SowSmart API."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.accounts import router as accounts_router
from app.api.alerts import router as alerts_router
from app.api.routes import router
from app.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """The 6-hourly alert check for every saved field, while the backend runs (needs the
    database; skipped when DATABASE_URL is empty, e.g. in tests)."""
    stop = None
    if settings.database_url.get_secret_value() and settings.alert_check_interval_hours > 0:
        from app.alerts.service import start_background

        stop = start_background(settings.alert_check_interval_hours)
    yield
    if stop is not None:
        stop.set()


app = FastAPI(title="SowSmart API", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(accounts_router)
app.include_router(alerts_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
