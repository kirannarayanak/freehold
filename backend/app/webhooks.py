"""Outgoing webhooks. deliver() is the only way one is ever sent, the way notify.dispatch() is
the only way anyone is notified.

Delivery happens on a small thread pool, never on the request. A receiver that is slow, down or
wrong must not make filing a work item slow, fail, or roll back: a hook is a notification about
something that already happened, so the write is always committed first and the delivery is best
effort. Failures are recorded on the hook row so an admin can see them without reading logs.
"""
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal, utcnow
from .models import Space, Webhook

log = logging.getLogger("freehold.webhooks")

EVENTS = [
    ("item.created", "Work item created"),
    ("item.updated", "Work item changed"),
    ("item.deleted", "Work item deleted"),
    ("comment.created", "Comment added"),
    ("sprint.started", "Sprint started"),
    ("sprint.completed", "Sprint completed"),
    ("version.released", "Version released"),
]
EVENT_NAMES = [e for e, _ in EVENTS]
TIMEOUT_SECONDS = 10
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webhook")


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _send(hook_id: int, url: str, secret: str, body: bytes) -> None:
    status, error = None, ""
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "Freehold-Webhook/1",
        **({"X-Freehold-Signature": sign(secret, body)} if secret else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
            status = r.status
    except urllib.error.HTTPError as e:      # reached the server, it said no
        status, error = e.code, f"HTTP {e.code}"
    except Exception as e:                   # noqa: BLE001  DNS, TLS, timeout, refused
        error = str(e)[:400]
    try:
        with SessionLocal() as db:
            hook = db.get(Webhook, hook_id)
            if hook:
                hook.last_status, hook.last_error, hook.last_at = status, error, utcnow()
                db.commit()
    except Exception:                        # noqa: BLE001
        log.exception("Could not record webhook result")
    if error:
        log.warning("Webhook %s to %s failed: %s", hook_id, url, error)


def deliver(db: Session, space: Space, event: str, payload: dict) -> int:
    """Queue this event to every active hook in the space subscribed to it. Returns how many."""
    if event not in EVENT_NAMES:
        raise ValueError(f"Unknown webhook event {event}")
    hooks = list(db.scalars(select(Webhook).where(Webhook.space_id == space.id, Webhook.active.is_(True))))
    sent = 0
    for hook in hooks:
        if hook.events and event not in hook.events:
            continue
        body = json.dumps({"event": event, "space": space.key, "at": utcnow().isoformat(), "data": payload},
                          default=str).encode()
        _pool.submit(_send, hook.id, hook.url, hook.secret, body)
        sent += 1
    return sent
