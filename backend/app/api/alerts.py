"""Alert endpoints (signed in): check, list, read, per-field preferences and browser push.
Checks run when the app opens (cached ~6 hours) and on "Check now". Storm simulations are
admin-only (scripts/simulate_storm.py), never an API route."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.alerts import push, service
from app.api.ratelimit import RateLimiter
from app.auth import CurrentUser
from app.config import get_settings
from app.store import ALERT_TYPES

router = APIRouter(prefix="/alerts")
check_limit = RateLimiter(limit=20, window_s=3600)


class CheckIn(BaseModel):
    force: bool = Field(False, description="True for 'Check now' (skips the 6-hour cache)")


class PreferencesIn(BaseModel):
    field_id: str
    alert_types: list[Literal["natural_event", "fire", "heavy_rain", "drought", "pest_risk",
                              "new_findings"]] = Field(default_factory=lambda: list(ALERT_TYPES))
    email: bool = True
    push: bool = True


class SubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: dict[str, str]


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc


@router.post("/check", dependencies=[Depends(check_limit)])
def check(body: CheckIn, user: CurrentUser) -> dict[str, Any]:
    result = service.run_check(user.sub, force=body.force)
    return {**result, "alerts": service.list_alerts(user.sub)}


@router.get("")
def alerts(user: CurrentUser) -> list[dict[str, Any]]:
    return service.list_alerts(user.sub)


@router.post("/{alert_id}/read", status_code=204)
def read(alert_id: str, user: CurrentUser) -> Response:
    if not service.mark_read(user.sub, _uuid(alert_id)):
        raise HTTPException(status_code=404, detail="Alert not found")
    return Response(status_code=204)


@router.put("/preferences", status_code=204)
def preferences(body: PreferencesIn, user: CurrentUser) -> Response:
    if not service.set_preferences(user.sub, _uuid(body.field_id), list(body.alert_types),
                                   body.email, body.push):
        raise HTTPException(status_code=404, detail="Field not found")
    return Response(status_code=204)


@router.get("/push-key")
def push_key() -> dict[str, str | None]:
    """The public VAPID key the browser needs to subscribe (public by design)."""
    return {"public_key": get_settings().vapid_public_key if push.configured() else None}


@router.post("/push-subscription", status_code=204)
def subscribe(body: SubscriptionIn, user: CurrentUser) -> Response:
    if not body.endpoint.startswith("https://") or not {"p256dh", "auth"} <= body.keys.keys():
        raise HTTPException(status_code=422, detail="Not a valid push subscription")
    service.add_subscription(user.sub, body.endpoint, body.keys["p256dh"], body.keys["auth"])
    return Response(status_code=204)


@router.delete("/push-subscription", status_code=204)
def unsubscribe(body: SubscriptionIn, user: CurrentUser) -> Response:
    service.remove_subscription(user.sub, body.endpoint)
    return Response(status_code=204)
