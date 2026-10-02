"""Reports, notifications, and import/export."""
import csv
import io
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import importer, reports
from ..db import get_db, utcnow
from ..models import (Comment, History, Link, Membership, Notification, Space, Sprint, User, WorkItem,
                      Worklog, item_assignees, item_watchers)
from ..security import current_user, current_user_or_query_token, get_space
from ..services import blocked_keys, category, item_to_dict, space_to_dict, sprint_to_dict

router = APIRouter(prefix="/api", tags=["reports and data"])


@router.get("/catch-up")
def catch_up(days: int = 7, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """What changed, on your work, while you were away.

    Jira can tell you everything that happened and it can tell you one notification at a time.
    Neither answers the question people actually ask on a Monday, which is what moved on my work,
    what is newly stuck, and what needs me now. This answers that in one request.
    """
    days = max(1, min(days, 90))
    since = utcnow() - timedelta(days=days)

    space_ids = [m.space_id for m in db.scalars(select(Membership).where(Membership.user_id == user.id))]
    if user.is_admin:
        space_ids = list(db.scalars(select(Space.id)))
    if not space_ids:
        return {"since": since.isoformat(), "days": days, "nothing": True}

    # Work you are involved in: assigned, watching, or you raised it.
    involved_ids = set(db.scalars(select(item_assignees.c.item_id)
                                  .where(item_assignees.c.user_id == user.id)))
    involved_ids |= set(db.scalars(select(item_watchers.c.item_id)
                                   .where(item_watchers.c.user_id == user.id)))
    involved_ids |= set(db.scalars(select(WorkItem.id).where(WorkItem.reporter_id == user.id,
                                                             WorkItem.space_id.in_(space_ids))))
    items = {i.id: i for i in db.scalars(select(WorkItem).where(WorkItem.id.in_(involved_ids)))} if involved_ids else {}

    rows = db.scalars(select(History).where(History.item_id.in_(involved_ids or [-1]),
                                            History.at > since,
                                            History.actor_id != user.id)
                      .order_by(History.at.desc())) if involved_ids else []

    def brief(item, extra=None):
        d = {"key": item.key, "title": item.title, "status": item.status, "type": item.type}
        if extra:
            d.update(extra)
        return d

    moved, assigned, commented, seen = [], [], [], set()
    for h in rows:
        item = items.get(h.item_id)
        if not item:
            continue
        actor = db.get(User, h.actor_id).name if h.actor_id else "Someone"
        if h.field == "status" and (item.id, "status") not in seen:
            seen.add((item.id, "status"))
            moved.append(brief(item, {"from": h.old_value, "to": h.new_value,
                                      "by": actor, "at": h.at.isoformat()}))
        # apply_changes records this as "assignees" and stores display names, not handles.
        elif h.field == "assignees" and user.name in (h.new_value or "") \
                and user.name not in (h.old_value or "") and (item.id, "a") not in seen:
            seen.add((item.id, "a"))
            assigned.append(brief(item, {"by": actor, "at": h.at.isoformat()}))
        elif h.field == "comment" and (item.id, "c") not in seen:
            seen.add((item.id, "c"))
            commented.append(brief(item, {"by": actor, "at": h.at.isoformat(),
                                          "preview": (h.new_value or "")[:140]}))

    # State you should know about now, regardless of when it changed.
    spaces = {s.id: s for s in db.scalars(select(Space).where(Space.id.in_(space_ids)))}
    blocked_now = blocked_keys(db, list(spaces.values()))
    today = utcnow().date()
    blocked, overdue = [], []
    for item in items.values():
        sp = spaces.get(item.space_id)
        if not sp or category(sp, item.status) == "done":
            continue
        if item.key in blocked_now:
            blocked.append(brief(item))
        if item.due_date and item.due_date < today:
            overdue.append(brief(item, {"due": item.due_date.isoformat()}))

    total = len(moved) + len(assigned) + len(commented) + len(blocked) + len(overdue)
    return {"since": since.isoformat(), "days": days, "total": total, "nothing": total == 0,
            "assigned": assigned, "moved": moved, "commented": commented,
            "blocked": blocked, "overdue": overdue}


class ReadIn(BaseModel):
    ids: list[int] = []
    all: bool = False


@router.get("/spaces/{key}/reports/{name}")
def report(key: str, name: str, sprint_id: int | None = None, days: int = 30, user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    days = max(7, min(days, 180))
    if name == "burndown":
        sprint = db.get(Sprint, sprint_id) if sprint_id else db.scalar(
            select(Sprint).where(Sprint.space_id == space.id, Sprint.state == "active"))
        if not sprint or sprint.space_id != space.id:
            return {"sprint": None}
        return reports.burndown(db, space, sprint)
    if name == "velocity":
        return reports.velocity(db, space)
    if name == "cfd":
        return reports.cumulative_flow(db, space, days)
    if name == "created-vs-resolved":
        return reports.created_vs_resolved(db, space, days)
    if name == "cycle-time":
        return reports.cycle_time(db, space, days)
    raise HTTPException(404, "Unknown report. Try burndown, velocity, cfd, created-vs-resolved or cycle-time.")


@router.get("/notifications")
def list_notifications(limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)):
    names = {u.id: u.name for u in db.scalars(select(User))}
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.in_app.is_(True))
                      .order_by(Notification.created_at.desc()).limit(min(limit, 200)))
    unread = db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id, Notification.in_app.is_(True), Notification.is_read.is_(False)))
    return {"unread": unread, "items": [{"id": n.id, "event": n.event, "text": n.text, "key": n.item_key,
                                         "actor": names.get(n.actor_id, ""), "read": n.is_read,
                                         "at": n.created_at.isoformat()} for n in rows]}


@router.post("/notifications/read")
def mark_read(body: ReadIn = ReadIn(), user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    stmt = update(Notification).where(Notification.user_id == user.id)
    if not body.all:
        stmt = stmt.where(Notification.id.in_(body.ids or [-1]))
    db.execute(stmt.values(is_read=True))
    db.commit()
    return {"ok": True}


@router.get("/spaces/{key}/export")
def export_json(key: str, user: User = Depends(current_user_or_query_token), db: Session = Depends(get_db)):
    space, role = get_space(db, key, user)
    items = list(db.scalars(select(WorkItem).where(WorkItem.space_id == space.id).order_by(WorkItem.number)))
    ids = {i.id: i.key for i in items}
    names = {u.id: u.name for u in db.scalars(select(User))}
    comments, logs, links = {}, {}, {}
    for c in db.scalars(select(Comment).where(Comment.item_id.in_(list(ids)))):
        comments.setdefault(c.item_id, []).append({"author": names.get(c.author_id), "body": c.body,
                                                   "at": c.created_at.isoformat()})
    for w in db.scalars(select(Worklog).where(Worklog.item_id.in_(list(ids)))):
        logs.setdefault(w.item_id, []).append({"user": names.get(w.user_id), "hours": w.hours, "day": w.day.isoformat(),
                                               "note": w.note})
    for l in db.scalars(select(Link).where(Link.source_id.in_(list(ids)))):
        if l.target_id in ids:
            links.setdefault(l.source_id, []).append({"type": l.type, "target": ids[l.target_id]})
    out_items = []
    for i in items:
        d = item_to_dict(i)
        d["assignees"] = [names.get(u) for u in d["assignee_ids"]]
        d.update(comments=comments.get(i.id, []), worklogs=logs.get(i.id, []), links=links.get(i.id, []))
        out_items.append(d)
    members = db.execute(select(User.email, Membership.role).join(Membership, Membership.user_id == User.id)
                         .where(Membership.space_id == space.id)).all()
    payload = {"format": "freehold-export", "version": 1, "space": space_to_dict(space),
               "members": [{"email": e, "role": r} for e, r in members],
               "sprints": [sprint_to_dict(s) for s in db.scalars(select(Sprint).where(Sprint.space_id == space.id))],
               "items": out_items}
    return Response(json.dumps(payload, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{space.key}-export.json"'})


@router.get("/spaces/{key}/export.csv")
def export_csv(key: str, user: User = Depends(current_user_or_query_token), db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user)
    names = {u.id: u.name for u in db.scalars(select(User))}
    sprints = {s.id: s.name for s in db.scalars(select(Sprint).where(Sprint.space_id == space.id))}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Key", "Summary", "Type", "Status", "Priority", "Assignees", "Reporter", "Sprint", "Points",
                "Estimate (h)", "Logged (h)", "Labels", "Parent", "Start", "Due", "Created", "Updated", "Resolved"])
    for i in db.scalars(select(WorkItem).where(WorkItem.space_id == space.id).order_by(WorkItem.number)):
        d = item_to_dict(i)
        w.writerow([d["key"], d["title"], d["type"], d["status"], d["priority"],
                    "; ".join(names.get(u, "") for u in d["assignee_ids"]), names.get(d["reporter_id"], ""),
                    sprints.get(d["sprint_id"], "Backlog"), d["points"] or "", d["estimate"] or "", d["logged"],
                    "; ".join(d["labels"]), d["parent_key"] or "", d["start"] or "", d["due"] or "",
                    d["created_at"], d["updated_at"], d["resolved_at"] or ""])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{space.key}-work-items.csv"'})


@router.post("/spaces/{key}/import/jira")
async def import_jira(key: str, file: UploadFile = File(...), user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    raw = await file.read()
    try:
        summary = importer.import_jira_csv(db, space, user, raw)
    except Exception as e:  # noqa: BLE001 - report import problems instead of a 500
        db.rollback()
        raise HTTPException(422, f"The file could not be imported: {e}")
    db.commit()
    return summary


@router.post("/spaces/{key}/import/freehold")
async def import_freehold(key: str, file: UploadFile = File(...), user: User = Depends(current_user),
                           db: Session = Depends(get_db)):
    space, _ = get_space(db, key, user, need="admin")
    try:
        payload = json.loads((await file.read()).decode("utf-8-sig"))
        summary = importer.import_freehold_json(db, space, user, payload)
    except json.JSONDecodeError:
        raise HTTPException(422, "That file is not valid JSON.")
    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(422, f"The file could not be imported: {e}")
    db.commit()
    return summary
