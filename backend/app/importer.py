"""Bring work in from Jira (CSV export) and from OpenTrack exports or the browser prototype's backup."""
import csv
import io
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import utcnow
from .models import Comment, History, Link, Membership, Space, Sprint, User, WorkItem
from .services import allocate_key, category, create_item, record

DONE_RE = re.compile(r"done|closed|resolved|complete|released|shipped|cancel|won.?t|rejected", re.I)
DOING_RE = re.compile(r"progress|review|test|qa|develop|doing|block|verify|staging|deploy", re.I)
DATE_FORMATS = ("%d/%b/%y %I:%M %p", "%d/%b/%Y %I:%M %p", "%d/%b/%y %H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%d/%b/%y",
                "%Y-%m-%d", "%d/%m/%Y")
COLUMNS = {
    "key": ("issue key", "work item key", "key"),
    "id": ("issue id", "work item id"),
    "summary": ("summary",),
    "type": ("issue type", "work type", "type"),
    "status": ("status",),
    "priority": ("priority",),
    "assignee": ("assignee",),
    "reporter": ("reporter",),
    "created": ("created",),
    "updated": ("updated",),
    "resolved": ("resolved",),
    "due": ("due date", "due"),
    "description": ("description",),
    "labels": ("labels",),
    "sprint": ("sprint",),
    "points": ("custom field (story point estimate)", "custom field (story points)", "story points",
               "story point estimate"),
    "parent": ("parent", "parent id", "parent key", "custom field (epic link)"),
    "estimate": ("original estimate", "original estimate (seconds)"),
    "spent": ("time spent", "time spent (seconds)"),
    "comment": ("comment",),
}


def parse_when(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _map_type(t: str) -> str:
    t = (t or "").lower()
    if "epic" in t:
        return "Epic"
    if "sub" in t:
        return "Subtask"
    if "bug" in t or "defect" in t:
        return "Bug"
    if "story" in t or "feature" in t:
        return "Story"
    return "Task"


def _map_priority(p: str) -> str:
    p = (p or "").lower()
    if p in ("highest", "blocker", "critical", "urgent"):
        return "Highest"
    if p in ("high", "major"):
        return "High"
    if p in ("low", "lowest", "minor", "trivial"):
        return "Low"
    return "Medium"


def ensure_status(space: Space, name: str) -> None:
    if not name or any(s["name"].lower() == name.lower() for s in space.statuses):
        return
    cat = "done" if DONE_RE.search(name) else "doing" if DOING_RE.search(name) else "todo"
    statuses = [dict(s) for s in space.statuses]
    entry = {"name": name, "category": cat, "wip": 0}
    if cat == "done":
        statuses.append(entry)
    else:
        first_done = next((i for i, s in enumerate(statuses) if s.get("category") == "done"), len(statuses))
        statuses.insert(first_done, entry)
    space.statuses = statuses


def _status_name(space: Space, name: str) -> str:
    for s in space.statuses:
        if s["name"].lower() == (name or "").lower():
            return s["name"]
    return space.statuses[0]["name"]


class _People:
    def __init__(self, db: Session, space: Space):
        members = set(db.scalars(select(Membership.user_id).where(Membership.space_id == space.id)))
        self.by_name, self.missing = {}, set()
        for u in db.scalars(select(User)):
            if u.id in members:
                self.by_name[u.name.lower()] = u
                self.by_name[u.email.lower()] = u
                self.by_name[u.handle.lower()] = u

    def find(self, name: str):
        name = (name or "").strip()
        if not name:
            return None
        user = self.by_name.get(name.lower())
        if not user:
            self.missing.add(name)
        return user


def _backdate(db: Session, item: WorkItem, space: Space, created, updated, resolved, first_status: str):
    """Rewrite the starting history so reports see when work really began and finished."""
    created = created or utcnow()
    item.created_at = created
    item.updated_at = updated or created
    for h in db.scalars(select(History).where(History.item_id == item.id)):
        db.delete(h)
    record(db, item, None, "created", "", first_status)
    db.flush()
    db.scalars(select(History).where(History.item_id == item.id)).first().at = created
    if item.status != first_status:
        when = resolved if (resolved and category(space, item.status) == "done") else (updated or created)
        record(db, item, None, "status", first_status, item.status)
        db.flush()
        rows = list(db.scalars(select(History).where(History.item_id == item.id).order_by(History.id)))
        rows[-1].at = when
    item.resolved_at = (resolved or updated or created) if category(space, item.status) == "done" else None


def import_jira_csv(db: Session, space: Space, actor: User, raw: bytes) -> dict:
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {"created": 0, "warnings": ["The file is empty."]}
    header = [h.strip().lower() for h in rows[0]]
    cols = {name: [i for i, h in enumerate(header) if h in aliases] for name, aliases in COLUMNS.items()}
    if not cols["summary"]:
        return {"created": 0, "warnings": ["No Summary column found. Export from Jira with CSV (all fields)."]}

    def one(row, name):
        for i in cols[name]:
            if i < len(row) and row[i].strip():
                return row[i].strip()
        return ""

    def many(row, name):
        return [row[i].strip() for i in cols[name] if i < len(row) and row[i].strip()]

    people = _People(db, space)
    for row in rows[1:]:
        if row:
            ensure_status(space, one(row, "status"))
    todo_status = space.statuses[0]["name"]
    sprints: dict[str, Sprint] = {}
    created_items, by_ref, parents, warnings = [], {}, [], []
    for row in rows[1:]:
        if not row or not one(row, "summary"):
            continue
        ext_key = one(row, "key")
        number = None
        if ext_key and ext_key.split("-")[0].upper() == space.key and ext_key.split("-")[-1].isdigit():
            number = int(ext_key.split("-")[-1])
        assignee = people.find(one(row, "assignee"))
        reporter = people.find(one(row, "reporter"))
        points = one(row, "points")
        estimate = one(row, "estimate")
        due = parse_when(one(row, "due"))
        data = {
            "title": one(row, "summary"), "number": number, "external_key": ext_key or None,
            "type": _map_type(one(row, "type")), "priority": _map_priority(one(row, "priority")),
            "status": _status_name(space, one(row, "status")), "description": one(row, "description"),
            "labels": [lab for cell in many(row, "labels") for lab in cell.split()],
            "assignee_ids": [assignee.id] if assignee else [],
            "points": float(points) if re.fullmatch(r"\d+(\.\d+)?", points) else None,
            "estimate": round(float(estimate) / 3600, 2) if estimate.isdigit() else None,
            "due": due.date().isoformat() if due else None,
        }
        if reporter:
            data["reporter_id"] = reporter.id
        item = create_item(db, space, actor, data, notify_people=False)
        spent = one(row, "spent")
        if spent.isdigit():
            item.logged_hours = round(int(spent) / 3600, 2)
        _backdate(db, item, space, parse_when(one(row, "created")), parse_when(one(row, "updated")),
                  parse_when(one(row, "resolved")), todo_status)
        sprint_names = many(row, "sprint")
        if sprint_names:
            name = sprint_names[-1]
            if name not in sprints:
                sprints[name] = Sprint(space_id=space.id, name=name[:120], state="closed")
                db.add(sprints[name])
                db.flush()
            if category(space, item.status) != "done":
                sprints[name].state = "future"
            item.sprint_id = sprints[name].id
        for cell in many(row, "comment"):
            parts = cell.split(";", 2)
            when = parse_when(parts[0]) if len(parts) == 3 else None
            body = parts[2] if len(parts) == 3 else cell
            db.add(Comment(item_id=item.id, author_id=None, body=body, created_at=when or utcnow()))
        for ref in (one(row, "id"), ext_key):
            if ref:
                by_ref[ref] = item
        parent_ref = one(row, "parent")
        if parent_ref:
            parents.append((item, parent_ref))
        created_items.append(item)
    for item, ref in parents:
        parent = by_ref.get(ref)
        if parent and parent.id != item.id:
            item.parent = parent
            item.parent_id = parent.id
    # Items in unfinished sprints go to the backlog of those sprints; completed sprints keep their history.
    for s in sprints.values():
        if s.state == "closed":
            s.completed_points = sum(i.points or 0 for i in created_items if i.sprint_id == s.id)
            s.closed_at = utcnow()
    if people.missing:
        warnings.append("No member matched these names, so their work was left unassigned: "
                        + ", ".join(sorted(people.missing)[:20]) + ". Add them to the space and re-import if needed.")
    db.flush()
    return {"created": len(created_items), "sprints": len(sprints), "warnings": warnings}


def import_opentrack_json(db: Session, space: Space, actor: User, payload: dict) -> dict:
    """Accepts an OpenTrack export ({"format": "opentrack-export"}) or the browser prototype backup."""
    if payload.get("format") == "opentrack-export":
        issues = payload.get("items", [])
        statuses = payload.get("space", {}).get("statuses", [])
        sprint_meta = {s["id"]: s for s in payload.get("sprints", [])}
    elif "projects" in payload:
        project = payload["projects"].get(space.key) or next(iter(payload["projects"].values()), None)
        if not project:
            return {"created": 0, "warnings": ["That backup has no projects in it."]}
        statuses = [{"name": s["name"], "wip": s.get("wip", 0)} for s in project.get("statuses", [])]
        sprint = project.get("sprint") or {}
        sprint_meta = {"active": {"name": sprint.get("name", "Sprint 1"), "goal": sprint.get("goal", ""),
                                  "start": sprint.get("start"), "end": sprint.get("end"), "state": "active"}}
        issues = [{
            "key": i.get("id"), "title": i.get("title"), "type": i.get("type"), "priority": i.get("priority"),
            "status": i.get("status"), "assignees": [i.get("assignee")] if i.get("assignee") not in (None, "Unassigned") else [],
            "points": i.get("points"), "estimate": i.get("estimate"), "logged": i.get("logged"),
            "description": i.get("desc", ""), "labels": i.get("labels", []), "parent_key": i.get("parent"),
            "start": i.get("start"), "due": i.get("due"), "sprint_id": "active" if i.get("sprint") == "active" else None,
            "checklist": [{"text": c.get("t", ""), "done": c.get("d", False)} for c in i.get("checklist", [])],
            "comments": [{"author": c.get("by"), "body": c.get("text", ""), "at": c.get("at")} for c in i.get("comments", [])],
            "links": [l for l in i.get("links", []) if l.get("type") in ("blocks", "relates to", "duplicates")],
        } for i in project.get("issues", [])]
    else:
        return {"created": 0, "warnings": ["This file is not an OpenTrack export or prototype backup."]}

    for s in statuses:
        ensure_status(space, s.get("name", ""))
    people = _People(db, space)
    sprint_map = {}
    if any(i.get("sprint_id") for i in issues):
        has_active = db.scalar(select(Sprint.id).where(Sprint.space_id == space.id, Sprint.state == "active"))
        for ref, meta in sprint_meta.items():
            state = meta.get("state", "future")
            if state == "active" and has_active:
                state = "future"
            s = Sprint(space_id=space.id, name=meta.get("name", "Imported sprint")[:120], goal=meta.get("goal", ""),
                       start_date=date.fromisoformat(meta["start"]) if meta.get("start") else None,
                       end_date=date.fromisoformat(meta["end"]) if meta.get("end") else None, state=state)
            db.add(s)
            db.flush()
            sprint_map[ref] = s
    by_old, created = {}, []
    for i in issues:
        if not i.get("title"):
            continue
        assignees = [u.id for u in (people.find(n) for n in i.get("assignees", [])) if u]
        data = {"title": i["title"], "type": i.get("type") if i.get("type") in ("Epic", "Story", "Task", "Bug", "Subtask") else "Task",
                "priority": i.get("priority") if i.get("priority") in ("Highest", "High", "Medium", "Low") else "Medium",
                "status": _status_name(space, i.get("status", "")), "assignee_ids": assignees,
                "points": i.get("points") or None, "estimate": i.get("estimate") or None,
                "description": i.get("description", ""), "labels": i.get("labels", []), "start": i.get("start") or None,
                "due": i.get("due") or None, "checklist": i.get("checklist", []), "external_key": i.get("key")}
        item = create_item(db, space, actor, data, notify_people=False)
        item.logged_hours = float(i.get("logged") or 0)
        sprint = sprint_map.get(i.get("sprint_id"))
        if sprint:
            item.sprint_id = sprint.id
        for c in i.get("comments", []):
            at = c.get("at")
            when = datetime.fromtimestamp(at / 1000) if isinstance(at, (int, float)) else parse_when(str(at or ""))
            author = people.find(c.get("author") or "") if c.get("author") not in (None, "You") else actor
            db.add(Comment(item_id=item.id, author_id=author.id if author else None, body=c.get("body", ""),
                           created_at=when or utcnow()))
        by_old[i.get("key")] = (item, i)
        created.append(item)
    for item, i in by_old.values():
        parent = by_old.get(i.get("parent_key"), (None, None))[0]
        if parent:
            item.parent = parent
            item.parent_id = parent.id
        for l in i.get("links", []):
            target = by_old.get(l.get("target") or l.get("target_key"), (None, None))[0]
            if target:
                db.add(Link(source_id=item.id, target_id=target.id, type=l["type"]))
    warnings = []
    if people.missing:
        warnings.append("No member matched these names, so their work was left unassigned: "
                        + ", ".join(sorted(people.missing)[:20]) + ".")
    db.flush()
    return {"created": len(created), "sprints": len(sprint_map), "warnings": warnings}
