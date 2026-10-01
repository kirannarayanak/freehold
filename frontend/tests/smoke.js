/* Headless click-through of the web app against a running server seeded by seed.py. Run via run.sh. */
const { JSDOM, VirtualConsole } = require("jsdom");
const BASE = process.env.FREEHOLD_URL || "http://127.0.0.1:8099/";
const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => errors.push("jsdomError: " + (e.stack || e.message)));
vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));
process.on("unhandledRejection", e => errors.push("unhandledRejection: " + (e && e.stack || e)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
let adminToken;

async function api(method, path, body, token) {
  const r = await fetch(new URL(path, BASE), { method, headers: Object.assign({ "Content-Type": "application/json" }, token ? { Authorization: "Bearer " + token } : {}), body: body ? JSON.stringify(body) : undefined });
  return r.json();
}
async function until(fn, label, ms = 4000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(40); }
  throw new Error("Timed out waiting for: " + label);
}
const results = [];
const ok = (name, cond, extra) => { results.push((cond ? "PASS " : "FAIL ") + name + (extra ? " (" + extra + ")" : "")); };

(async () => {
  adminToken = (await api("POST", "/api/auth/login", { email: "kiran@example.com", password: "correct-horse" })).token;
  const dom = await JSDOM.fromURL(BASE, {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = (u, o) => fetch(new URL(u, BASE), o);
      const JsdomFD = w.FormData;
      w.FormData = function (form) {
        const fd = new FormData();
        if (form) for (const [k, v] of new JsdomFD(form)) fd.append(k, v);
        return fd;
      };
      const P = w.HTMLDialogElement.prototype;
      P.showModal = function () { this.open = true; };
      P.close = function () { if (!this.open) return; this.open = false; this.dispatchEvent(new w.Event("close")); };
      w.HTMLElement.prototype.scrollIntoView = function () {};
    },
  });
  const w = dom.window, d = w.document;
  const $ = s => d.querySelector(s), $$ = s => Array.from(d.querySelectorAll(s));
  const click = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  const change = (el, v) => { if (v !== undefined) { if (el.type === "checkbox") el.checked = v; else el.value = v; } el.dispatchEvent(new w.Event("change", { bubbles: true })); };
  const input = (el, v) => { el.value = v; el.dispatchEvent(new w.Event("input", { bubbles: true })); };
  const F = (form, n) => form.querySelector('[name="' + n + '"]');
  const submit = f => f.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  const key = (el, k, extra) => el.dispatchEvent(new w.KeyboardEvent("keydown", Object.assign({ key: k, bubbles: true, cancelable: true }, extra || {})));
  await until(() => w.Freehold && !$("#auth").hidden && $("form[data-form=login]"), "login form");
  ok("login screen shows", true);

  // wrong password shows an error
  let f = $("form[data-form=login]");
  F(f,"email").value = "kiran@example.com"; F(f,"password").value = "nope"; submit(f);
  await until(() => $(".form-err").textContent, "login error");
  ok("wrong password message", /do not match/.test($(".form-err").textContent));
  F(f,"password").value = "correct-horse"; submit(f);
  await until(() => !$("#app").hidden && $$(".card").length, "board cards");
  ok("board renders cards", $$(".card").length === 4, $$(".card").length + " cards");
  ok("WIP/cols", $$(".col-h").length === 4);
  ok("blocked flag on card", $$(".flag-block").length === 1);
  ok("overdue flag on card", $$(".flag-late").length === 1);
  ok("nav has 8 views", $$(".nav-btn").length === 8);

  // filter
  const q = $("#q");
  input(q, "assignee = me");
  await sleep(250);
  ok("filter narrows board", $$(".card").length === 1, $$(".card").length + " cards");
  input(q, "status in (Done");
  await sleep(250);
  ok("bad filter shows error", /closing parenthesis/.test($("#qerr").textContent), $("#qerr").textContent);
  input(q, "");
  await sleep(250);

  // swimlanes
  change($('select[data-change="lanes"]'), "assignee");
  await sleep(50);
  ok("swimlanes by assignee", $$(".lane-h").length >= 2, $$(".lane-h").length + " lanes");
  change($('select[data-change="lanes"]'), "none");

  // drag and drop a card to Done
  const cardEl = $$(".card").find(c => c.dataset.key === "WEB-3");
  const dt = { setData() {}, types: [], files: [], effectAllowed: "" };
  const dragEv = type => { const e = new w.Event(type, { bubbles: true, cancelable: true }); e.dataTransfer = dt; return e; };
  cardEl.dispatchEvent(dragEv("dragstart"));
  const doneCol = $$(".col").find(c => c.dataset.status === "Done");
  doneCol.dispatchEvent(dragEv("dragover"));
  doneCol.dispatchEvent(dragEv("drop"));
  await sleep(300);
  let srv = await api("GET", "/api/items/WEB-3", null, adminToken);
  ok("drag to Done saves status", srv.item.status === "Done" && srv.item.resolved_at, srv.item.status);

  // open item dialog
  click($$(".card").find(c => c.dataset.key === "WEB-2"));
  await until(() => $("#dlg").open && $(".dlg-h"), "dialog");
  ok("dialog opens with title", $(".title-in").value === "Payment gateway integration");
  ok("markdown rendered", $(".desc strong") && $(".desc input[type=checkbox][checked]") && $(".desc .mention") && $(".desc a.keyref"));
  ok("links shown", /blocks/.test($(".dlg-main").textContent));
  change($('select[data-field="status"]'), "In review");
  await sleep(300);
  srv = await api("GET", "/api/items/WEB-2", null, adminToken);
  ok("status change from dialog", srv.item.status === "In review");
  // assign bob
  const bob = w.Freehold.S.members.find(m => m.name === "Bob Stone");
  change($('select[data-change="assign"]'), String(bob.id));
  await sleep(300);
  srv = await api("GET", "/api/items/WEB-2", null, adminToken);
  ok("multiple assignees", srv.item.assignee_ids.length === 2, JSON.stringify(srv.item.assignee_ids));
  // description edit
  click($(".desc"));
  await until(() => $("#descBox"), "desc editor");
  input($("#descBox"), "New **desc** for @bob.stone");
  click($('[data-act="descTab"][data-p="1"]'));
  ok("preview renders", $(".md.prev strong") && $(".md.prev .mention"));
  click($('[data-act="saveDesc"]'));
  await sleep(300);
  srv = await api("GET", "/api/items/WEB-2", null, adminToken);
  ok("description saved", srv.item.description === "New **desc** for @bob.stone");
  // comment
  await until(() => $("#cBody"), "comment box");
  input($("#cBody"), "Looks good @bo");
  ok("mention suggestions", $("#mentionBox") && /Bob Stone/.test($("#mentionBox").textContent));
  click($('#mentionBox [data-act="pickMention"]'));
  ok("mention inserted", $("#cBody").value === "Looks good @bob.stone ", JSON.stringify($("#cBody").value));
  click($('[data-act="addComment"]'));
  await sleep(300);
  srv = await api("GET", "/api/items/WEB-2", null, adminToken);
  ok("comment posted", srv.comments.length === 2);
  // checklist add
  const ck = $('input[data-quick="check"]');
  ck.value = "Write tests"; key(ck, "Enter");
  await sleep(300);
  srv = await api("GET", "/api/items/WEB-2", null, adminToken);
  ok("checklist item added", srv.item.checklist.length === 1);
  // attachment upload
  await w.Freehold.uploadFiles([new File(["hello world"], "notes.txt", { type: "text/plain" })]);
  await sleep(200);
  ok("attachment listed", /notes\.txt/.test($(".atts").textContent));
  // log work
  click($('[data-act="dtab"][data-t="worklog"]'));
  $("#wlHours").value = "1.5"; click($('[data-act="logWork"]'));
  await sleep(300);
  srv = await api("GET", "/api/items/WEB-2", null, adminToken);
  ok("time logged", srv.item.logged === 1.5);
  click($('[data-act="dtab"][data-t="history"]'));
  ok("history tab", $$(".hist").length > 3, $$(".hist").length + " rows");
  // add child subtask
  const child = $('input[data-quick="child"]');
  child.value = "Handle refunds !high"; key(child, "Enter");
  await sleep(400);
  ok("child subtask created", /Handle refunds/.test($(".dlg-main").textContent));
  // link
  $("#linkKey").value = "WEB-6"; $("#linkType").value = "relates to";
  click($('[data-act="addLink"]'));
  await sleep(300);
  ok("link added", /relates to/.test($(".dlg-main").textContent));
  // watch toggle
  click($('[data-act="watch"]'));
  await sleep(250);
  ok("watch toggles", /Watch/.test($('[data-act="watch"]').textContent));
  click($('[data-act="closeDlg"]'));
  ok("dialog closed", !$("#dlg").open);

  // create modal with quick syntax
  click($('[data-act="openCreate"]'));
  await until(() => $("#modal").open, "create modal");
  const cf = $('form[data-form="create"]');
  input(F(cf,"title"), "Guest checkout flow");
  await sleep(20);
  ok("duplicate suggestion", /Guest checkout/.test($("#dupes").textContent));
  F(cf,"title").value = "bug: Fix login timeout @bob !high #web ~3";
  submit(cf);
  await sleep(400);
  const all = await api("GET", "/api/spaces/WEB", null, adminToken);
  const made = all.items.find(i => i.title === "Fix login timeout");
  ok("quick syntax create", made && made.type === "Bug" && made.priority === "High" && made.labels[0] === "web" && made.points === 3 && made.assignee_ids[0] === bob.id,
    made && JSON.stringify([made.type, made.priority, made.labels, made.points, made.assignee_ids]));

  // board quick create
  const qc = $('input[data-quick="board"]');
  qc.value = "Board quick item ~2"; key(qc, "Enter");
  await sleep(400);
  ok("board quick create in sprint", $$(".card").some(c => /Board quick item/.test(c.textContent)));

  // views
  const views = { backlog: ".bl-sec", list: "table.tbl", timeline: ".tl", calendar: ".cal", reports: ".tiles", activity: ".feed", settings: ".card-sec" };
  for (const [v, sel] of Object.entries(views)) {
    click($$(".nav-btn").find(b => b.dataset.to.endsWith("/" + v)));
    await until(() => $(sel), v + " view");
    ok(v + " view renders", true);
  }
  // reports charts load
  click($$(".nav-btn").find(b => b.dataset.to.endsWith("/reports")));
  await until(() => $$("#r-burn figure.chart, #r-cfd figure.chart, #r-cvr figure.chart").length === 3, "report charts");
  ok("report charts render", !/NaN/.test($(".reports").innerHTML));

  // list: select + bulk priority
  click($$(".nav-btn").find(b => b.dataset.to.endsWith("/list")));
  await sleep(50);
  const boxes = $$('input[data-change="sel"]').slice(0, 2);
  boxes.forEach(b => change(b, true));
  await sleep(50);
  ok("bulk bar appears", $(".bulk") && /2 selected/.test($(".bulk").textContent));
  change($('select[data-field="priority"]'), "Low");
  await sleep(400);
  const lst = await api("GET", "/api/spaces/WEB", null, adminToken);
  ok("bulk update", lst.items.filter(i => i.priority === "Low").length >= 2);
  click($('[data-act="sort"][data-k="priority"]'));
  ok("sort by priority", true);

  // backlog: drag an item from backlog into sprint section
  click($$(".nav-btn").find(b => b.dataset.to.endsWith("/backlog")));
  await sleep(50);
  const bRow = $$(".row").find(r => /Write API docs/.test(r.textContent));
  bRow.dispatchEvent(dragEv("dragstart"));
  const sprintSec = $$(".bl-sec").find(s => s.dataset.sprint !== "backlog");
  sprintSec.dispatchEvent(dragEv("drop"));
  await sleep(300);
  const moved = (await api("GET", "/api/spaces/WEB", null, adminToken)).items.find(i => i.title === "Write API docs");
  ok("drag into sprint", moved.sprint_id === Number(sprintSec.dataset.sprint));

  // settings: add workflow status and save
  click($$(".nav-btn").find(b => b.dataset.to.endsWith("/settings")));
  await sleep(50);
  click($('[data-act="wfAdd"]'));
  const names = $$('input[data-change="wf"][data-k="name"]');
  change(names[names.length - 1], "QA");
  click($('[data-act="wfMove"][data-i="' + (names.length - 1) + '"][data-d="-1"]'));
  click($('[data-act="wfSave"]'));
  await sleep(400);
  const sp = await api("GET", "/api/spaces/WEB", null, adminToken);
  ok("workflow saved", sp.space.statuses.map(s => s.name).join(",") === "To do,In progress,In review,QA,Done", sp.space.statuses.map(s => s.name).join(","));

  // command palette
  key(d.body, "k", { ctrlKey: true });
  ok("palette opens", !$("#palette").hidden);
  input($("#palQ"), "go to calendar");
  key($("#palQ"), "Enter");
  await sleep(200);
  ok("palette runs command", w.Freehold.S.view === "calendar" && $(".cal"));
  key(d.body, "3");
  await sleep(150);
  ok("number shortcut", w.Freehold.S.view === "list");

  // notifications panel
  click($('[data-act="toggleNotifs"]'));
  ok("notifications panel", !$("#notifs").hidden && $(".notifs-h"));
  click($('[data-act="toggleNotifs"]'));

  // profile prefs
  click($('[data-to="#/profile"]'));
  await until(() => $('form[data-form="prefs"]'), "profile");
  const pf = $('form[data-form="prefs"]');
  F(pf,"commented.email").checked = true; F(pf,"email_mode").value = "digest";
  submit(pf);
  await sleep(300);
  const me = await api("GET", "/api/me", null, adminToken);
  ok("prefs saved", me.prefs.events.commented.email === true && me.prefs.email_mode === "digest");

  // admin: create user
  click($('[data-to="#/admin"]'));
  await until(() => $('form[data-form="newUser"]'), "admin");
  const nf = $('form[data-form="newUser"]');
  F(nf,"name").value = "Dana Lee"; F(nf,"email").value = "dana@example.com"; F(nf,"password").value = "password1";
  submit(nf);
  await sleep(400);
  ok("admin creates user", /Dana Lee/.test($("#view").textContent));

  // complete sprint from board
  click($$(".nav-btn").find(b => b.dataset.to.endsWith("/board")));
  await sleep(50);
  click($('[data-act="completeSprint"]'));
  await until(() => $("#modal").open && $('form[data-form="complete"]'), "complete modal");
  submit($('form[data-form="complete"]'));
  await sleep(500);
  const after = await api("GET", "/api/spaces/WEB", null, adminToken);
  ok("sprint completed", after.sprints.some(s => s.state === "closed") && after.sprints.some(s => s.name === "Sprint 2"));
  ok("board shows empty state", /No active sprint/.test($("#view").textContent));

  // new space form
  click($('[data-to="#/profile"]'));
  w.location.hash = "#/new-space";
  await until(() => $('form[data-form="newSpace"]'), "new space form");
  const sf = $('form[data-form="newSpace"]');
  input(F(sf,"name"), "Mobile App");
  ok("key suggestion", F(sf,"key").value === "MA", F(sf,"key").value);
  F(sf,"key").value = "MOB"; sf.querySelector('input[value="kanban"]').checked = true;
  submit(sf);
  await until(() => w.Freehold.S.space && w.Freehold.S.space.key === "MOB", "new space");
  ok("kanban space created", /Kanban/.test($("#view").textContent));

  // theme toggle and logout
  click($('[data-act="toggleTheme"]'));
  ok("theme toggles", ["dark", "light"].includes(d.documentElement.dataset.theme));
  click($('[data-act="logout"]'));
  await until(() => !$("#auth").hidden, "logout");
  ok("logout", true);

  await sleep(200);
  console.log(results.join("\n"));
  const fails = results.filter(r => r.startsWith("FAIL")).length;
  console.log("\n" + (results.length - fails) + " passed, " + fails + " failed, " + errors.length + " runtime errors");
  errors.slice(0, 10).forEach(e => console.log(e.slice(0, 600)));
  process.exit(fails || errors.length ? 1 : 0);
})().catch(e => { console.log(results.join("\n")); console.log("CRASH", e.stack); errors.slice(0, 10).forEach(x => console.log(x.slice(0, 600))); process.exit(1); });
