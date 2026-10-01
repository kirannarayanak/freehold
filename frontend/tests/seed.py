"""Seed demo data into an empty OpenTrack for the UI smoke test."""
import datetime as dt
import os

import httpx

c = httpx.Client(base_url=os.getenv("OPENTRACK_URL", "http://127.0.0.1:8099"))
a = c.post("/api/auth/register", json={"name":"Kiran Narayana","email":"kiran@example.com","password":"correct-horse"}).json()
A = {"Authorization": "Bearer "+a["token"]}
for n,e in (("Bob Stone","bob@example.com"),("Carol Diaz","carol@example.com")):
    c.post("/api/users", json={"name":n,"email":e,"password":"password1"}, headers=A)
c.post("/api/spaces", json={"key":"WEB","name":"Website relaunch"}, headers=A)
for e in ("bob@example.com","carol@example.com"):
    c.post("/api/spaces/WEB/members", json={"email":e,"role":"member"}, headers=A)
users = {u["name"]:u["id"] for u in c.get("/api/users", headers=A).json()}
sid = c.get("/api/spaces/WEB", headers=A).json()["sprints"][0]["id"]
epic = c.post("/api/spaces/WEB/items", json={"title":"Checkout redesign","type":"Epic","priority":"High","start":"2026-09-20","due":"2026-10-20"}, headers=A).json()
today = dt.date.today()
specs = [("Payment gateway integration","Task","Highest","In progress",[users["Kiran Narayana"]],8,["payments"],str(today+dt.timedelta(days=4))),
 ("Cart total rounding bug","Bug","High","To do",[],2,["payments","bug"],str(today-dt.timedelta(days=1))),
 ("Order confirmation email","Story","Medium","In review",[users["Bob Stone"],users["Carol Diaz"]],3,["email"],None),
 ("Guest checkout","Story","High","Done",[users["Bob Stone"]],5,[],None)]
keys=[]
for t,ty,p,st,asg,pts,lab,due in specs:
    it = c.post("/api/spaces/WEB/items", json={"title":t,"type":ty,"priority":p,"status":st,"assignee_ids":asg,"points":pts,"labels":lab,"due":due,"parent_key":epic["key"],"sprint_id":sid,"start":str(today-dt.timedelta(days=3)),"description":"Some **markdown** with a task list:\n\n- [x] done thing\n- [ ] open thing\n\ncc @bob.stone see "+epic["key"]}, headers=A).json()
    keys.append(it["key"])
c.post(f"/api/items/{keys[0]}/links", json={"type":"blocks","target_key":keys[1]}, headers=A)
c.post("/api/spaces/WEB/items", json={"title":"Write API docs","type":"Task"}, headers=A)
c.patch(f"/api/sprints/{sid}", json={"state":"active","start":str(today-dt.timedelta(days=3)),"goal":"Ship checkout"}, headers=A)
c.post(f"/api/items/{keys[0]}/comments", json={"body":"Webhooks are next. @bob.stone can you review?"}, headers=A)
print("seeded", keys, epic["key"])
