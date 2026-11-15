"""Browser push (Web Push with VAPID keys from `make vapid`). The payload carries the alert's
title and short message and the app link; never coordinates."""

from __future__ import annotations

import json
import logging
from typing import Any

from pywebpush import WebPushException, webpush

from app.config import get_settings

log = logging.getLogger(__name__)


class PushGone(Exception):
    """The browser unsubscribed (404/410): delete the subscription."""


def configured() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key.get_secret_value() and s.vapid_subject)


def send(subscription: dict[str, Any], payload: dict[str, Any]) -> None:
    s = get_settings()
    try:
        webpush(
            subscription_info={"endpoint": subscription["endpoint"],
                               "keys": {"p256dh": subscription["p256dh"],
                                        "auth": subscription["auth"]}},
            data=json.dumps(payload),
            vapid_private_key=s.vapid_private_key.get_secret_value(),
            vapid_claims={"sub": s.vapid_subject},
            ttl=12 * 3600,
            timeout=10,
        )
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            raise PushGone() from exc
        log.info("push failed with status %s", status)
        raise
