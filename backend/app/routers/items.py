"""Work items: create, read, update, bulk edit, comments, links, time, watching, attachments and search."""
import mimetypes
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, notify, webhooks
from ..db import get_db, utcnow
from ..models import Attachment, Comment, History, Link, Membership, Space, Sprint, User, WorkItem, Worklog
from ..query import QueryError, run
from ..security import ROLE_ORDER, current_user, current_user_or_query_token, get_space, space_role
from ..services import (LINK_TYPES, apply_changes, build_context, counts, create_item, involved, item_to_dict,
                        member_ids, mentioned_users, record, space_to_dict)

router = APIRouter(prefix="/api", tags=["work items"])


class BulkIn(BaseModel):
    keys: list[str]
    set: dict = {}
    delete: bool = False


class CommentIn(BaseModel):
    body: str


class LinkIn(BaseModel):
    type: str
    target_key: str


class WorklogIn(BaseModel):
    hours: float
    note: str = ""
    day: str | None = None


class FlagIn(BaseModel):
    on: bool = True


def _item(db: Session, key: str, user: User, need: str = "viewer") -> tuple[WorkItem, Space, str]:
    item = db.scalar(select(WorkItem).where(WorkItem.key == key.upper()))
    if not item:
        raise HTTPException(404, f"{key.upper()} was not found.")
    space, role = get_space(db, item.space.key, user, need=need)
    return item, space, role


def _touch(item: WorkItem):
    item.updated_at = utcnow()


def _names(db: Session) -> dict:
    return {u.id: u.name for u in db.scalars(select(User))}


def _detail(db: Session, item: WorkItem, space: Space, role: str, me: User) -> dict:
    names = _names(db)
    cnt = counts(db, [item.id])
    comments = db.scalars(select(Comment).where(Comment.item_id == item.id).order_by(Comment.created_at))
    history = db.scalars(select(History).where(History.item_id == item.id).order_by(History.at.desc(), History.id.desc()))
    atts = db.scalars(select(Attachment).where(Attachment.item_id == item.id).order_by(Attachment.created_at))
    logs = db.scalars(select(Worklog).where(Worklog.item_id == item.id).order_by(Worklog.day.desc()))
    links = []
    for link in db.scalars(select(Link).where((Link.source_id == item.id) | (Link.target_id == item.id))):
        outgoing = link.source_id == item.id
        other = db.get(WorkItem, link.target_id if outgoing else link.source_id)
        if not other:
            continue
        label = link.type if outgoing else {"blocks": "blocked by", "duplicates": "duplicated by"}.get(link.type, link.type)
        links.append({"id": link.id, "label": label, "key": other.key, "title": other.title, "status": other.status})
    children = db.scalars(select(WorkItem).where(WorkItem.parent_id == item.id).order_by(WorkItem.rank))
    muted = item.key in notify.prefs_of(me)["muted"]
    return {
        "item": item_to_dict(item, cnt), "role": role, "muted": muted,
        "comments": [{"id": c.id, "author_id": c.author_id, "author": names.get(c.author_id, "Imported"),
                      "body": c.body, "created_at": c.created_at.isoformat(),
                      "edited_at": c.edited_at.isoformat() if c.edited_at else None} for c in comments],
        "history": [{"at": h.at.isoformat(), "actor": names.get(h.actor_id, "Import"), "field": h.field,
                     "old": h.old_value, "new": h.new_value} for h in history],
        "attachments": [{"id": a.id, "filename": a.filename, "size": a.size, "content_type": a.content_type,
                         "uploaded_by": names.get(a.uploaded_by, ""), "created_at": a.created_at.isoformat()}
                        for a in atts],
        "worklogs": [{"id": w.id, "user": names.get(w.user_id, ""), "user_id": w.user_id, "hours": w.hours,
                      "note": w.note, "day": w.day.isoformat()} for w in logs],
        "links": links,
        "children": [{"key": c.key, "title": c.title, "status": c.status, "type": c.type} for c in children],
    }


@router.post("/spaces/{key}/items")
def new_item(key: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="member")
    item = create_item(db, space, user, body)
    db.commit()
    payload = item_to_dict(item)
    webhooks.deliver(db, space, "item.created", {"item": payload, "actor": user.handle})
    return payload


@router.get("/items/{key}")
def get_item(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user)
    return _detail(db, item, space, role, user)


@router.patch("/items/{key}")
def update_item(key: str, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, _ = _item(db, key, user, need="member")
    changed = apply_changes(db, space, item, user, body)
    db.commit()
    payload = item_to_dict(item, counts(db, [item.id]))
    if changed:
        webhooks.deliver(db, space, "item.updated", {"item": payload, "changed": changed,
                                                     "actor": user.handle})
    return payload


def _delete_item(db: Session, item: WorkItem, user: User):
    for att in db.scalars(select(Attachment).where(Attachment.item_id == item.id)):
        (config.UPLOAD_DIR / att.storage_name).unlink(missing_ok=True)
    now = utcnow()
    for child in db.scalars(select(WorkItem).where(WorkItem.parent_id == item.id)):
        child.parent_id = None
        child.updated_at = now
    record(db, item, user, "deleted", item.title, "")
    db.flush()
    db.delete(item)


@router.delete("/items/{key}")
def delete_item(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, _ = _item(db, key, user, need="member")
    gone = {"key": item.key, "title": item.title}
    _delete_item(db, item, user)
    db.commit()
    webhooks.deliver(db, space, "item.deleted", {"item": gone, "actor": user.handle})
    return {"deleted": key.upper()}


@router.post("/items/bulk")
def bulk(body: BulkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not body.keys:
        raise HTTPException(422, "Select at least one work item.")
    results = []
    for key in body.keys:
        item, space, _ = _item(db, key, user, need="member")
        if body.delete:
            _delete_item(db, item, user)
        else:
            apply_changes(db, space, item, user, dict(body.set))
            results.append(item)
    db.commit()
    return {"updated": [item_to_dict(i) for i in results], "deleted": body.keys if body.delete else []}


@router.post("/items/{key}/clone")
def clone_item(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, _ = _item(db, key, user, need="member")
    data = item_to_dict(item)
    sprint = db.get(Sprint, item.sprint_id) if item.sprint_id else None
    copy = create_item(db, space, user, {
        "title": f"Copy of {item.title}"[:300], "type": item.type, "priority": item.priority,
        "description": item.description, "assignee_ids": data["assignee_ids"], "points": item.points,
        "estimate": item.estimate_hours, "labels": item.labels, "parent_key": data["parent_key"],
        "sprint_id": sprint.id if sprint and sprint.state != "closed" else None, "start": data["start"], "due": data["due"],
        "checklist": [{"text": c.get("text"), "done": False} for c in item.checklist or []]}, notify_people=False)
    db.commit()
    return item_to_dict(copy)


@router.post("/items/{key}/comments")
def add_comment(key: str, body: CommentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, _ = _item(db, key, user, need="member")
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "Write something before posting.")
    comment = Comment(item_id=item.id, author_id=user.id, body=text, created_at=utcnow())
    db.add(comment)
    record(db, item, user, "comment", "", text[:140])
    if user not in item.watchers:
        item.watchers = item.watchers + [user]
    _touch(item)
    members = member_ids(db, space)
    notified = set()
    for u in mentioned_users(db, text):
        if u.id in members and notify.dispatch(db, u, "mentioned", f"{user.name} mentioned you on {item.key}: {text[:80]}",
                                               item.key, user):
            notified.add(u.id)
    for u in involved(item, db):
        if u.id not in notified and u.id in members:
            notify.dispatch(db, u, "commented", f"{user.name} commented on {item.key}: {text[:80]}", item.key, user)
    db.commit()
    webhooks.deliver(db, space, "comment.created",
                     {"item": {"key": item.key, "title": item.title}, "body": text, "actor": user.handle})
    return _detail(db, item, space, space_role(db, space, user), user)


@router.patch("/comments/{comment_id}")
def edit_comment(comment_id: int, body: CommentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(404, "Comment not found.")
    item = db.get(WorkItem, comment.item_id)
    space, role = get_space(db, item.space.key, user)
    if comment.author_id != user.id and role != "admin":
        raise HTTPException(403, "Only the author or a space admin can edit this comment.")
    if not body.body.strip():
        raise HTTPException(422, "A comment cannot be empty.")
    comment.body = body.body.strip()
    comment.edited_at = utcnow()
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(404, "Comment not found.")
    item = db.get(WorkItem, comment.item_id)
    space, role = get_space(db, item.space.key, user)
    if comment.author_id != user.id and role != "admin":
        raise HTTPException(403, "Only the author or a space admin can delete this comment.")
    db.delete(comment)
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.post("/items/{key}/links")
def add_link(key: str, body: LinkIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user, need="member")
    target, _, _ = _item(db, body.target_key, user)
    if target.id == item.id:
        raise HTTPException(422, "A work item cannot link to itself.")
    kind, source, dest = body.type, item, target
    if kind == "blocked by":
        kind, source, dest = "blocks", target, item
    elif kind == "duplicated by":
        kind, source, dest = "duplicates", target, item
    if kind not in LINK_TYPES:
        raise HTTPException(422, "Link type must be blocks, blocked by, relates to, duplicates or duplicated by.")
    exists = db.scalar(select(Link.id).where(Link.source_id == source.id, Link.target_id == dest.id, Link.type == kind))
    if not exists:
        db.add(Link(source_id=source.id, target_id=dest.id, type=kind))
        record(db, item, user, "link", "", f"{body.type} {target.key}")
        _touch(item)
        _touch(target)
    db.commit()
    return _detail(db, item, space, role, user)


@router.delete("/links/{link_id}")
def delete_link(link_id: int, key: str = Query(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user, need="member")
    link = db.get(Link, link_id)
    if not link or item.id not in (link.source_id, link.target_id):
        raise HTTPException(404, "Link not found on this work item.")
    other = db.get(WorkItem, link.target_id if link.source_id == item.id else link.source_id)
    record(db, item, user, "link", f"{link.type} {other.key if other else ''}", "")
    db.delete(link)
    _touch(item)
    if other:
        _touch(other)
    db.commit()
    return _detail(db, item, space, role, user)


@router.post("/items/{key}/worklogs")
def log_work(key: str, body: WorklogIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user, need="member")
    if not 0 < body.hours <= 24:
        raise HTTPException(422, "Log between 0 and 24 hours at a time.")
    try:
        day = date.fromisoformat(body.day) if body.day else date.today()
    except ValueError:
        raise HTTPException(422, "The day must be a date like 2026-10-01.")
    db.add(Worklog(item_id=item.id, user_id=user.id, hours=body.hours, note=body.note[:500], day=day))
    item.logged_hours = round((item.logged_hours or 0) + body.hours, 2)
    record(db, item, user, "worklog", "", f"{body.hours}h")
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.delete("/worklogs/{worklog_id}")
def delete_worklog(worklog_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    log = db.get(Worklog, worklog_id)
    if not log:
        raise HTTPException(404, "Time entry not found.")
    item = db.get(WorkItem, log.item_id)
    space, role = get_space(db, item.space.key, user, need="member")
    if log.user_id != user.id and role != "admin":
        raise HTTPException(403, "Only the person who logged it or a space admin can remove this entry.")
    item.logged_hours = max(0, round((item.logged_hours or 0) - log.hours, 2))
    db.delete(log)
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.post("/items/{key}/watch")
def watch(key: str, body: FlagIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user)
    watching = user in item.watchers
    if body.on and not watching:
        item.watchers = item.watchers + [user]
    elif not body.on and watching:
        item.watchers = [u for u in item.watchers if u.id != user.id]
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.post("/items/{key}/mute")
def mute(key: str, body: FlagIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user)
    stored = dict(user.prefs or {})
    muted = [k for k in stored.get("muted", []) if k != item.key]
    if body.on:
        muted.append(item.key)
    stored["muted"] = muted
    user.prefs = stored
    db.commit()
    return _detail(db, item, space, role, user)


@router.post("/items/{key}/attachments")
async def upload(key: str, file: UploadFile = File(...), user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    item, space, role = _item(db, key, user, need="member")
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Files can be up to {config.MAX_UPLOAD_MB} MB.")
    name = (file.filename or "file").replace("/", "_").replace("\\", "_")[:200]
    storage = uuid.uuid4().hex
    (config.UPLOAD_DIR / storage).write_bytes(data)
    ctype = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    db.add(Attachment(item_id=item.id, filename=name, content_type=ctype, size=len(data), storage_name=storage,
                      uploaded_by=user.id))
    record(db, item, user, "attachment", "", name)
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.get("/attachments/{attachment_id}")
def download(attachment_id: int, user: User = Depends(current_user_or_query_token), db: Session = Depends(get_db)):
    att = db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(404, "Attachment not found.")
    item = db.get(WorkItem, att.item_id)
    get_space(db, item.space.key, user)
    path = config.UPLOAD_DIR / att.storage_name
    if not path.exists():
        raise HTTPException(410, "The file is missing from storage.")
    inline = att.content_type.startswith("image/") and "svg" not in att.content_type
    return FileResponse(path, media_type=att.content_type if inline else "application/octet-stream",
                        filename=att.filename, content_disposition_type="inline" if inline else "attachment",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    att = db.get(Attachment, attachment_id)
    if not att:
        raise HTTPException(404, "Attachment not found.")
    item = db.get(WorkItem, att.item_id)
    space, role = get_space(db, item.space.key, user, need="member")
    if att.uploaded_by != user.id and role != "admin":
        raise HTTPException(403, "Only the uploader or a space admin can delete this file.")
    (config.UPLOAD_DIR / att.storage_name).unlink(missing_ok=True)
    record(db, item, user, "attachment", att.filename, "")
    db.delete(att)
    _touch(item)
    db.commit()
    return _detail(db, item, space, role, user)


@router.get("/search")
def search(q: str = "", space: str | None = None, limit: int = 200, user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    """Search with OQL across every space you can see, or one space."""
    if space:
        spaces = [get_space(db, space, user)[0]]
    elif user.is_admin:
        spaces = list(db.scalars(select(Space)))
    else:
        spaces = list(db.scalars(select(Space).join(Membership, Membership.space_id == Space.id)
                                 .where(Membership.user_id == user.id)))
    if not spaces:
        return {"items": [], "total": 0}
    items = list(db.scalars(select(WorkItem).where(WorkItem.space_id.in_([s.id for s in spaces]))))
    dicts = [item_to_dict(i) for i in items]
    ctx = build_context(db, spaces, user, dicts)
    try:
        found = run(q, dicts, ctx)
    except QueryError as e:
        raise HTTPException(400, str(e))
    return {"items": found[:min(limit, 1000)], "total": len(found)}
