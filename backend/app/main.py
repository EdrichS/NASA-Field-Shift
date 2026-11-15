"""SowSmart API."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.accounts import router as accounts_router
from app.api.alerts import router as alerts_router
from app.api.routes import router
from app.config import get_settings

settings = get_settings()
log = logging.getLogger(__name__)
# An analysis with two AI reports is about 100 KB. Bigger bodies only run up the AI bill (guest
# follow-ups send the analysis back) or fill the database.
MAX_BODY_BYTES = 512_000


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


@app.middleware("http")
async def limit_body(request: Request,
                     call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if "chunked" in request.headers.get("transfer-encoding", "").lower():
        return JSONResponse({"detail": "Send a Content-Length."}, status_code=411)
    size = request.headers.get("content-length", "0")
    if not size.isdigit() or int(size) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "Request too large."}, status_code=413)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
