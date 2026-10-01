"""Notifications: who hears about what is decided per user, never by an admin-wide scheme."""
import copy
import logging
import smtplib
import threading
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .db import utcnow
from .models import Notification, User

log = logging.getLogger("opentrack.notify")

EVENTS = {
    "assigned": "Someone assigns a work item to you",
    "mentioned": "Someone mentions you with @",
    "commented": "New comments on work you are involved in",
    "status": "Status changes on work you are involved in",
    "updated": "Other edits on work you are involved in",
}
DEFAULT_PREFS = {
    "events": {
        "assigned": {"inapp": True, "email": True},
        "mentioned": {"inapp": True, "email": True},
        "commented": {"inapp": True, "email": False},
        "status": {"inapp": True, "email": False},
        "updated": {"inapp": False, "email": False},
    },
    "email_mode": "instant",  # instant | digest | off
    "digest_hour": 8,         # UTC hour for the daily digest
    "muted": [],              # work item keys this user muted
}


def prefs_of(user: User) -> dict:
    merged = copy.deepcopy(DEFAULT_PREFS)
    stored = user.prefs or {}
    for event, channels in (stored.get("events") or {}).items():
        if event in merged["events"] and isinstance(channels, dict):
            merged["events"][event].update({k: bool(v) for k, v in channels.items() if k in ("inapp", "email")})
    for key in ("email_mode", "digest_hour", "muted", "last_digest"):
        if key in stored:
            merged[key] = stored[key]
    return merged


def send_email(to: str, subject: str, body: str) -> None:
    """Send in a background thread so a slow mail server never slows the app down."""
    def _send():
        if not config.SMTP_HOST:
            log.info("Email (SMTP not configured) to=%s subject=%s\n%s", to, subject, body)
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, to, subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as smtp:
                if config.SMTP_TLS:
                    smtp.starttls()
                if config.SMTP_USER:
                    smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
                smtp.send_message(msg)
        except Exception:  # noqa: BLE001 - never let email break the request
            log.exception("Could not send email to %s", to)

    threading.Thread(target=_send, daemon=True).start()


def dispatch(db: Session, user: User, event: str, text: str, item_key: str, actor: User | None) -> bool:
    """Create the in-app notification and/or email that this user asked for. Returns True if anything was sent."""
    if not user.is_active or (actor and user.id == actor.id):
        return False
    prefs = prefs_of(user)
    if item_key and item_key in prefs["muted"]:
        return False
    channels = prefs["events"].get(event, {"inapp": True, "email": False})
    wants_email = channels["email"] and prefs["email_mode"] != "off"
    if not channels["inapp"] and not wants_email:
        return False
    note = Notification(user_id=user.id, actor_id=actor.id if actor else None, item_key=item_key, event=event,
                        text=text, in_app=channels["inapp"], email_pending=wants_email and prefs["email_mode"] == "digest")
    db.add(note)
    if wants_email and prefs["email_mode"] == "instant":
        link = f"{config.BASE_URL}/#/item/{item_key}" if item_key else config.BASE_URL
        send_email(user.email, text, f"{text}\n\nOpen it: {link}\n\nChange what you get in OpenTrack under Profile > Notifications.")
    return True


def send_due_digests(db: Session) -> int:
    """Send one daily email per digest user at their chosen hour. Called by a background loop."""
    now = utcnow()
    today = now.date().isoformat()
    sent = 0
    for user in db.scalars(select(User).where(User.is_active.is_(True))):
        prefs = prefs_of(user)
        if prefs["email_mode"] != "digest" or now.hour != int(prefs["digest_hour"]) or prefs.get("last_digest") == today:
            continue
        pending = list(db.scalars(select(Notification).where(Notification.user_id == user.id,
                                                             Notification.email_pending.is_(True))
                                  .order_by(Notification.created_at)))
        stored = dict(user.prefs or {})
        stored["last_digest"] = today
        user.prefs = stored
        if pending:
            lines = [f"- {n.text}  ({config.BASE_URL}/#/item/{n.item_key})" for n in pending]
            send_email(user.email, f"OpenTrack: {len(pending)} updates", "Your daily summary:\n\n" + "\n".join(lines))
            for n in pending:
                n.email_pending = False
            sent += 1
    db.commit()
    return sent
