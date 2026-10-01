"""Agile reports computed from work item history, so every chart can be rebuilt from the audit trail."""
from datetime import date, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import History, Space, Sprint, WorkItem
from .services import category


def _timelines(db: Session, space: Space) -> dict[int, list[tuple[datetime, str]]]:
    rows = db.execute(select(History.item_id, History.at, History.new_value)
                      .where(History.space_id == space.id, History.field.in_(("created", "status")),
                             History.item_id.is_not(None))
                      .order_by(History.at, History.id)).all()
    out: dict[int, list[tuple[datetime, str]]] = {}
    for item_id, at, status in rows:
        out.setdefault(item_id, []).append((at, status))
    return out


def _status_at(timeline, moment: datetime):
    status = None
    for at, value in timeline:
        if at > moment:
            break
        status = value
    return status


def _days(start: date, end: date) -> list[date]:
    if end < start:
        return [start]
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def burndown(db: Session, space: Space, sprint: Sprint) -> dict:
    start = sprint.start_date or sprint.created_at.date()
    end = sprint.end_date or (start + timedelta(days=13))
    today = date.today()
    items = list(db.scalars(select(WorkItem).where(WorkItem.sprint_id == sprint.id)))
    timelines = _timelines(db, space)
    days = _days(start, end)
    remaining, completed, scope = [], [], []
    for d in days:
        if d > today:
            remaining.append(None)
            completed.append(None)
            scope.append(None)
            continue
        moment = datetime.combine(d, datetime.max.time())
        rem = comp = total = 0.0
        seen = 0
        for it in items:
            status = _status_at(timelines.get(it.id, []), moment)
            if status is None:
                continue
            seen += 1
            pts = it.points or 0
            total += pts
            if category(space, status) == "done":
                comp += pts
            else:
                rem += pts
        if not seen:  # no sprint work existed yet that day: leave a gap rather than a misleading zero
            remaining.append(None)
            completed.append(None)
            scope.append(None)
            continue
        remaining.append(rem)
        completed.append(comp)
        scope.append(total)
    total_now = sum(it.points or 0 for it in items)
    n = max(1, len(days) - 1)
    ideal = [round(total_now - total_now * i / n, 2) for i in range(len(days))]
    return {"sprint": sprint.name, "days": [d.isoformat() for d in days], "remaining": remaining,
            "completed": completed, "scope": scope, "ideal": ideal}


def velocity(db: Session, space: Space) -> dict:
    sprints = list(db.scalars(select(Sprint).where(Sprint.space_id == space.id, Sprint.state == "closed")
                              .order_by(Sprint.closed_at)))[-8:]
    rows = [{"name": s.name, "committed": s.committed_points or 0, "completed": s.completed_points or 0}
            for s in sprints]
    avg = round(sum(r["completed"] for r in rows) / len(rows), 1) if rows else 0
    return {"sprints": rows, "average": avg}


def cumulative_flow(db: Session, space: Space, days_back: int = 30) -> dict:
    today = date.today()
    days = _days(today - timedelta(days=days_back - 1), today)
    timelines = _timelines(db, space)
    names = [s["name"] for s in space.statuses]
    series = {n: [] for n in names}
    for d in days:
        moment = datetime.combine(d, datetime.max.time())
        tally = dict.fromkeys(names, 0)
        for tl in timelines.values():
            status = _status_at(tl, moment)
            if status in tally:
                tally[status] += 1
        for n in names:
            series[n].append(tally[n])
    return {"days": [d.isoformat() for d in days],
            "series": [{"status": n, "category": category(space, n), "values": series[n]} for n in names]}


def created_vs_resolved(db: Session, space: Space, days_back: int = 30) -> dict:
    today = date.today()
    days = _days(today - timedelta(days=days_back - 1), today)
    index = {d: i for i, d in enumerate(days)}
    created, resolved = [0] * len(days), [0] * len(days)
    for tl in _timelines(db, space).values():
        prev = None
        for n, (at, status) in enumerate(tl):
            d = at.date()
            if n == 0 and d in index:
                created[index[d]] += 1
            if category(space, status) == "done" and (prev is None or category(space, prev) != "done") and n > 0:
                if d in index:
                    resolved[index[d]] += 1
            prev = status
    return {"days": [d.isoformat() for d in days], "created": created, "resolved": resolved}


def cycle_time(db: Session, space: Space, days_back: int = 60) -> dict:
    since = datetime.combine(date.today() - timedelta(days=days_back), datetime.min.time())
    timelines = _timelines(db, space)
    points = []
    for it in db.scalars(select(WorkItem).where(WorkItem.space_id == space.id, WorkItem.resolved_at.is_not(None),
                                                WorkItem.resolved_at >= since)):
        started = next((at for at, st in timelines.get(it.id, []) if category(space, st) == "doing"), it.created_at)
        days = max(0.0, (it.resolved_at - started).total_seconds() / 86400)
        points.append({"key": it.key, "title": it.title, "resolved": it.resolved_at.isoformat(), "days": round(days, 2)})
    points.sort(key=lambda p: p["resolved"])
    values = [p["days"] for p in points]
    return {"points": points, "average": round(sum(values) / len(values), 2) if values else 0,
            "median": round(median(values), 2) if values else 0}
