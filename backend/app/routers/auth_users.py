"""Sign-up, sign-in, profile and site user management."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config, notify
from ..db import get_db
from ..models import User
from ..security import (create_token, current_user, hash_password, make_handle, require_site_admin,
                        verify_password)
from ..services import user_to_dict

router = APIRouter(prefix="/api", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: str | None = None
    current_password: str | None = None
    new_password: str | None = None
    prefs: dict | None = None


class NewUserIn(BaseModel):
    name: str
    email: str
    password: str
    is_admin: bool = False


class UserPatchIn(BaseModel):
    name: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None
    password: str | None = None


def _check_new_user(db: Session, name: str, email: str, password: str) -> str:
    email = email.strip().lower()
    if not name.strip():
        raise HTTPException(422, "Enter a name.")
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(422, "Use a password with at least 8 characters.")
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with that email already exists.")
    return email


@router.get("/auth/status")
def auth_status(db: Session = Depends(get_db)):
    return {"needs_setup": db.scalar(select(func.count(User.id))) == 0, "allow_signup": config.ALLOW_SIGNUP}


@router.post("/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    first = db.scalar(select(func.count(User.id))) == 0
    if not first and not config.ALLOW_SIGNUP:
        raise HTTPException(403, "Sign-up is closed. Ask a site admin to create your account.")
    email = _check_new_user(db, body.name, body.email, body.password)
    user = User(name=body.name.strip(), email=email, handle=make_handle(db, body.name, email),
                password_hash=hash_password(body.password), is_admin=first, prefs={})
    db.add(user)
    db.commit()
    return {"token": create_token(user), "user": user_to_dict(user, private=True)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "That email and password do not match.")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated.")
    return {"token": create_token(user), "user": user_to_dict(user, private=True)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_to_dict(user, private=True)


@router.patch("/me")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(422, "Enter a name.")
        user.name = body.name.strip()[:120]
    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(403, "Your current password is not correct.")
        if len(body.new_password) < 8:
            raise HTTPException(422, "Use a password with at least 8 characters.")
        user.password_hash = hash_password(body.new_password)
    if body.prefs is not None:
        stored = dict(user.prefs or {})
        events = body.prefs.get("events")
        if isinstance(events, dict):
            stored["events"] = {e: {"inapp": bool(c.get("inapp")), "email": bool(c.get("email"))}
                                for e, c in events.items() if e in notify.EVENTS and isinstance(c, dict)}
        if body.prefs.get("email_mode") in ("instant", "digest", "off"):
            stored["email_mode"] = body.prefs["email_mode"]
        if "digest_hour" in body.prefs:
            hour = int(body.prefs["digest_hour"])
            if not 0 <= hour <= 23:
                raise HTTPException(422, "The digest hour must be between 0 and 23.")
            stored["digest_hour"] = hour
        if isinstance(body.prefs.get("muted"), list):
            stored["muted"] = [str(k).upper() for k in body.prefs["muted"]][:500]
        user.prefs = stored
    db.commit()
    return user_to_dict(user, private=True)


@router.get("/users")
def list_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(User).order_by(User.name)
    if not user.is_admin:
        query = query.where(User.is_active.is_(True))
    return [dict(user_to_dict(u), is_admin=u.is_admin) for u in db.scalars(query)]


@router.post("/users")
def create_user(body: NewUserIn, admin: User = Depends(require_site_admin), db: Session = Depends(get_db)):
    email = _check_new_user(db, body.name, body.email, body.password)
    user = User(name=body.name.strip(), email=email, handle=make_handle(db, body.name, email),
                password_hash=hash_password(body.password), is_admin=body.is_admin, prefs={})
    db.add(user)
    db.commit()
    return dict(user_to_dict(user), is_admin=user.is_admin)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatchIn, admin: User = Depends(require_site_admin),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    if user.id == admin.id and (body.is_admin is False or body.is_active is False):
        raise HTTPException(422, "You cannot remove your own admin rights or deactivate yourself.")
    if body.name is not None:
        user.name = body.name.strip()[:120] or user.name
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(422, "Use a password with at least 8 characters.")
        user.password_hash = hash_password(body.password)
    db.commit()
    return dict(user_to_dict(user), is_admin=user.is_admin)
