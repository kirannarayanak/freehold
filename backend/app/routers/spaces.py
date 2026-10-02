"""Spaces, members, sprints, saved filters and the activity feed."""
import re
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import config, webhooks
from ..db import get_db, utcnow
from ..models import (CUSTOM_FIELD_TYPES, DEFAULT_STATUSES, RESERVED_FIELD_KEYS, ROLES, Attachment,
                      CustomField, History, Membership, SavedFilter, Space, Sprint, User, Version,
                      Webhook, WorkItem)
from ..security import current_user, get_space, space_role
from ..services import (category, counts, iso, item_to_dict, record, space_fields, space_links,
                        space_to_dict, sprint_to_dict, user_to_dict, version_to_dict)

router = APIRouter(prefix="/api", tags=["spaces"])
KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")


class SpaceIn(BaseModel):
    key: str
    name: str
    description: str = ""
    template: str = "scrum"  # scrum | kanban


class SpacePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    statuses: list[dict] | None = None
    status_map: dict | None = None
    settings: dict | None = None


class MemberIn(BaseModel):
    email: str | None = None
    user_id: int | None = None
    role: str = "member"


class RoleIn(BaseModel):
    role: str


class SprintIn(BaseModel):
    name: str | None = None
    goal: str = ""
    start: str | None = None
    end: str | None = None


class SprintPatch(BaseModel):
    name: str | None = None
    goal: str | None = None
    start: str | None = None
    end: str | None = None
    state: str | None = None


class CompleteIn(BaseModel):
    move_to: str | int = "backlog"  # backlog | next | <sprint id>


class FilterIn(BaseModel):
    name: str
    query: str
    shared: bool = False


def _date(value, label):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, f"{label} must be a date like 2026-10-01.")


def _members(db: Session, space: Space) -> list[dict]:
    rows = db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                      .where(Membership.space_id == space.id).order_by(User.name)).all()
    return [dict(user_to_dict(u), role=m.role) for m, u in rows]


def _filters(db: Session, space: Space, user: User) -> list[dict]:
    rows = db.scalars(select(SavedFilter).where(SavedFilter.space_id == space.id)
                      .where((SavedFilter.owner_id == user.id) | (SavedFilter.shared.is_(True))).order_by(SavedFilter.name))
    return [{"id": f.id, "name": f.name, "query": f.query, "shared": f.shared, "mine": f.owner_id == user.id}
            for f in rows]


@router.get("/spaces")
def list_spaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.is_admin:
        spaces = db.scalars(select(Space).order_by(Space.name))
        return [space_to_dict(s, "admin") for s in spaces]
    rows = db.execute(select(Space, Membership.role).join(Membership, Membership.space_id == Space.id)
                      .where(Membership.user_id == user.id).order_by(Space.name)).all()
    return [space_to_dict(s, role) for s, role in rows]


@router.post("/spaces")
def create_space(body: SpaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    key = body.key.strip().upper()
    if not KEY_RE.match(key):
        raise HTTPException(422, "Use a key of 2 to 10 letters or digits that starts with a letter, like WEB.")
    if db.scalar(select(Space.id).where(Space.key == key)):
        raise HTTPException(409, f"The key {key} is already taken.")
    if not body.name.strip():
        raise HTTPException(422, "Give the space a name.")
    statuses = [dict(s) for s in DEFAULT_STATUSES]
    if body.template == "kanban":
        statuses = [s for s in statuses if s["name"] != "In review"]
    space = Space(key=key, name=body.name.strip()[:120], description=body.description, statuses=statuses,
                  settings={"template": body.template})
    db.add(space)
    db.flush()
    db.add(Membership(space_id=space.id, user_id=user.id, role="admin"))
    if body.template != "kanban":
        db.add(Sprint(space_id=space.id, name="Sprint 1", state="future"))
    db.commit()
    return space_to_dict(space, "admin")


@router.get("/spaces/{key}")
def space_bundle(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything the board needs in one request; the browser then works from memory."""
    space, role = get_space(db, key, user)
    items = list(db.scalars(select(WorkItem).where(WorkItem.space_id == space.id).order_by(WorkItem.rank)))
    cnt = counts(db, [i.id for i in items])
    sprints = db.scalars(select(Sprint).where(Sprint.space_id == space.id).order_by(Sprint.id))
    return {
        "space": space_to_dict(space, role), "members": _members(db, space),
        "sprints": [sprint_to_dict(s) for s in sprints], "items": [item_to_dict(i, cnt) for i in items],
        "versions": _versions(db, space), "links": space_links(db, space),
        "fields": [_field_to_dict(f) for f in space_fields(db, space)],
        "filters": _filters(db, space, user), "server_time": utcnow().isoformat(),
    }


@router.get("/spaces/{key}/changes")
def space_changes(key: str, since: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Cheap polling: work items changed or deleted since a timestamp, plus the small lists."""
    space, role = get_space(db, key, user)
    try:
        moment = datetime.fromisoformat(since)
    except ValueError:
        raise HTTPException(422, "since must be an ISO timestamp.")
    now = utcnow()
    items = list(db.scalars(select(WorkItem).where(WorkItem.space_id == space.id, WorkItem.updated_at > moment)))
    cnt = counts(db, [i.id for i in items])
    deleted = list(db.scalars(select(History.item_key).where(History.space_id == space.id,
                                                             History.field == "deleted", History.at > moment)))
    sprints = db.scalars(select(Sprint).where(Sprint.space_id == space.id).order_by(Sprint.id))
    return {"space": space_to_dict(space, role), "items": [item_to_dict(i, cnt) for i in items], "deleted": deleted,
            "sprints": [sprint_to_dict(s) for s in sprints], "versions": _versions(db, space),
            "links": space_links(db, space), "members": _members(db, space), "server_time": now.isoformat()}


@router.patch("/spaces/{key}")
def update_space(key: str, body: SpacePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, role = get_space(db, key, user, need="admin")
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(422, "Give the space a name.")
        space.name = body.name.strip()[:120]
    if body.description is not None:
        space.description = body.description
    if body.settings is not None:
        space.settings = {**(space.settings or {}), **body.settings}
    if body.statuses is not None:
        cleaned, seen = [], set()
        for s in body.statuses:
            name = str(s.get("name", "")).strip()[:60]
            cat = s.get("category", "todo")
            if not name or name.lower() in seen:
                raise HTTPException(422, "Each status needs a unique name.")
            if cat not in ("todo", "doing", "done"):
                raise HTTPException(422, "A status category must be todo, doing or done.")
            seen.add(name.lower())
            cleaned.append({"name": name, "category": cat, "wip": max(0, int(s.get("wip") or 0))})
        if len(cleaned) < 2:
            raise HTTPException(422, "A workflow needs at least two statuses.")
        if not any(s["category"] == "done" for s in cleaned):
            raise HTTPException(422, "Mark at least one status as done so work can finish.")
        names = {s["name"] for s in cleaned}
        mapping = body.status_map or {}
        space.statuses = cleaned
        now = utcnow()
        for item in db.scalars(select(WorkItem).where(WorkItem.space_id == space.id, WorkItem.status.not_in(names))):
            target = mapping.get(item.status) if mapping.get(item.status) in names else cleaned[0]["name"]
            record(db, item, user, "status", item.status, target)
            item.status = target
            item.resolved_at = item.resolved_at or now if category(space, target) == "done" else None
            item.updated_at = now
    db.commit()
    return space_to_dict(space, role)


@router.delete("/spaces/{key}")
def delete_space(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    item_ids = select(WorkItem.id).where(WorkItem.space_id == space.id)
    for att in db.scalars(select(Attachment).where(Attachment.item_id.in_(item_ids))):
        (config.UPLOAD_DIR / att.storage_name).unlink(missing_ok=True)
    db.execute(delete(WorkItem).where(WorkItem.space_id == space.id).execution_options(synchronize_session=False))
    db.delete(space)
    db.commit()
    return {"deleted": key.upper()}


@router.get("/spaces/{key}/members")
def list_members(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    return _members(db, space)


@router.post("/spaces/{key}/members")
def add_member(key: str, body: MemberIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    if body.role not in ROLES:
        raise HTTPException(422, "Role must be viewer, member or admin.")
    target = db.get(User, body.user_id) if body.user_id else db.scalar(
        select(User).where(User.email == (body.email or "").strip().lower()))
    if not target:
        raise HTTPException(404, "No account uses that email. A site admin can create it under Admin > People.")
    existing = db.get(Membership, (space.id, target.id))
    if existing:
        existing.role = body.role
    else:
        db.add(Membership(space_id=space.id, user_id=target.id, role=body.role))
    db.commit()
    return _members(db, space)


def _admins_left(db, space, excluding):
    return db.scalar(select(func.count()).select_from(Membership).where(
        Membership.space_id == space.id, Membership.role == "admin", Membership.user_id != excluding))


@router.patch("/spaces/{key}/members/{user_id}")
def change_role(key: str, user_id: int, body: RoleIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    m = db.get(Membership, (space.id, user_id))
    if not m:
        raise HTTPException(404, "That person is not a member of this space.")
    if body.role not in ROLES:
        raise HTTPException(422, "Role must be viewer, member or admin.")
    if m.role == "admin" and body.role != "admin" and not _admins_left(db, space, user_id):
        raise HTTPException(422, "A space needs at least one admin.")
    m.role = body.role
    db.commit()
    return _members(db, space)


@router.delete("/spaces/{key}/members/{user_id}")
def remove_member(key: str, user_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    m = db.get(Membership, (space.id, user_id))
    if not m:
        raise HTTPException(404, "That person is not a member of this space.")
    if m.role == "admin" and not _admins_left(db, space, user_id):
        raise HTTPException(422, "A space needs at least one admin.")
    db.delete(m)
    db.commit()
    return _members(db, space)


def _sprint(db: Session, sprint_id: int, user: User, need="member") -> tuple[Sprint, Space]:
    sprint = db.get(Sprint, sprint_id)
    if not sprint:
        raise HTTPException(404, "Sprint not found.")
    space = db.get(Space, sprint.space_id)
    get_space(db, space.key, user, need=need)
    return sprint, space


class VersionIn(BaseModel):
    name: str
    description: str = ""
    release_date: str | None = None


class VersionPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    release_date: str | None = None
    released: bool | None = None
    archived: bool | None = None


def _versions(db: Session, space: Space) -> list[dict]:
    rows = db.scalars(select(Version).where(Version.space_id == space.id).order_by(Version.id))
    return [version_to_dict(v) for v in rows]


def _version(db: Session, version_id: int, user: User, need: str = "member") -> tuple[Version, Space]:
    version = db.get(Version, version_id)
    if not version:
        raise HTTPException(404, "That version was not found.")
    space = db.get(Space, version.space_id)
    get_space(db, space.key, user, need=need)
    return version, space


@router.get("/spaces/{key}/versions")
def list_versions(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    return _versions(db, space)


@router.post("/spaces/{key}/versions")
def create_version(key: str, body: VersionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="member")
    name = body.name.strip()[:120]
    if not name:
        raise HTTPException(422, "A version needs a name.")
    if db.scalar(select(Version.id).where(Version.space_id == space.id, Version.name == name)):
        raise HTTPException(409, f"This space already has a version called {name}.")
    version = Version(space_id=space.id, name=name, description=body.description or "",
                      release_date=_date(body.release_date, "Release date"))
    db.add(version)
    db.commit()
    return version_to_dict(version)


@router.patch("/versions/{version_id}")
def update_version(version_id: int, body: VersionPatch, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    version, space = _version(db, version_id, user)
    if body.name is not None:
        name = body.name.strip()[:120]
        if not name:
            raise HTTPException(422, "A version needs a name.")
        clash = db.scalar(select(Version.id).where(Version.space_id == space.id, Version.name == name,
                                                   Version.id != version.id))
        if clash:
            raise HTTPException(409, f"This space already has a version called {name}.")
        version.name = name
    if body.description is not None:
        version.description = body.description
    if body.release_date is not None:
        version.release_date = _date(body.release_date, "Release date")
    if body.archived is not None:
        version.archived = body.archived
    if body.released is not None and body.released != version.released:
        if body.released:
            open_items = db.scalar(select(func.count(WorkItem.id)).where(
                WorkItem.version_id == version.id,
                WorkItem.resolved_at.is_(None)))
            if open_items:
                raise HTTPException(422, f"{open_items} item(s) in {version.name} are not finished. "
                                         "Move them to another version or finish them first.")
        version.released = body.released
        version.released_at = utcnow() if body.released else None
    db.commit()
    return version_to_dict(version)


@router.get("/versions/{version_id}/notes")
def version_notes(version_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Release notes as markdown, grouped by type and ordered the way people read them.

    Generated rather than written, so they cannot drift from what actually shipped.
    """
    version = db.get(Version, version_id)
    if not version:
        raise HTTPException(404, "That version was not found.")
    space = db.get(Space, version.space_id)
    get_space(db, space.key, user)
    items = list(db.scalars(select(WorkItem).where(WorkItem.version_id == version.id)
                            .order_by(WorkItem.number)))
    done = [i for i in items if category(space, i.status) == "done"]
    open_items = [i for i in items if category(space, i.status) != "done"]

    lines = [f"# {space.name} {version.name}", ""]
    if version.release_date:
        lines += [f"Released {version.release_date.isoformat()}", ""]
    if version.description:
        lines += [version.description, ""]
    if not items:
        lines += ["_Nothing is assigned to this version yet._"]
    # Bugs first: the thing people scan release notes for is whether their bug is fixed.
    for heading, types in (("Fixes", ("Bug",)), ("Features", ("Story", "Epic")), ("Other", ("Task", "Subtask"))):
        group = [i for i in done if i.type in types]
        if group:
            lines += [f"## {heading}", ""]
            lines += [f"- **{i.key}** {i.title}" for i in group]
            lines += [""]
    if open_items:
        lines += ["## Still open", "",
                  "_Assigned to this version but not finished._", ""]
        lines += [f"- **{i.key}** {i.title} ({i.status})" for i in open_items]
        lines += [""]
    lines += ["---", f"_{len(done)} of {len(items)} items complete._"]
    return {"version": version.name, "markdown": "\n".join(lines),
            "counts": {"total": len(items), "done": len(done), "open": len(open_items)}}


@router.delete("/versions/{version_id}")
def delete_version(version_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    version, _ = _version(db, version_id, user, need="admin")
    # Work is never deleted with the version: the column is SET NULL, so items simply lose their
    # fix version and stay where they are.
    db.delete(version)
    db.commit()
    return {"ok": True}


class WebhookIn(BaseModel):
    url: str
    events: list[str] = []


class WebhookPatch(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    active: bool | None = None


def _hook_to_dict(h: Webhook, secret: str | None = None) -> dict:
    """The secret is returned once, when it is created. After that only whether one is set,
    because an admin screen that shows every signing secret is a secret-leaking screen."""
    d = {"id": h.id, "url": h.url, "events": h.events, "active": h.active, "has_secret": bool(h.secret),
         "last_status": h.last_status, "last_error": h.last_error, "last_at": iso(h.last_at)}
    if secret:
        d["secret"] = secret
    return d


def _check_events(events: list[str]) -> list[str]:
    bad = [e for e in events if e not in webhooks.EVENT_NAMES]
    if bad:
        raise HTTPException(422, f"Unknown event(s): {', '.join(bad)}. "
                                 f"Valid events are {', '.join(webhooks.EVENT_NAMES)}.")
    return events


def _hook(db: Session, hook_id: int, user: User) -> tuple[Webhook, Space]:
    hook = db.get(Webhook, hook_id)
    if not hook:
        raise HTTPException(404, "That webhook was not found.")
    space = db.get(Space, hook.space_id)
    get_space(db, space.key, user, need="admin")
    return hook, space


class FieldIn(BaseModel):
    name: str
    key: str | None = None
    type: str = "text"
    options: list[str] = []
    description: str = ""
    required: bool = False


class FieldPatch(BaseModel):
    name: str | None = None
    type: str | None = None
    options: list[str] | None = None
    description: str | None = None
    required: bool | None = None
    archived: bool | None = None
    position: int | None = None


def _field_to_dict(f: CustomField) -> dict:
    return {"id": f.id, "key": f.key, "name": f.name, "type": f.type, "options": f.options,
            "description": f.description, "required": f.required, "archived": f.archived,
            "position": f.position}


def _slug(name: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return (out or "field")[:40]


def _check_key(db: Session, space: Space, key: str, exclude: int | None = None) -> str:
    if key in RESERVED_FIELD_KEYS:
        raise HTTPException(422, f"'{key}' is the name of a built-in field. "
                                 "Pick another name, or the filter box could not tell them apart.")
    q = select(CustomField.id).where(CustomField.space_id == space.id, CustomField.key == key)
    if exclude:
        q = q.where(CustomField.id != exclude)
    if db.scalar(q):
        raise HTTPException(409, f"This space already has a field with the key '{key}'.")
    return key


@router.get("/spaces/{key}/fields")
def list_fields(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    rows = db.scalars(select(CustomField).where(CustomField.space_id == space.id)
                      .order_by(CustomField.position, CustomField.id))
    return {"fields": [_field_to_dict(f) for f in rows], "types": list(CUSTOM_FIELD_TYPES)}


@router.post("/spaces/{key}/fields")
def create_field(key: str, body: FieldIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    name = body.name.strip()[:120]
    if not name:
        raise HTTPException(422, "A field needs a name.")
    if body.type not in CUSTOM_FIELD_TYPES:
        raise HTTPException(422, f"Type must be one of {', '.join(CUSTOM_FIELD_TYPES)}.")
    if body.type in ("select", "multiselect") and not body.options:
        raise HTTPException(422, f"A {body.type} field needs at least one option.")
    slug = _check_key(db, space, _slug(body.key or name))
    top = db.scalar(select(func.max(CustomField.position)).where(CustomField.space_id == space.id)) or 0
    field = CustomField(space_id=space.id, key=slug, name=name, type=body.type,
                        options=[o.strip() for o in body.options if o.strip()],
                        description=body.description or "", required=body.required, position=top + 1)
    db.add(field)
    db.commit()
    return _field_to_dict(field)


@router.patch("/fields/{field_id}")
def update_field(field_id: int, body: FieldPatch, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    field = db.get(CustomField, field_id)
    if not field:
        raise HTTPException(404, "That field was not found.")
    space = db.get(Space, field.space_id)
    get_space(db, space.key, user, need="admin")
    if body.name is not None:
        field.name = body.name.strip()[:120] or field.name
    if body.type is not None and body.type != field.type:
        # The key is what values are stored under, so changing the type would reinterpret every
        # value already saved. Archiving and adding a new field keeps the old data readable.
        raise HTTPException(422, "A field's type cannot be changed once it exists. "
                                 "Archive it and add a new one, so existing values keep their meaning.")
    if body.options is not None:
        field.options = [o.strip() for o in body.options if o.strip()]
    if body.description is not None:
        field.description = body.description
    if body.required is not None:
        field.required = body.required
    if body.archived is not None:
        field.archived = body.archived
    if body.position is not None:
        field.position = body.position
    db.commit()
    return _field_to_dict(field)


@router.delete("/fields/{field_id}")
def delete_field(field_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Deleting a definition leaves the values in place but unreadable, so archiving is offered
    first and deletion says how many items would be affected."""
    field = db.get(CustomField, field_id)
    if not field:
        raise HTTPException(404, "That field was not found.")
    space = db.get(Space, field.space_id)
    get_space(db, space.key, user, need="admin")
    db.delete(field)
    db.commit()
    return {"ok": True}


@router.get("/spaces/{key}/webhooks")
def list_webhooks(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    rows = db.scalars(select(Webhook).where(Webhook.space_id == space.id).order_by(Webhook.id))
    return {"webhooks": [_hook_to_dict(h) for h in rows], "events": [list(e) for e in webhooks.EVENTS]}


@router.post("/spaces/{key}/webhooks")
def create_webhook(key: str, body: WebhookIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(422, "A webhook URL must start with http:// or https://")
    secret = secrets.token_urlsafe(32)
    hook = Webhook(space_id=space.id, url=url[:500], secret=secret, events=_check_events(body.events), active=True)
    db.add(hook)
    db.commit()
    return _hook_to_dict(hook, secret=secret)


@router.patch("/webhooks/{hook_id}")
def update_webhook(hook_id: int, body: WebhookPatch, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    hook, _ = _hook(db, hook_id, user)
    if body.url is not None:
        url = body.url.strip()
        if not url.startswith(("http://", "https://")):
            raise HTTPException(422, "A webhook URL must start with http:// or https://")
        hook.url = url[:500]
    if body.events is not None:
        hook.events = _check_events(body.events)
    if body.active is not None:
        hook.active = body.active
    db.commit()
    return _hook_to_dict(hook)


@router.delete("/webhooks/{hook_id}")
def delete_webhook(hook_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    hook, _ = _hook(db, hook_id, user)
    db.delete(hook)
    db.commit()
    return {"ok": True}


@router.post("/webhooks/{hook_id}/test")
def test_webhook(hook_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Send a ping so an admin can confirm the receiver works before relying on it."""
    hook, space = _hook(db, hook_id, user)
    webhooks.deliver(db, space, "item.updated",
                     {"test": True, "item": {"key": f"{space.key}-0", "title": "Test ping from Freehold"},
                      "actor": user.handle})
    return {"ok": True, "note": "Queued. Check the hook's last status in a moment."}


@router.post("/spaces/{key}/sprints")
def create_sprint(key: str, body: SprintIn = SprintIn(), user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="member")
    n = db.scalar(select(func.count(Sprint.id)).where(Sprint.space_id == space.id)) + 1
    sprint = Sprint(space_id=space.id, name=(body.name or f"Sprint {n}").strip()[:120], goal=body.goal,
                    start_date=_date(body.start, "Start date"), end_date=_date(body.end, "End date"), state="future")
    db.add(sprint)
    db.commit()
    return sprint_to_dict(sprint)


@router.patch("/sprints/{sprint_id}")
def update_sprint(sprint_id: int, body: SprintPatch, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    sprint, space = _sprint(db, sprint_id, user)
    if body.name is not None:
        sprint.name = body.name.strip()[:120] or sprint.name
    if body.goal is not None:
        sprint.goal = body.goal
    if body.start is not None:
        sprint.start_date = _date(body.start, "Start date")
    if body.end is not None:
        sprint.end_date = _date(body.end, "End date")
    if body.state == "active" and sprint.state != "active":
        if sprint.state == "closed":
            raise HTTPException(422, "A completed sprint cannot be restarted.")
        if db.scalar(select(Sprint.id).where(Sprint.space_id == space.id, Sprint.state == "active")):
            raise HTTPException(422, "Complete the active sprint before starting another.")
        sprint.state = "active"
        sprint.start_date = sprint.start_date or date.today()
        sprint.end_date = sprint.end_date or sprint.start_date + timedelta(days=13)
        sprint.committed_points = sum(i.points or 0 for i in db.scalars(
            select(WorkItem).where(WorkItem.sprint_id == sprint.id)))
    db.commit()
    return sprint_to_dict(sprint)


@router.post("/sprints/{sprint_id}/complete")
def complete_sprint(sprint_id: int, body: CompleteIn = CompleteIn(), user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    sprint, space = _sprint(db, sprint_id, user)
    if sprint.state != "active":
        raise HTTPException(422, "Only the active sprint can be completed.")
    items = list(db.scalars(select(WorkItem).where(WorkItem.sprint_id == sprint.id)))
    done = [i for i in items if category(space, i.status) == "done"]
    open_items = [i for i in items if i not in done]
    target = None
    if body.move_to == "next":
        n = db.scalar(select(func.count(Sprint.id)).where(Sprint.space_id == space.id)) + 1
        target = Sprint(space_id=space.id, name=f"Sprint {n}", state="future")
        db.add(target)
        db.flush()
    elif body.move_to not in ("backlog", "", None):
        target = db.get(Sprint, int(body.move_to))
        if not target or target.space_id != space.id or target.state == "closed":
            raise HTTPException(422, "Pick a future sprint in this space, or the backlog.")
    now = utcnow()
    for item in open_items:
        record(db, item, user, "sprint", sprint.name, target.name if target else "Backlog")
        item.sprint_id = target.id if target else None
        item.updated_at = now
    sprint.state = "closed"
    sprint.closed_at = now
    sprint.completed_points = sum(i.points or 0 for i in done)
    db.commit()
    return {"sprint": sprint_to_dict(sprint), "moved": len(open_items), "completed": len(done),
            "next": sprint_to_dict(target) if target else None}


@router.delete("/sprints/{sprint_id}")
def delete_sprint(sprint_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sprint, space = _sprint(db, sprint_id, user)
    if sprint.state != "future":
        raise HTTPException(422, "Only sprints that have not started can be deleted.")
    now = utcnow()
    for item in db.scalars(select(WorkItem).where(WorkItem.sprint_id == sprint.id)):
        item.sprint_id = None
        item.updated_at = now
    db.delete(sprint)
    db.commit()
    return {"deleted": sprint_id}


@router.get("/spaces/{key}/filters")
def list_filters(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    return _filters(db, space, user)


@router.post("/spaces/{key}/filters")
def save_filter(key: str, body: FilterIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    if not body.name.strip() or not body.query.strip():
        raise HTTPException(422, "A saved filter needs a name and a query.")
    db.add(SavedFilter(space_id=space.id, owner_id=user.id, name=body.name.strip()[:120], query=body.query,
                       shared=body.shared))
    db.commit()
    return _filters(db, space, user)


@router.delete("/filters/{filter_id}")
def delete_filter(filter_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = db.get(SavedFilter, filter_id)
    if not f:
        raise HTTPException(404, "Filter not found.")
    space = db.get(Space, f.space_id)
    if f.owner_id != user.id and space_role(db, space, user) != "admin":
        raise HTTPException(403, "Only the owner or a space admin can delete this filter.")
    db.delete(f)
    db.commit()
    return _filters(db, space, user)


@router.get("/spaces/{key}/activity")
def activity(key: str, limit: int = 60, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    rows = db.execute(select(History, User.name).outerjoin(User, User.id == History.actor_id)
                      .where(History.space_id == space.id).order_by(History.at.desc(), History.id.desc())
                      .limit(min(limit, 300))).all()
    return [{"at": h.at.isoformat(), "actor": name or "Import", "key": h.item_key, "field": h.field,
             "old": h.old_value, "new": h.new_value} for h, name in rows]
