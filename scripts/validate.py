#!/usr/bin/env python3
"""End-to-end lifecycle check against a FRESH Freehold instance.

Runs what a real team does in its first sprint: set up, migrate from Jira, plan, work, complete,
report. Every step asserts something a user would notice, so a pass means the product works rather
than that the server stayed up.

    python scripts/validate.py                       # http://localhost:8090
    python scripts/validate.py http://localhost:8080

The instance must be EMPTY: the first step claims the site admin account.
"""
import sys
import time
from datetime import date, timedelta

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090").rstrip("/")
c = httpx.Client(base_url=BASE, timeout=30)
passed, failed = [], []


def check(name, condition, detail=""):
    (passed if condition else failed).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    return condition


def api(method, path, token=None, **kw):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    r = c.request(method, path, headers=h, **kw)
    return r


def section(t):
    print(f"\n{t}")


TODAY = date.today()
JIRA_CSV = (
    "Issue key,Issue Type,Summary,Status,Priority,Assignee,Reporter,Created,Updated,Resolved,"
    "Sprint,Labels,Labels,Story Points,Original Estimate,Comment\n"
    "LEG-1,Story,Legacy login screen,In Progress,High,Dana Reed,Dana Reed,01/Sep/26 9:15 AM,"
    "20/Sep/26 2:00 PM,,Sprint A,legacy,auth,5,28800,\"18/Sep/26 10:00 AM;dana;Started on this\"\n"
    "LEG-2,Bug,Session expires too fast,Done,Highest,Dana Reed,Dana Reed,02/Sep/26 10:00 AM,"
    "21/Sep/26 9:00 AM,21/Sep/26 9:00 AM,Sprint A,auth,bug,2,7200,\n"
)

# ---------------------------------------------------------------- set up
section("Setting up, as a new team would")
st = api("GET", "/api/auth/status").json()
if not check("instance is empty and wants setup", st.get("needs_setup") is True,
             "run this against a fresh instance"):
    sys.exit(1)
check("licence and source are offered before sign-in (AGPL s13)",
      bool(st.get("source_url")) and bool(st.get("license")))

admin = api("POST", "/api/auth/register",
            json={"name": "Dana Reed", "email": "dana@example.com", "password": "correct-horse"}).json()
A = admin["token"]
check("first account becomes site admin", admin["user"]["is_admin"] is True)
check("closed sign-up blocks a second self-registration",
      api("POST", "/api/auth/register",
          json={"name": "Nope", "email": "n@example.com", "password": "12345678"}).status_code == 403)

for name, email in (("Sam Okafor", "sam@example.com"), ("Priya Raman", "priya@example.com")):
    api("POST", "/api/users", A, json={"name": name, "email": email, "password": "password1"})
users = {u["name"]: u for u in api("GET", "/api/users", A).json()}
check("teammates created", len(users) == 3, str(list(users)))
S = api("POST", "/api/auth/login", json={"email": "sam@example.com", "password": "password1"}).json()["token"]
P = api("POST", "/api/auth/login", json={"email": "priya@example.com", "password": "password1"}).json()["token"]

# ---------------------------------------------------------------- space and config
section("Creating a space and configuring it")
check("space created", api("POST", "/api/spaces", A, json={"key": "web", "name": "Website"}).status_code == 200)
api("POST", "/api/spaces/WEB/members", A, json={"email": "sam@example.com", "role": "member"})
api("POST", "/api/spaces/WEB/members", A, json={"email": "priya@example.com", "role": "viewer"})
b = api("GET", "/api/spaces/WEB", A).json()
check("members have the roles they were given",
      {m["name"]: m["role"] for m in b["members"]}.get("Priya Raman") == "viewer")

statuses = b["space"]["statuses"] + [{"name": "QA", "category": "doing", "wip": 2}]
api("PATCH", "/api/spaces/WEB", A, json={"statuses": statuses})
check("workflow takes a new status",
      "QA" in [s["name"] for s in api("GET", "/api/spaces/WEB", A).json()["space"]["statuses"]])

sev = api("POST", "/api/spaces/WEB/fields", A,
          json={"name": "Severity", "type": "select", "options": ["Low", "High"]}).json()
api("POST", "/api/spaces/WEB/fields", A, json={"name": "Customer", "type": "text"})
check("custom fields defined", "key" in sev and sev["key"] == "severity")
check("a field may not shadow a built-in",
      api("POST", "/api/spaces/WEB/fields", A, json={"name": "Status"}).status_code == 422)

# ---------------------------------------------------------------- migration
section("Migrating from Jira")
api("POST", "/api/spaces", A, json={"key": "LEG", "name": "Legacy"})
api("POST", "/api/spaces/LEG/members", A, json={"email": "sam@example.com", "role": "member"})
res = api("POST", "/api/spaces/LEG/import/jira", A,
          files={"file": ("jira.csv", JIRA_CSV.encode(), "text/csv")}).json()
check("jira csv imports", res.get("created") == 2, str(res))
leg = api("GET", "/api/spaces/LEG", A).json()
items = {i["key"]: i for i in leg["items"]}
check("original jira keys are preserved", set(items) == {"LEG-1", "LEG-2"}, str(list(items)))
check("duplicate Labels columns merge", items["LEG-1"]["labels"] == ["legacy", "auth"])
check("seconds convert to hours", items["LEG-1"]["estimate"] == 8.0)
check("work is backdated, so reports are honest",
      items["LEG-1"]["created_at"].startswith("2026-09-01"), items["LEG-1"]["created_at"])
d1 = api("GET", "/api/items/LEG-1", A).json()
check("comments come across with their author and date",
      any(x["body"] == "Started on this" for x in d1["comments"]))
starts = [h for h in d1["history"] if h["field"] == "created"]
check("exactly one created row, so reports do not read it back as new", len(starts) == 1, str(len(starts)))
check("history ends on the item's real status",
      sorted((h for h in d1["history"] if h["field"] in ("created", "status")),
             key=lambda h: h["at"])[-1]["new"] == items["LEG-1"]["status"])

# ---------------------------------------------------------------- plan
section("Planning a sprint")
ver = api("POST", "/api/spaces/WEB/versions", A, json={"name": "1.0", "release_date": str(TODAY + timedelta(days=30))}).json()
sprint = api("GET", "/api/spaces/WEB", A).json()["sprints"][0]
made = []
for title, typ, pts in (("Checkout redesign", "Epic", None), ("Payment gateway", "Task", 8),
                        ("Rounding bug", "Bug", 2), ("Guest checkout", "Story", 5)):
    body = {"title": title, "type": typ, "points": pts, "sprint_id": sprint["id"]}
    if typ != "Epic":
        body["version_id"] = ver["id"]
    made.append(api("POST", "/api/spaces/WEB/items", A, json=body).json())
epic, pay, bug, guest = made
check("work items created with points and a fix version",
      all("key" in m for m in made) and pay["version_id"] == ver["id"])
api("PATCH", f"/api/items/{pay['key']}", A,
    json={"parent_key": epic["key"], "assignee_ids": [users["Sam Okafor"]["id"]],
          "custom": {"severity": "High", "customer": "Acme"}})
api("POST", f"/api/items/{pay['key']}/links", A, json={"type": "blocks", "target_key": bug["key"]})
check("custom values, parent and link all stick",
      api("GET", f"/api/items/{pay['key']}", A).json()["item"]["custom"]["severity"] == "High")

# ---------------------------------------------------------------- permissions
section("Checking permissions hold")
check("a viewer cannot edit",
      api("PATCH", f"/api/items/{bug['key']}", P, json={"title": "hacked"}).status_code == 403)
check("a viewer can read", api("GET", "/api/spaces/WEB", P).status_code == 200)
check("a member cannot change space settings",
      api("PATCH", "/api/spaces/WEB", S, json={"name": "nope"}).status_code == 403)
check("a non-member sees nothing, not even that it exists",
      api("GET", "/api/spaces/LEG", P).status_code == 404)

# ---------------------------------------------------------------- work
section("Working the sprint")
api("PATCH", f"/api/sprints/{sprint['id']}", A,
    json={"state": "active", "start": str(TODAY - timedelta(days=5)), "goal": "Ship checkout"})
check("sprint starts", api("GET", "/api/spaces/WEB", A).json()["sprints"][0]["state"] == "active")
api("PATCH", f"/api/items/{pay['key']}", S, json={"status": "In progress"})
api("POST", f"/api/items/{pay['key']}/comments", S, json={"body": "Webhooks next. @dana.reed please review"})
api("POST", f"/api/items/{pay['key']}/worklogs", S, json={"hours": 3, "day": str(TODAY), "note": "integration"})
api("POST", f"/api/items/{pay['key']}/attachments", S,
    files={"file": ("notes.txt", b"some notes", "text/plain")})
detail = api("GET", f"/api/items/{pay['key']}", A).json()
check("time is logged", detail["item"]["logged"] == 3)
check("attachment is stored", len(detail["attachments"]) == 1)
check("a mention notifies the person mentioned",
      any("@dana.reed" in x["body"] or "mention" in x.get("event", "")
          for x in detail["comments"]) and
      any(n["event"] == "mentioned" for n in api("GET", "/api/notifications", A).json()["items"]))
check("the blocked item is flagged as blocked",
      bug["key"] in [i["key"] for i in api("GET", "/api/search", A, params={"q": "is:blocked", "space": "WEB"}).json()["items"]])

# ---------------------------------------------------------------- queries
section("Filtering")
for q, want in (("is:open", True), ("severity = High", True), ("customer ~ acme", True),
                ("points >= 5", True), ("assignee = sam.okafor", True), ("assignee ~ sam", True), ("sprint = \"" + sprint["name"] + "\"", True)):
    r = api("GET", "/api/search", A, params={"q": q, "space": "WEB"})
    check(f"query works: {q}", r.status_code == 200 and (len(r.json()["items"]) > 0) == want,
          r.text[:120])
check("a bad query explains itself rather than returning nothing",
      api("GET", "/api/search", A, params={"q": "notafield = x", "space": "WEB"}).status_code == 400)

# ---------------------------------------------------------------- integrations
section("Integrations")
tok = api("POST", "/api/me/tokens", A, json={"name": "validation"}).json()
check("an api token can act for its owner",
      api("GET", "/api/spaces/WEB", tok["token"]).status_code == 200)
api("DELETE", f"/api/me/tokens/{tok['id']}", A)
check("a revoked token stops working immediately",
      api("GET", "/api/spaces/WEB", tok["token"]).status_code == 401)
hook = api("POST", "/api/spaces/WEB/webhooks", A, json={"url": "http://127.0.0.1:1/dead"}).json()
check("a dead webhook does not stop work being filed",
      api("POST", "/api/spaces/WEB/items", A, json={"title": "still works"}).status_code == 200)
api("DELETE", f"/api/webhooks/{hook['id']}", A)

# ---------------------------------------------------------------- catch up
section("Catching up")
cu = api("GET", "/api/catch-up", A, params={"days": 7}).json()
check("catch-up reports other people's changes to your work", cu["total"] > 0, str(cu))
check("catch-up excludes your own edits",
      all(x["key"] != guest["key"] for x in cu["moved"]))

# ---------------------------------------------------------------- finish
section("Completing the sprint and reporting")
api("PATCH", f"/api/items/{guest['key']}", A, json={"status": "Done"})
api("PATCH", f"/api/items/{pay['key']}", A, json={"status": "Done"})
api("PATCH", f"/api/items/{bug['key']}", A, json={"status": "Done"})
burn = api("GET", "/api/spaces/WEB/reports/burndown", A, params={"sprint_id": sprint["id"]}).json()
check("burndown has a real series", any(v is not None for v in burn["remaining"]), str(burn)[:160])
api("POST", f"/api/sprints/{sprint['id']}/complete", A)
sp = api("GET", "/api/spaces/WEB", A).json()["sprints"][0]
check("completing a sprint records committed and completed",
      sp["state"] == "closed" and sp["committed_points"] is not None)
vel = api("GET", "/api/spaces/WEB/reports/velocity", A).json()
check("velocity sees the closed sprint", len(vel["sprints"]) == 1, str(vel))

rel = api("PATCH", f"/api/versions/{ver['id']}", A, json={"released": True})
check("a version releases once its work is finished", rel.status_code == 200, rel.text[:140])
notes = api("GET", f"/api/versions/{ver['id']}/notes", A).json()
check("release notes list what shipped", "Guest checkout" in notes["markdown"], notes["markdown"][:160])

# ---------------------------------------------------------------- data out
section("Getting your data out")
exp = api("GET", "/api/spaces/WEB/export", A).json()
check("export contains the work", len(exp["items"]) >= 4)
api("POST", "/api/spaces", A, json={"key": "COPY", "name": "Round trip"})
imp = api("POST", "/api/spaces/COPY/import/freehold", A,
          files={"file": ("export.json", __import__("json").dumps(exp).encode(), "application/json")}).json()
check("an export re-imports, so there is no lock-in", imp.get("created", 0) >= 4, str(imp))
check("csv export works", api("GET", "/api/spaces/WEB/export.csv", A).status_code == 200)

# ---------------------------------------------------------------- report
print("\n" + "=" * 62)
print(f"  {len(passed)} passed, {len(failed)} failed")
if failed:
    print("\n  Failures:")
    for f in failed:
        print(f"    - {f}")
print("=" * 62)
sys.exit(1 if failed else 0)
