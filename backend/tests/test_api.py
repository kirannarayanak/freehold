"""End-to-end API tests: run with `pytest` from the backend folder (SQLite) or with DATABASE_URL set to PostgreSQL."""
import io
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def world(client):
    assert client.get("/api/auth/status").json()["needs_setup"] is True
    r = client.post("/api/auth/register", json={"name": "Kiran Narayana", "email": "kiran@example.com", "password": "correct-horse"})
    assert r.status_code == 200, r.text
    admin = r.json()
    assert admin["user"]["is_admin"] is True and admin["user"]["handle"] == "kiran.narayana"
    r = client.post("/api/auth/register", json={"name": "Eve", "email": "eve@example.com", "password": "12345678"})
    assert r.status_code == 403
    A = auth(admin["token"])
    for name, email in (("Bob Stone", "bob@example.com"), ("Carol Diaz", "carol@example.com")):
        assert client.post("/api/users", json={"name": name, "email": email, "password": "password1"}, headers=A).status_code == 200
    bob = client.post("/api/auth/login", json={"email": "BOB@example.com", "password": "password1"}).json()
    carol = client.post("/api/auth/login", json={"email": "carol@example.com", "password": "password1"}).json()
    assert client.post("/api/auth/login", json={"email": "bob@example.com", "password": "nope"}).status_code == 401
    r = client.post("/api/spaces", json={"key": "web", "name": "Website relaunch"}, headers=A)
    assert r.status_code == 200 and r.json()["key"] == "WEB"
    return {"A": A, "B": auth(bob["token"]), "C": auth(carol["token"]), "bob": bob["user"], "carol": carol["user"],
            "admin": admin["user"]}


def test_membership_and_permissions(client, world):
    A, B, C = world["A"], world["B"], world["C"]
    assert client.get("/api/spaces/WEB", headers=B).status_code == 404
    r = client.post("/api/spaces/WEB/members", json={"email": "bob@example.com", "role": "member"}, headers=A)
    assert r.status_code == 200
    client.post("/api/spaces/WEB/members", json={"email": "carol@example.com", "role": "viewer"}, headers=A)
    bundle = client.get("/api/spaces/WEB", headers=B).json()
    assert bundle["space"]["role"] == "member" and len(bundle["members"]) == 3
    assert [s["name"] for s in bundle["sprints"]] == ["Sprint 1"]
    assert client.post("/api/spaces/WEB/items", json={"title": "nope"}, headers=C).status_code == 403
    assert client.patch("/api/spaces/WEB", json={"name": "x"}, headers=B).status_code == 403
    admin_id = world["admin"]["id"]
    r = client.patch(f"/api/spaces/WEB/members/{admin_id}", json={"role": "member"}, headers=A)
    assert r.status_code == 422  # last admin


def test_items_history_and_notifications(client, world):
    A, B, C, bob = world["A"], world["B"], world["C"], world["bob"]
    r = client.post("/api/spaces/WEB/items", headers=A, json={
        "title": "Payment gateway integration", "type": "Task", "priority": "Highest", "assignee_ids": [bob["id"]],
        "labels": ["payments", " backend ", "payments"], "points": 8, "description": "Wire up **Stripe**. cc @carol.diaz"})
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["key"] == "WEB-1" and item["labels"] == ["payments", "backend"] and item["assignee_ids"] == [bob["id"]]
    notes = client.get("/api/notifications", headers=B).json()
    assert notes["unread"] == 1 and notes["items"][0]["event"] == "assigned"
    assert client.get("/api/notifications", headers=C).json()["items"][0]["event"] == "mentioned"
    assert client.patch("/api/items/WEB-1", json={"status": "In progress"}, headers=C).status_code == 403
    r = client.patch("/api/items/WEB-1", json={"status": "In progress", "due": "2026-10-04"}, headers=B)
    assert r.status_code == 200 and r.json()["status"] == "In progress"
    assert client.patch("/api/items/WEB-1", json={"status": "Nope"}, headers=B).status_code == 422
    admin_notes = client.get("/api/notifications", headers=A).json()
    assert admin_notes["items"][0]["event"] == "status"
    detail = client.get("/api/items/WEB-1", headers=B).json()
    fields = [h["field"] for h in detail["history"]]
    assert "created" in fields and "status" in fields and "due" in fields
    # Bob turns off in-app comment notifications; a plain comment should not reach him, a mention should.
    prefs = client.get("/api/me", headers=B).json()["prefs"]
    prefs["events"]["commented"] = {"inapp": False, "email": False}
    client.patch("/api/me", json={"prefs": prefs}, headers=B)
    before = client.get("/api/notifications", headers=B).json()["unread"]
    client.post("/api/items/WEB-1/comments", json={"body": "Looks good"}, headers=A)
    assert client.get("/api/notifications", headers=B).json()["unread"] == before
    client.post("/api/items/WEB-1/comments", json={"body": "@bob.stone can you check the webhook?"}, headers=A)
    after = client.get("/api/notifications", headers=B).json()
    assert after["unread"] == before + 1 and after["items"][0]["event"] == "mentioned"
    client.post("/api/notifications/read", json={"all": True}, headers=B)
    assert client.get("/api/notifications", headers=B).json()["unread"] == 0
    # Muting an item silences it.
    client.post("/api/items/WEB-1/mute", json={"on": True}, headers=B)
    client.post("/api/items/WEB-1/comments", json={"body": "@bob.stone ping"}, headers=A)
    assert client.get("/api/notifications", headers=B).json()["unread"] == 0


def test_links_search_worklog_attachments(client, world):
    A, B = world["A"], world["B"]
    r = client.post("/api/spaces/WEB/items", json={"title": "Order confirmation email", "points": 3}, headers=B)
    assert r.json()["key"] == "WEB-2"
    r = client.post("/api/items/WEB-1/links", json={"type": "blocks", "target_key": "WEB-2"}, headers=B)
    assert r.status_code == 200 and r.json()["links"][0]["label"] == "blocks"
    other = client.get("/api/items/WEB-2", headers=B).json()
    assert other["links"][0]["label"] == "blocked by"
    s = client.get("/api/search", params={"q": "is:blocked"}, headers=B).json()
    assert [i["key"] for i in s["items"]] == ["WEB-2"]
    s = client.get("/api/search", params={"q": 'assignee = bob.stone AND status = "in progress" ORDER BY key'}, headers=B).json()
    assert [i["key"] for i in s["items"]] == ["WEB-1"]
    assert client.get("/api/search", params={"q": "status in (Done"}, headers=B).status_code == 400
    r = client.post("/api/items/WEB-1/worklogs", json={"hours": 2.5, "note": "webhooks"}, headers=B)
    assert r.json()["item"]["logged"] == 2.5
    assert client.post("/api/items/WEB-1/worklogs", json={"hours": 30}, headers=B).status_code == 422
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/api/items/WEB-1/attachments", files=files, headers=B)
    att = r.json()["attachments"][0]
    assert att["filename"] == "notes.txt" and att["size"] == 5
    token = B["Authorization"][7:]
    d = client.get(f"/api/attachments/{att['id']}", params={"token": token})
    assert d.status_code == 200 and d.content == b"hello" and "attachment" in d.headers["content-disposition"]
    assert client.get(f"/api/attachments/{att['id']}").status_code == 401
    r = client.delete(f"/api/attachments/{att['id']}", headers=B)
    assert r.json()["attachments"] == []


def test_sprints_and_reports(client, world):
    A, B = world["A"], world["B"]
    bundle = client.get("/api/spaces/WEB", headers=B).json()
    sprint_id = bundle["sprints"][0]["id"]
    for key in ("WEB-1", "WEB-2"):
        assert client.patch(f"/api/items/{key}", json={"sprint_id": sprint_id}, headers=B).status_code == 200
    start = (datetime.now() - timedelta(days=3)).date().isoformat()
    r = client.patch(f"/api/sprints/{sprint_id}", json={"state": "active", "start": start, "goal": "Ship checkout"}, headers=B)
    assert r.json()["state"] == "active" and r.json()["committed_points"] == 11
    other = client.post("/api/spaces/WEB/sprints", json={}, headers=B).json()
    assert client.patch(f"/api/sprints/{other['id']}", json={"state": "active"}, headers=B).status_code == 422
    client.patch("/api/items/WEB-2", json={"status": "Done"}, headers=B)
    item = client.get("/api/items/WEB-2", headers=B).json()["item"]
    assert item["resolved_at"] is not None
    bd = client.get("/api/spaces/WEB/reports/burndown", headers=B).json()
    assert bd["sprint"] == "Sprint 1" and len(bd["days"]) == 14
    today_index = 3
    assert bd["remaining"][today_index] == 8 and bd["completed"][today_index] == 3
    cfd = client.get("/api/spaces/WEB/reports/cfd", params={"days": 7}, headers=B).json()
    assert [s["status"] for s in cfd["series"]][-1] == "Done" and cfd["series"][-1]["values"][-1] == 1
    cvr = client.get("/api/spaces/WEB/reports/created-vs-resolved", params={"days": 7}, headers=B).json()
    assert sum(cvr["created"]) == 2 and sum(cvr["resolved"]) == 1
    ct = client.get("/api/spaces/WEB/reports/cycle-time", headers=B).json()
    assert ct["points"][0]["key"] == "WEB-2"
    r = client.post(f"/api/sprints/{sprint_id}/complete", json={"move_to": other["id"]}, headers=B)
    assert r.json()["moved"] == 1 and r.json()["completed"] == 1
    v = client.get("/api/spaces/WEB/reports/velocity", headers=B).json()
    assert v["sprints"][0]["completed"] == 3 and v["sprints"][0]["committed"] == 11
    assert client.get("/api/items/WEB-1", headers=B).json()["item"]["sprint_id"] == other["id"]


def test_changes_bulk_clone_delete(client, world):
    A, B = world["A"], world["B"]
    since = client.get("/api/spaces/WEB", headers=B).json()["server_time"]
    r = client.post("/api/items/bulk", json={"keys": ["WEB-1", "WEB-2"], "set": {"priority": "Low"}}, headers=B)
    assert {i["priority"] for i in r.json()["updated"]} == {"Low"}
    copy = client.post("/api/items/WEB-2/clone", headers=B).json()
    assert copy["title"].startswith("Copy of")
    client.delete(f"/api/items/{copy['key']}", headers=B)
    ch = client.get("/api/spaces/WEB/changes", params={"since": since}, headers=B).json()
    assert {"WEB-1", "WEB-2"} <= {i["key"] for i in ch["items"]} and copy["key"] in ch["deleted"]


def test_workflow_change_remaps_status(client, world):
    A, B = world["A"], world["B"]
    statuses = [{"name": "Backlog", "category": "todo"}, {"name": "Doing", "category": "doing", "wip": 3},
                {"name": "Shipped", "category": "done"}]
    r = client.patch("/api/spaces/WEB", json={"statuses": statuses, "status_map": {"Done": "Shipped", "In progress": "Doing"}}, headers=A)
    assert r.status_code == 200 and [s["name"] for s in r.json()["statuses"]] == ["Backlog", "Doing", "Shipped"]
    items = {i["key"]: i["status"] for i in client.get("/api/spaces/WEB", headers=B).json()["items"]}
    assert items["WEB-2"] == "Shipped" and items["WEB-1"] == "Doing"
    bad = client.patch("/api/spaces/WEB", json={"statuses": [{"name": "A"}, {"name": "B"}]}, headers=A)
    assert bad.status_code == 422


JIRA_CSV = """Summary,Issue key,Issue id,Issue Type,Status,Priority,Assignee,Reporter,Created,Updated,Resolved,Due date,Labels,Labels,Sprint,Sprint,Custom field (Story point estimate),Parent,Description,Comment,Original estimate,Time Spent
Checkout epic,SHOP-1,10001,Epic,In Progress,High,Bob Stone,Kiran Narayana,01/Sep/26 9:00 AM,20/Sep/26 5:00 PM,,,,,,,,,The big one,,,
Card form,SHOP-2,10002,Story,Closed,Major,Bob Stone,Kiran Narayana,02/Sep/26 9:00 AM,10/Sep/26 5:00 PM,10/Sep/26 5:00 PM,15/Sep/26 12:00 AM,ui,payments,SHOP Sprint 1,SHOP Sprint 2,5,10001,Build it,"05/Sep/26 10:00 AM;abc123;Looks good",14400,7200
Refund flow,SHOP-3,10003,Bug,QA,Blocker,Someone Else,Kiran Narayana,03/Sep/26 9:00 AM,21/Sep/26 5:00 PM,,,,,,SHOP Sprint 2,3,10001,,,,
"""


def test_jira_import(client, world):
    A = world["A"]
    client.post("/api/spaces", json={"key": "SHOP", "name": "Shop", "template": "kanban"}, headers=A)
    client.post("/api/spaces/SHOP/members", json={"email": "bob@example.com"}, headers=A)
    files = {"file": ("jira.csv", io.BytesIO(JIRA_CSV.encode()), "text/csv")}
    r = client.post("/api/spaces/SHOP/import/jira", files=files, headers=A)
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["created"] == 3 and "Someone Else" in summary["warnings"][0]
    b = client.get("/api/spaces/SHOP", headers=A).json()
    items = {i["key"]: i for i in b["items"]}
    assert set(items) == {"SHOP-1", "SHOP-2", "SHOP-3"}
    assert items["SHOP-2"]["parent_key"] == "SHOP-1" and items["SHOP-2"]["labels"] == ["ui", "payments"]
    assert items["SHOP-2"]["status"] == "Closed" and items["SHOP-2"]["resolved_at"].startswith("2026-09-10")
    assert items["SHOP-2"]["estimate"] == 4 and items["SHOP-2"]["logged"] == 2 and items["SHOP-2"]["points"] == 5
    assert items["SHOP-3"]["priority"] == "Highest" and items["SHOP-3"]["assignee_ids"] == []
    cats = {s["name"]: s["category"] for s in b["space"]["statuses"]}
    assert cats["QA"] == "doing" and cats["Closed"] == "done" and cats["In progress"] == "doing" and "In Progress" not in cats
    assert {s["name"] for s in b["sprints"]} == {"SHOP Sprint 2"}
    detail = client.get("/api/items/SHOP-2", headers=A).json()
    assert detail["comments"][0]["body"] == "Looks good"
    # Exactly one "created" row, dated when the work really started. A second row dated at import
    # time would be the newest status event, so every history-based report would read imported
    # items back as their starting status: a closed item would show as open from the import day on.
    for key in ("SHOP-1", "SHOP-2", "SHOP-3"):
        hist = client.get(f"/api/items/{key}", headers=A).json()["history"]
        starts = [h for h in hist if h["field"] == "created"]
        assert len(starts) == 1, f"{key} has {len(starts)} created rows"
        assert starts[0]["at"].startswith("2026-09-0"), starts[0]["at"]
        timeline = sorted((h for h in hist if h["field"] in ("created", "status")), key=lambda h: h["at"])
        assert timeline[0]["field"] == "created"
        assert timeline[-1]["new"] == items[key]["status"], f"{key} history ends on the wrong status"


def test_prototype_and_export_roundtrip(client, world):
    A = world["A"]
    backup = {"current": "WEB", "projects": {"WEB": {"name": "Website", "statuses": [{"name": "To do"}, {"name": "Doing"}, {"name": "Done"}],
              "sprint": {"name": "Sprint 12", "goal": "Ship", "start": "2026-09-23", "end": "2026-10-07"},
              "issues": [
                  {"id": "WEB-1", "title": "Epic one", "type": "Epic", "priority": "High", "status": "Doing", "assignee": "Bob Stone", "sprint": "backlog"},
                  {"id": "WEB-2", "title": "Child", "type": "Story", "priority": "Medium", "status": "To do", "assignee": "Unassigned",
                   "sprint": "active", "parent": "WEB-1", "points": 5, "links": [{"type": "blocks", "target": "WEB-3"}],
                   "checklist": [{"t": "a", "d": True}], "comments": [{"by": "You", "text": "hi", "at": 1759000000000}]},
                  {"id": "WEB-3", "title": "Blocked", "type": "Bug", "priority": "Low", "status": "Done", "sprint": "active",
                   "links": [{"type": "blocked by", "target": "WEB-2"}]}]}}}
    client.post("/api/spaces", json={"key": "PROTO", "name": "From prototype"}, headers=A)
    client.post("/api/spaces/PROTO/members", json={"email": "bob@example.com"}, headers=A)
    files = {"file": ("backup.json", io.BytesIO(json.dumps(backup).encode()), "application/json")}
    r = client.post("/api/spaces/PROTO/import/freehold", files=files, headers=A)
    assert r.status_code == 200 and r.json()["created"] == 3, r.text
    b = client.get("/api/spaces/PROTO", headers=A).json()
    items = {i["title"]: i for i in b["items"]}
    assert items["Child"]["parent_key"] == items["Epic one"]["key"] and items["Child"]["checklist"][0]["done"] is True
    assert len(b["links"]) == 1 and items["Epic one"]["assignee_ids"] == [world["bob"]["id"]]
    assert any(s["name"] == "Sprint 12" for s in b["sprints"])
    exported = client.get("/api/spaces/PROTO/export", headers=A).json()
    assert exported["format"] == "freehold-export" and len(exported["items"]) == 3
    client.post("/api/spaces", json={"key": "COPY", "name": "Copy"}, headers=A)
    files = {"file": ("export.json", io.BytesIO(json.dumps(exported).encode()), "application/json")}
    r = client.post("/api/spaces/COPY/import/freehold", files=files, headers=A)
    assert r.json()["created"] == 3
    csv_text = client.get("/api/spaces/COPY/export.csv", headers=A).text
    assert csv_text.startswith("Key,Summary") and "COPY-1" in csv_text


def test_login_rate_limit(client, world):
    from app import security
    security._failures.clear()
    try:
        for _ in range(security.LOGIN_MAX_FAILURES):
            assert client.post("/api/auth/login",
                               json={"email": "bob@example.com", "password": "wrong"}).status_code == 401
        # Further attempts are refused before the password is even checked, and the right password
        # does not get through either: otherwise the limit would only slow down wrong guesses.
        r = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong"})
        assert r.status_code == 429 and "Retry-After" in r.headers
        assert client.post("/api/auth/login",
                           json={"email": "bob@example.com", "password": "password1"}).status_code == 429
        # A different account from the same client is still limited by the per-address counter,
        # so spraying many accounts is covered too.
        assert client.post("/api/auth/login",
                           json={"email": "carol@example.com", "password": "password1"}).status_code == 429
    finally:
        security._failures.clear()
    assert client.post("/api/auth/login",
                       json={"email": "bob@example.com", "password": "password1"}).status_code == 200


def test_items_nest_arbitrarily_deep(client, world):
    """Jira cannot do this: JRA-4446 has over a thousand votes and is still open."""
    A = world["A"]
    parent_key, chain = None, []
    for i in range(5):
        body = {"title": f"depth {i}", "type": "Epic" if i == 0 else "Subtask"}
        if parent_key:
            body["parent_key"] = parent_key
        r = client.post("/api/spaces/WEB/items", json=body, headers=A)
        assert r.status_code == 200, r.text
        parent_key = r.json()["key"]
        chain.append(parent_key)
    # Five levels, and each one really points at the one above it.
    for child, parent in zip(chain[1:], chain):
        assert client.get(f"/api/items/{child}", headers=A).json()["item"]["parent_key"] == parent
    # Depth is free; cycles are not.
    r = client.patch(f"/api/items/{chain[0]}", json={"parent_key": chain[-1]}, headers=A)
    assert r.status_code == 422 and "loop" in r.json()["detail"]


def test_versions_and_releases(client, world):
    A, B = world["A"], world["B"]
    r = client.post("/api/spaces/WEB/versions", json={"name": "1.0", "release_date": "2026-11-01"}, headers=A)
    assert r.status_code == 200, r.text
    v1 = r.json()
    assert v1["name"] == "1.0" and v1["released"] is False and v1["release_date"] == "2026-11-01"
    # Names are unique inside a space.
    assert client.post("/api/spaces/WEB/versions", json={"name": "1.0"}, headers=A).status_code == 409

    item = client.post("/api/spaces/WEB/items", json={"title": "Ship it"}, headers=A).json()
    item = client.patch(f"/api/items/{item['key']}", json={"version_id": v1["id"]}, headers=A).json()
    assert item["version_id"] == v1["id"]
    # A later change is in history under a readable name, not an id, so the trail survives a rename.
    # (Values set at creation are folded into the single "created" row by design.)
    hist = client.get(f"/api/items/{item['key']}", headers=A).json()["history"]
    assert any(h["field"] == "version" and h["new"] == "1.0" for h in hist)

    # The bundle carries versions, so the browser can render them without another request.
    bundle = client.get("/api/spaces/WEB", headers=A).json()
    assert [v["name"] for v in bundle["versions"]] == ["1.0"]

    # A version cannot be released while work in it is unfinished.
    r = client.patch(f"/api/versions/{v1['id']}", json={"released": True}, headers=A)
    assert r.status_code == 422 and "not finished" in r.json()["detail"]

    done = [st["name"] for st in bundle["space"]["statuses"] if st["category"] == "done"][0]
    client.patch(f"/api/items/{item['key']}", json={"status": done}, headers=A)
    assert client.patch(f"/api/versions/{v1['id']}", json={"released": True}, headers=A).json()["released"] is True

    # Archived versions stop accepting new work.
    v2 = client.post("/api/spaces/WEB/versions", json={"name": "1.1"}, headers=A).json()
    client.patch(f"/api/versions/{v2['id']}", json={"archived": True}, headers=A)
    r = client.patch(f"/api/items/{item['key']}", json={"version_id": v2["id"]}, headers=A)
    assert r.status_code == 422 and "archived" in r.json()["detail"]

    # Only admins delete, and deleting a version never deletes the work in it.
    assert client.delete(f"/api/versions/{v2['id']}", headers=B).status_code == 403
    assert client.delete(f"/api/versions/{v1['id']}", headers=A).status_code == 200
    after = client.get(f"/api/items/{item['key']}", headers=A).json()["item"]
    assert after["version_id"] is None and after["title"] == "Ship it"


def test_profile_admin_and_delete(client, world):
    A, B = world["A"], world["B"]
    assert client.patch("/api/me", json={"current_password": "wrong", "new_password": "newpassword"}, headers=B).status_code == 403
    assert client.patch("/api/me", json={"current_password": "password1", "new_password": "newpassword"}, headers=B).status_code == 200
    assert client.post("/api/auth/login", json={"email": "bob@example.com", "password": "newpassword"}).status_code == 200
    assert client.post("/api/users", json={"name": "X", "email": "x@example.com", "password": "password1"}, headers=B).status_code == 403
    carol_id = world["carol"]["id"]
    client.patch(f"/api/users/{carol_id}", json={"is_active": False}, headers=A)
    assert client.get("/api/me", headers=world["C"]).status_code == 401
    assert client.delete("/api/spaces/COPY", headers=A).status_code == 200
    assert client.get("/api/spaces/COPY", headers=A).status_code == 404
    act = client.get("/api/spaces/WEB/activity", headers=B).json()
    assert act and {"at", "actor", "key", "field"} <= set(act[0])
