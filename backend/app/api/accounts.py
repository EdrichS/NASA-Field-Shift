"""Signed-in endpoints (step 3.4): profile, saved fields and analyses, "delete my data".
Every route requires a valid Auth0 token and only touches rows owned by its `sub`."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from app import store
from app.api.ratelimit import RateLimiter
from app.auth import CurrentUser, User, email_of
from app.data.geometry import geom_hash
from app.schemas import FieldPatch, MeOut, ProfileIn, SaveOut, SaveRequest

router = APIRouter()
save_limit = RateLimiter(limit=30, window_s=3600)


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser) -> dict[str, Any]:
    profile = store.upsert_user(user.sub, email_of(user))
    return {**profile, "fields": store.list_fields(user.sub)}


@router.put("/me", status_code=204)
def update_me(body: ProfileIn, user: CurrentUser) -> Response:
    store.update_profile(user.sub, (body.display_name or "").strip() or None, body.language,
                         body.units)
    return Response(status_code=204)


@router.delete("/me", status_code=204)
def delete_me(user: CurrentUser) -> Response:
    """Delete my data: profile, fields, analyses, reports, alerts and push subscriptions."""
    store.delete_user(user.sub)
    return Response(status_code=204)


@router.post("/analyses/save", response_model=SaveOut, dependencies=[Depends(save_limit)])
def save(body: SaveRequest, user: CurrentUser) -> dict[str, Any]:
    """Keep an analysis (guest results are posted here after signing up and tapping Save)."""
    request = body.request.model_dump()
    analysis = body.analysis.model_dump()
    if geom_hash(request["geometry"]) != analysis["field"]["geom_hash"]:
        raise HTTPException(status_code=422, detail="The analysis does not match this field.")
    return store.save_analysis(user.sub, request, analysis, field_name=body.field_name.strip(),
                               input_mode=body.input_mode, email=email_of(user))


@router.get("/analyses/{analysis_id}")
def saved_analysis(analysis_id: str, user: CurrentUser) -> dict[str, Any]:
    result = _owned(user, analysis_id)
    return result


@router.get("/fields")
def fields(user: CurrentUser) -> list[dict[str, Any]]:
    return store.list_fields(user.sub)


@router.patch("/fields/{field_id}", status_code=204)
def rename(field_id: str, body: FieldPatch, user: CurrentUser) -> Response:
    if not _valid_uuid(field_id) or not store.rename_field(user.sub, field_id, body.name.strip()):
        raise HTTPException(status_code=404, detail="Field not found")
    return Response(status_code=204)


@router.delete("/fields/{field_id}", status_code=204)
def remove(field_id: str, user: CurrentUser) -> Response:
    if not _valid_uuid(field_id) or not store.delete_field(user.sub, field_id):
        raise HTTPException(status_code=404, detail="Field not found")
    return Response(status_code=204)


def _owned(user: User, analysis_id: str) -> dict[str, Any]:
    result = store.get_analysis(user.sub, analysis_id) if _valid_uuid(analysis_id) else None
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
