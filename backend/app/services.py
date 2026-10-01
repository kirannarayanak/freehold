"""Domain logic shared by the API routers: serialising, validating and changing work items."""
import re
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import notify
from .db import utcnow
from .models import (PRIORITIES, TYPES, Attachment, Comment, History, Link, Membership, Space, Sprint, User,
                     Version, WorkItem)
from .query import Context

MENTION_RE = re.compile(r"(?<![\w@])@([a-z0-9._-]+)", re.I)
LINK_TYPES = ("blocks", "relates to", "duplicates")


def iso(value):
    return value.isoformat() if value else None


def user_to_dict(u: User, private: bool = False) -> dict:
    d = {"id": u.id, "name": u.name, "handle": u.handle, "email": u.email, "is_active": u.is_active}
    if private:
        d.update(is_admin=u.is_admin, prefs=notify.prefs_of(u))
    return d


def space_to_dict(s: Space, role: str | None = None) -> dict:
    return {"id": s.id, "key": s.key, "name": s.name, "description": s.description, "statuses": s.statuses,
            "settings": s.settings or {}, "role": role}


def version_to_dict(v: "Version") -> dict:
    return {"id": v.id, "name": v.name, "description": v.description, "release_date": iso(v.release_date),
            "released": v.released, "archived": v.archived, "released_at": iso(v.released_at)}


def sprint_to_dict(s: Sprint) -> dict:
    return {"id": s.id, "name": s.name, "goal": s.goal, "start": iso(s.start_date), "end": iso(s.end_date),
            "state": s.state, "committed_points": s.committed_points, "completed_points": s.completed_points,
            "closed_at": iso(s.closed_at)}


def category(space: Space, status: str) -> str:
    for s in space.statuses:
        if s["name"] == status:
            return s.get("category", "todo")
    return "todo"


def counts(db: Session, item_ids: list[int]) -> dict:
    if not item_ids:
        return {"comments": {}, "attachments": {}, "status_since": {}}
    c = dict(db.execute(select(Comment.item_id, func.count()).where(Comment.item_id.in_(item_ids))
                        .group_by(Comment.item_id)).all())
    a = dict(db.execute(select(Attachment.item_id, func.count()).where(Attachment.item_id.in_(item_ids))
                        .group_by(Attachment.item_id)).all())
    # When the status last changed, which is what "stale" is measured from. Age is the wrong
    # number: an item opened a year ago and worked on yesterday is not stale.
    since = dict(db.execute(select(History.item_id, func.max(History.at))
                            .where(History.item_id.in_(item_ids),
                                   History.field.in_(("created", "status")))
                            .group_by(History.item_id)).all())
    return {"comments": c, "attachments": a, "status_since": since}


def item_to_dict(item: WorkItem, cnt: dict | None = None) -> dict:
    cnt = cnt or {"comments": {}, "attachments": {}, "status_since": {}}
    return {
        "id": item.id, "key": item.key, "number": item.number, "type": item.type, "title": item.title,
        "description": item.description or "", "status": item.status, "priority": item.priority,
        "assignee_ids": sorted(u.id for u in item.assignees), "watcher_ids": sorted(u.id for u in item.watchers),
        "reporter_id": item.reporter_id, "points": item.points, "estimate": item.estimate_hours,
        "logged": round(item.logged_hours or 0, 2), "start": iso(item.start_date), "due": iso(item.due_date),
        "labels": list(item.labels or []), "checklist": list(item.checklist or []),
        "parent_key": item.parent.key if item.parent else None, "sprint_id": item.sprint_id,
        "version_id": item.version_id,
        "status_since": iso(cnt.get("status_since", {}).get(item.id) or item.updated_at),
        "rank": item.rank, "external_key": item.external_key, "created_at": iso(item.created_at),
        "updated_at": iso(item.updated_at), "resolved_at": iso(item.resolved_at),
        "comment_count": cnt["comments"].get(item.id, 0), "attachment_count": cnt["attachments"].get(item.id, 0),
    }


def link_to_dict(link: Link, keys: dict) -> dict:
    return {"id": link.id, "type": link.type, "source_key": keys.get(link.source_id),
            "target_key": keys.get(link.target_id)}


def space_links(db: Session, space: Space) -> list[dict]:
    rows = db.execute(select(Link, WorkItem.key).join(WorkItem, WorkItem.id == Link.source_id)
                      .where(WorkItem.space_id == space.id)).all()
    target_ids = {l.target_id for l, _ in rows}
    keys = dict(db.execute(select(WorkItem.id, WorkItem.key).where(WorkItem.id.in_(target_ids))).all()) if target_ids else {}
    out = []
    for link, source_key in rows:
        keys[link.source_id] = source_key
        out.append(link_to_dict(link, keys))
    return out


def blocked_keys(db: Session, spaces: list[Space]) -> set[str]:
    by_id = {s.id: s for s in spaces}
    src = WorkItem.__table__.alias("src")
    tgt = WorkItem.__table__.alias("tgt")
    rows = db.execute(select(src.c.status, src.c.space_id, tgt.c.key).select_from(Link.__table__)
                      .join(src, src.c.id == Link.source_id).join(tgt, tgt.c.id == Link.target_id)
                      .where(Link.type == "blocks", tgt.c.space_id.in_(list(by_id)))).all()
    out = set()
    for status, space_id, target_key in rows:
        source_space = by_id.get(space_id)
        if source_space is None or category(source_space, status) != "done":
            out.add(target_key)
    return out


def build_context(db: Session, spaces: list[Space], me: User, items: list[dict]) -> Context:
    users = {u.id: {"name": u.name, "handle": u.handle, "email": u.email} for u in db.scalars(select(User))}
    sprints = {s.id: {"name": s.name, "state": s.state}
               for s in db.scalars(select(Sprint).where(Sprint.space_id.in_([s.id for s in spaces])))}
    versions = {v.id: {"name": v.name, "released": v.released}
                for v in db.scalars(select(Version).where(Version.space_id.in_([s.id for s in spaces])))}
    cats = {}
    for s in spaces:
        for st in s.statuses:
            cats.setdefault(st["name"], st.get("category", "todo"))
    stale_days = 14
    for sp in spaces:
        stale_days = int((sp.settings or {}).get("stale_days") or stale_days)
    return Context(users=users, sprints=sprints, versions=versions, categories=cats, stale_days=stale_days,
                   parents={i["key"]: i["title"] for i in items},
                   blocked=blocked_keys(db, spaces), me=me.id, today=date.today())


def member_ids(db: Session, space: Space) -> set[int]:
    return set(db.scalars(select(Membership.user_id).where(Membership.space_id == space.id)))


def record(db: Session, item: WorkItem, actor: User | None, field: str, old="", new="") -> None:
    db.add(History(space_id=item.space_id, item_id=item.id, item_key=item.key, actor_id=actor.id if actor else None,
                   field=field, old_value="" if old is None else str(old), new_value="" if new is None else str(new),
                   at=utcnow()))


def mentioned_users(db: Session, text: str) -> list[User]:
    handles = {h.lower() for h in MENTION_RE.findall(text or "")}
    if not handles:
        return []
    return list(db.scalars(select(User).where(func.lower(User.handle).in_(handles), User.is_active.is_(True))))


def involved(item: WorkItem, db: Session) -> list[User]:
    people = {u.id: u for u in item.assignees + item.watchers}
    if item.reporter_id and item.reporter_id not in people:
        reporter = db.get(User, item.reporter_id)
        if reporter:
            people[reporter.id] = reporter
    return list(people.values())


def _parse_date(value, name):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(422, f"{name} must be a date like 2026-10-01.")


def _number(value, name):
    if value in (None, ""):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise HTTPException(422, f"{name} must be a number.")
    if n < 0:
        raise HTTPException(422, f"{name} cannot be negative.")
    return n


def _fmt_users(users):
    return ", ".join(sorted(u.name for u in users)) or "Unassigned"


def apply_changes(db: Session, space: Space, item: WorkItem, actor: User, data: dict, notify_people=True) -> list[str]:
    """Validate and apply a partial update. Records history and sends notifications. Returns changed field names."""
    changed: list[str] = []
    members = member_ids(db, space)
    newly_assigned: list[User] = []
    new_mentions: list[User] = []

    def set_field(name, attr, new, old_display=None, new_display=None):
        old = getattr(item, attr)
        if old == new:
            return
        record(db, item, actor, name, old_display if old_display is not None else (iso(old) if isinstance(old, date) else old),
               new_display if new_display is not None else (iso(new) if isinstance(new, date) else new))
        setattr(item, attr, new)
        changed.append(name)

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            raise HTTPException(422, "A work item needs a summary.")
        set_field("title", "title", title[:300])
    if "description" in data:
        before = {u.id for u in mentioned_users(db, item.description)}
        set_field("description", "description", data["description"] or "", "", "")
        new_mentions = [u for u in mentioned_users(db, item.description) if u.id not in before]
    if "type" in data:
        if data["type"] not in TYPES:
            raise HTTPException(422, f"Type must be one of {', '.join(TYPES)}.")
        set_field("type", "type", data["type"])
    if "priority" in data:
        if data["priority"] not in PRIORITIES:
            raise HTTPException(422, f"Priority must be one of {', '.join(PRIORITIES)}.")
        set_field("priority", "priority", data["priority"])
    if "status" in data:
        names = [s["name"] for s in space.statuses]
        if data["status"] not in names:
            raise HTTPException(422, f"{data['status']} is not a status in {space.key}. Use one of: {', '.join(names)}.")
        was_done = category(space, item.status) == "done" if item.status else False
        set_field("status", "status", data["status"])
        now_done = category(space, item.status) == "done"
        if now_done and not was_done:
            item.resolved_at = utcnow()
        elif was_done and not now_done:
            item.resolved_at = None
    if "assignee_ids" in data:
        ids = [int(i) for i in (data["assignee_ids"] or [])]
        unknown = [i for i in ids if i not in members]
        if unknown:
            raise HTTPException(422, "Assignees must be members of this space.")
        users = list(db.scalars(select(User).where(User.id.in_(ids)))) if ids else []
        old_ids = {u.id for u in item.assignees}
        if old_ids != set(ids):
            record(db, item, actor, "assignees", _fmt_users(item.assignees), _fmt_users(users))
            newly_assigned = [u for u in users if u.id not in old_ids]
            item.assignees = users
            changed.append("assignees")
    if "reporter_id" in data:
        rid = data["reporter_id"]
        if rid is not None and int(rid) not in members:
            raise HTTPException(422, "The reporter must be a member of this space.")
        old = db.get(User, item.reporter_id).name if item.reporter_id and db.get(User, item.reporter_id) else ""
        new = db.get(User, int(rid)).name if rid is not None else ""
        set_field("reporter", "reporter_id", int(rid) if rid is not None else None, old, new)
    if "points" in data:
        set_field("points", "points", _number(data["points"], "Story points"))
    if "estimate" in data:
        set_field("estimate", "estimate_hours", _number(data["estimate"], "Estimate"))
    if "start" in data:
        set_field("start", "start_date", _parse_date(data["start"], "Start date"))
    if "due" in data:
        set_field("due", "due_date", _parse_date(data["due"], "Due date"))
    if "labels" in data:
        labels = []
        for label in data["labels"] or []:
            label = str(label).strip()[:40]
            if label and label not in labels:
                labels.append(label)
        set_field("labels", "labels", labels, ", ".join(item.labels or []), ", ".join(labels))
    if "checklist" in data:
        checklist = [{"text": str(c.get("text", "")).strip()[:300], "done": bool(c.get("done"))}
                     for c in (data["checklist"] or []) if str(c.get("text", "")).strip()]
        done = sum(1 for c in checklist if c["done"])
        old = item.checklist or []
        set_field("checklist", "checklist", checklist, f"{sum(1 for c in old if c.get('done'))}/{len(old)} done",
                  f"{done}/{len(checklist)} done")
    if "parent_key" in data:
        parent = None
        if data["parent_key"]:
            parent = db.scalar(select(WorkItem).where(WorkItem.key == str(data["parent_key"]).upper()))
            if not parent or parent.space_id != space.id:
                raise HTTPException(422, "The parent must be a work item in this space.")
            walk = parent
            while walk is not None:
                if walk.id == item.id:
                    raise HTTPException(422, "That parent would create a loop.")
                walk = walk.parent
        old_key = item.parent.key if item.parent else ""
        if (parent.id if parent else None) != item.parent_id:
            record(db, item, actor, "parent", old_key, parent.key if parent else "")
            item.parent = parent
            item.parent_id = parent.id if parent else None
            changed.append("parent")
    if "sprint_id" in data:
        sid = data["sprint_id"]
        sprint = None
        if sid not in (None, "", "backlog"):
            sprint = db.get(Sprint, int(sid))
            if not sprint or sprint.space_id != space.id:
                raise HTTPException(422, "That sprint is not in this space.")
            if sprint.state == "closed":
                raise HTTPException(422, "You cannot add work to a completed sprint.")
        old = db.get(Sprint, item.sprint_id).name if item.sprint_id and db.get(Sprint, item.sprint_id) else "Backlog"
        set_field("sprint", "sprint_id", sprint.id if sprint else None, old, sprint.name if sprint else "Backlog")
    if "version_id" in data:
        vid = data["version_id"]
        version = None
        if vid not in (None, "", "none"):
            version = db.get(Version, int(vid))
            if not version or version.space_id != space.id:
                raise HTTPException(422, "That version is not in this space.")
            if version.archived:
                raise HTTPException(422, "That version is archived. Unarchive it before assigning work to it.")
        old = db.get(Version, item.version_id).name if item.version_id and db.get(Version, item.version_id) else ""
        set_field("version", "version_id", version.id if version else None, old, version.name if version else "")
    if "rank" in data and data["rank"] is not None:
        item.rank = float(data["rank"])

    if changed or "rank" in data:
        item.updated_at = utcnow()

    if notify_people and changed:
        notified = set()
        for u in newly_assigned:
            if notify.dispatch(db, u, "assigned", f"{actor.name} assigned you {item.key}: {item.title}", item.key, actor):
                notified.add(u.id)
        for u in new_mentions:
            if u.id not in notified and u.id in members and notify.dispatch(
                    db, u, "mentioned", f"{actor.name} mentioned you in {item.key}: {item.title}", item.key, actor):
                notified.add(u.id)
        rest = [c for c in changed if c not in ("assignees", "status")]
        for u in involved(item, db):
            if u.id in notified or u.id not in members:
                continue
            if "status" in changed:
                notify.dispatch(db, u, "status", f"{actor.name} moved {item.key} to {item.status}", item.key, actor)
            elif rest:
                notify.dispatch(db, u, "updated", f"{actor.name} updated {', '.join(rest)} on {item.key}", item.key, actor)
    return changed


def allocate_key(db: Session, space: Space, number: int | None = None) -> tuple[int, str]:
    if number is None or db.scalar(select(WorkItem.id).where(WorkItem.space_id == space.id, WorkItem.number == number)):
        space.seq = (space.seq or 0) + 1
        number = space.seq
        while db.scalar(select(WorkItem.id).where(WorkItem.space_id == space.id, WorkItem.number == number)):
            space.seq += 1
            number = space.seq
    else:
        space.seq = max(space.seq or 0, number)
    return number, f"{space.key}-{number}"


def create_item(db: Session, space: Space, actor: User, data: dict, notify_people=True) -> WorkItem:
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(422, "A work item needs a summary.")
    number, key = allocate_key(db, space, data.get("number"))
    top_rank = db.scalar(select(func.max(WorkItem.rank)).where(WorkItem.space_id == space.id)) or 0
    item = WorkItem(space_id=space.id, number=number, key=key, title=title[:300], status=space.statuses[0]["name"],
                    type="Task", priority="Medium", reporter_id=actor.id, labels=[], checklist=[],
                    rank=top_rank + 1, created_at=utcnow(), updated_at=utcnow(), external_key=data.get("external_key"))
    item.space = space
    db.add(item)
    db.flush()
    fields = {k: v for k, v in data.items() if k not in ("title", "number", "external_key")}
    apply_changes(db, space, item, actor, fields, notify_people=False)
    if category(space, item.status) == "done" and not item.resolved_at:
        item.resolved_at = utcnow()
    db.flush()
    # Initial values are not "changes": keep one "created" row whose value is the starting status (reports use it).
    for h in db.scalars(select(History).where(History.item_id == item.id)):
        db.delete(h)
    record(db, item, actor, "created", "", item.status)
    if notify_people:
        for u in item.assignees:
            notify.dispatch(db, u, "assigned", f"{actor.name} assigned you {item.key}: {item.title}", item.key, actor)
        members = member_ids(db, space)
        for u in mentioned_users(db, item.description):
            if u.id in members and u not in item.assignees:
                notify.dispatch(db, u, "mentioned", f"{actor.name} mentioned you in {item.key}: {item.title}",
                                item.key, actor)
    return item
