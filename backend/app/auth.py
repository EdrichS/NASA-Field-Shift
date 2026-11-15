"""Auth0 access tokens (CLAUDE.md section 5): RS256, checked against the tenant's JWKS, audience
and issuer. Analyze and report endpoints work without a token (guests); saving, fields and alerts
need one. Every query on user data filters by the token's `sub`.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

log = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class User:
    sub: str
    token: str


@lru_cache(maxsize=4)
def _jwks(domain: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://{domain}/.well-known/jwks.json", cache_keys=True,
                           lifespan=3600, timeout=10)


def decode_token(token: str) -> dict:
    """The verified claims, or jwt.PyJWTError. Patched in tests."""
    s = get_settings()
    if not (s.auth0_domain and s.auth0_audience):
        raise jwt.InvalidTokenError("Auth0 is not configured on this server")
    key = _jwks(s.auth0_domain).get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["RS256"], audience=s.auth0_audience,
                      issuer=f"https://{s.auth0_domain}/",
                      options={"require": ["exp", "iat", "sub"]})


def optional_user(
        creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> User | None:
    if creds is None or not creds.credentials:
        return None
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401,
                            detail="Your sign-in has expired. Please log in again.",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    return User(sub=str(claims["sub"]), token=creds.credentials)


def require_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to save fields and get alerts.",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(require_user)]
MaybeUser = Annotated[User | None, Depends(optional_user)]

_emails: dict[str, str | None] = {}
_lock = threading.Lock()


def email_of(user: User) -> str | None:
    """The verified email on the Auth0 account, from /userinfo (the access token doesn't carry
    it). Looked up once per user per process; None if unavailable or not verified."""
    with _lock:
        if user.sub in _emails:
            return _emails[user.sub]
    s = get_settings()
    email = None
    try:
        r = httpx.get(f"https://{s.auth0_domain}/userinfo",
                      headers={"Authorization": f"Bearer {user.token}"}, timeout=10)
        if r.status_code == 200:
            info = r.json()
            if info.get("email") and info.get("email_verified", False):
                email = str(info["email"])
        else:
            log.info("Auth0 userinfo answered %s", r.status_code)
    except httpx.HTTPError as exc:
        log.info("Auth0 userinfo failed: %s", type(exc).__name__)
    with _lock:
        _emails[user.sub] = email
    return email
