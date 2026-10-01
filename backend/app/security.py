"""Passwords, tokens and permission checks."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .db import get_db, utcnow
from .models import ApiToken, Membership, Space, User

ROLE_ORDER = {"viewer": 0, "member": 1, "admin": 2}
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)

LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "8"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
_failures: dict[str, list[float]] = {}


def _recent(key: str, now: float) -> list[float]:
    hits = [t for t in _failures.get(key, []) if now - t < LOGIN_WINDOW_SECONDS]
    if hits:
        _failures[key] = hits
    else:
        _failures.pop(key, None)
    return hits


def check_login_allowed(request: Request, email: str) -> None:
    """Refuse a sign-in attempt after repeated failures, before any password is checked.

    Counted per client address and per address+email together, so one attacker spraying many
    accounts is stopped as well as one account being brute forced from many places. The window
    is in memory, which means it resets on restart and is not shared between app containers:
    it raises the cost of guessing, it is not a substitute for a rate limiter at the proxy.
    """
    now = time.monotonic()
    client = request.client.host if request.client else "unknown"
    for key in (f"ip:{client}", f"user:{client}:{email.strip().lower()}"):
        if len(_recent(key, now)) >= LOGIN_MAX_FAILURES:
            raise HTTPException(429, "Too many sign-in attempts. Wait a few minutes and try again.",
                                headers={"Retry-After": str(LOGIN_WINDOW_SECONDS)})


def record_login_failure(request: Request, email: str) -> None:
    now = time.monotonic()
    client = request.client.host if request.client else "unknown"
    for key in (f"ip:{client}", f"user:{client}:{email.strip().lower()}"):
        _failures.setdefault(key, []).append(now)


def clear_login_failures(request: Request, email: str) -> None:
    client = request.client.host if request.client else "unknown"
    _failures.pop(f"user:{client}:{email.strip().lower()}", None)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return hmac.compare_digest(digest, expected)


TOKEN_PREFIX = "fh_"


def new_api_token() -> tuple[str, str, str]:
    """Returns (token, prefix, hash). The token is shown once and never stored."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[:12], hash_api_token(raw)


def hash_api_token(raw: str) -> str:
    # The token is 256 bits of randomness, so a plain SHA-256 is right here. Password hashing is
    # slow on purpose to survive low-entropy secrets; doing that per API request would be a cost
    # with no matching benefit.
    return hashlib.sha256(raw.encode()).hexdigest()


def _user_from_api_token(raw: str, db: Session) -> User | None:
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw)))
    if not token:
        raise HTTPException(401, "That API token is not valid.")
    if token.expires_at and token.expires_at < utcnow():
        raise HTTPException(401, "That API token has expired.")
    user = db.get(User, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "This account is not active.")
    # Written on a best-effort basis: a failure here must not refuse an otherwise valid request.
    try:
        token.last_used_at = utcnow()
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return user


def create_token(user: User) -> str:
    payload = {"sub": str(user.id), "exp": utcnow() + timedelta(hours=config.TOKEN_HOURS)}
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def _user_from_token(token: str, db: Session) -> User:
    if token.startswith(TOKEN_PREFIX):
        return _user_from_api_token(token, db)
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Your session has expired. Sign in again.")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "This account is not active.")
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(401, "Sign in to continue.")
    return _user_from_token(header[7:].strip(), db)


def current_user_or_query_token(request: Request, db: Session = Depends(get_db)) -> User:
    """Downloads opened with a plain link cannot send headers, so they may pass ?token=."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return _user_from_token(header[7:].strip(), db)
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    return _user_from_token(token, db)


def require_site_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Only site admins can do this.")
    return user


def space_role(db: Session, space: Space, user: User) -> str | None:
    if user.is_admin:
        return "admin"
    m = db.get(Membership, (space.id, user.id))
    return m.role if m else None


def get_space(db: Session, key: str, user: User, need: str = "viewer") -> tuple[Space, str]:
    space = db.scalar(select(Space).where(Space.key == key.upper()))
    role = space_role(db, space, user) if space else None
    if not space or role is None:
        raise HTTPException(404, f"Space {key.upper()} was not found or you are not a member.")
    if ROLE_ORDER[role] < ROLE_ORDER[need]:
        raise HTTPException(403, f"You need the {need} role in {space.key} to do this.")
    return space, role


def make_handle(db: Session, name: str, email: str) -> str:
    base = re.sub(r"[^a-z0-9._-]", "", (name or email.split("@")[0]).lower().replace(" ", "."))[:40] or "user"
    handle, n = base, 1
    while db.scalar(select(User.id).where(User.handle == handle)):
        n += 1
        handle = f"{base}{n}"
    return handle
