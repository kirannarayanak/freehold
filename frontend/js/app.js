/* Freehold web app. Plain JavaScript, no build step: edit and reload. */
(function () {
  "use strict";
  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));
  const esc = MD.esc;

  const VIEWS = [["board", "Board"], ["backlog", "Backlog"], ["list", "List"], ["timeline", "Timeline"],
    ["calendar", "Calendar"], ["reports", "Reports"], ["activity", "Activity"], ["settings", "Settings"]];
  const TYPES = ["Epic", "Story", "Task", "Bug", "Subtask"];
  const PRIORITIES = ["Highest", "High", "Medium", "Low"];
  const TYPE_ICON = { Epic: "⚡", Story: "▣", Task: "✓", Bug: "●", Subtask: "↳" };
  const PRI_ICON = { Highest: "⇈", High: "↑", Medium: "=", Low: "↓" };
  const LINK_TYPES = ["blocks", "blocked by", "relates to", "duplicates", "duplicated by"];
  const EVENTS = [["assigned", "Someone assigns a work item to you"], ["mentioned", "Someone mentions you with @"],
    ["commented", "New comments on work you are involved in"], ["status", "Status changes on work you are involved in"],
    ["updated", "Other edits on work you are involved in"]];

  const S = {
    me: null, users: [], userById: {}, spaces: [], space: null, role: null, members: [], sprints: [], versions: [], fields: [], items: [],
    links: [], filters: [], byKey: {}, serverTime: null, view: "board", lanes: "none", query: "", selected: new Set(),
    sortK: "key", sortDir: 1, calMonth: null, notes: { unread: 0, items: [] }, openKey: null, detail: null,
    descEdit: false, descPreview: false, editComment: null, dtab: "comments", reportSprint: null, dragging: null,
    wf: null, importResult: "", loading: false,
  };

  /* ---------- small helpers ---------- */
  const ts = iso => (iso ? Date.parse(String(iso).slice(0, 23) + (String(iso).endsWith("Z") ? "" : "Z")) : NaN);
  const today = () => OQL.isoDay(new Date());
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  function fmtDay(d) { if (!d) return ""; const [y, m, day] = d.slice(0, 10).split("-"); return +day + " " + MONTHS[+m - 1] + (y !== String(new Date().getFullYear()) ? " " + y : ""); }
  const DRAFT = "freehold.draft.";
  function draftKey(kind) { return DRAFT + (S.openKey || "new") + "." + kind; }
  function saveDraft(kind, text) {
    try { text && text.trim() ? localStorage.setItem(draftKey(kind), text) : localStorage.removeItem(draftKey(kind)); }
    catch (e) { /* private mode, or the quota is full: a draft is a convenience, never a requirement */ }
  }
  function readDraft(kind) { try { return localStorage.getItem(draftKey(kind)) || ""; } catch (e) { return ""; } }
  function clearDraft(kind) { try { localStorage.removeItem(draftKey(kind)); } catch (e) {} }

  function ago(iso) {
    const s = (Date.now() - ts(iso)) / 1000;
    if (isNaN(s)) return "";
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + "m ago";
    if (s < 86400) return Math.floor(s / 3600) + "h ago";
    if (s < 86400 * 7) return Math.floor(s / 86400) + "d ago";
    return fmtDay(new Date(ts(iso)).toISOString());
  }
  const initials = n => String(n || "?").split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
  function hue(s) { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
  function avatar(uid, size) {
    const u = S.userById[uid];
    if (!u) return "";
    return '<span class="av' + (size ? " av-" + size : "") + '" style="--h:' + hue(u.name) + '" title="' + esc(u.name) + '">' + esc(initials(u.name)) + "</span>";
  }
  const avatars = ids => '<span class="avs">' + (ids || []).map(id => avatar(id)).join("") + "</span>";
  const uname = id => (S.userById[id] ? S.userById[id].name : "Unassigned");
  const canEdit = () => S.role === "member" || S.role === "admin";
  const isAdmin = () => S.role === "admin";
  const cat = status => { const s = S.space && S.space.statuses.find(x => x.name === status); return s ? s.category : "todo"; };
  const isDone = it => cat(it.status) === "done";
  const sprintName = id => { const s = S.sprints.find(x => x.id === id); return s ? s.name : "Backlog"; };
  const activeSprint = () => S.sprints.find(s => s.state === "active");
  const opt = (value, label, selected) => '<option value="' + esc(value) + '"' + (selected ? " selected" : "") + ">" + esc(label) + "</option>";
  const typeIcon = t => '<span class="tp tp-' + esc(t) + '" title="' + esc(t) + '">' + (TYPE_ICON[t] || "") + "</span>";
  const priIcon = p => '<span class="pri pri-' + esc(p) + '" title="' + esc(p) + ' priority">' + (PRI_ICON[p] || "") + "</span>";
  const statusPill = s => '<span class="pill cat-' + cat(s) + '">' + esc(s) + "</span>";
  const fld = (form, name) => form.querySelector('[name="' + name + '"]');
  const fmtSize = b => (b < 1024 ? b + " B" : b < 1048576 ? (b / 1024).toFixed(0) + " KB" : (b / 1048576).toFixed(1) + " MB");

  function toast(msg, actionLabel, action) {
    const t = $("#toast");
    t.innerHTML = esc(msg) + (actionLabel ? ' <button class="linkish" data-act="toastAction">' + esc(actionLabel) + "</button>" : "");
    S.toastAction = action || null;
    t.classList.add("show");
    clearTimeout(S.toastTimer);
    S.toastTimer = setTimeout(() => t.classList.remove("show"), actionLabel ? 6000 : 3200);
  }
  const fail = e => toast(e && e.message ? e.message : String(e));
  const plural = (n, word) => n + " " + word + (n === 1 ? "" : "s");
  const dateRange = (a, b) => (a && b ? fmtDay(a) + " to " + fmtDay(b) : a ? "Started " + fmtDay(a) : "Ends " + fmtDay(b));

  function blockedSet() {
    const out = new Set();
    for (const l of S.links) {
      if (l.type !== "blocks") continue;
      const src = S.byKey[l.source_key];
      if (!src || !isDone(src)) out.add(l.target_key);
    }
    return out;
  }
  function qctx() {
    const cats = {};
    (S.space ? S.space.statuses : []).forEach(s => (cats[s.name] = s.category));
    const sprints = {};
    S.sprints.forEach(s => (sprints[s.id] = { name: s.name, state: s.state }));
    const versions = {};
    (S.versions || []).forEach(v => (versions[v.id] = { name: v.name, released: v.released }));
    const users = {};
    S.users.forEach(u => (users[u.id] = { name: u.name, handle: u.handle, email: u.email }));
    const parents = {};
    S.items.forEach(i => (parents[i.key] = i.title));
    const custom = {};
    (S.fields || []).forEach(f => (custom[f.key] = f.type));
    return { users, sprints, versions, custom, categories: cats, parents, blocked: blockedSet(), me: S.me.id,
      staleDays: (S.space && S.space.settings && S.space.settings.stale_days) || 14, today: new Date() };
  }
  /* Apply the filter bar. Returns {items, ordered}; shows errors under the input without blocking the view. */
  function filtered(items) {
    const err = $("#qerr");
    if (!S.query.trim()) { err.textContent = ""; return { items, ordered: false }; }
    try {
      const r = OQL.run(S.query, items, qctx());
      err.textContent = "";
      return r;
    } catch (e) {
      err.textContent = e.message;
      return { items, ordered: false };
    }
  }

  function indexItems() { S.byKey = {}; S.items.forEach(i => (S.byKey[i.key] = i)); }
  function upsert(it) {
    const cur = S.byKey[it.key];
    if (cur) Object.assign(cur, it);
    else { S.items.push(it); S.byKey[it.key] = it; }
    return S.byKey[it.key];
  }
  function removeItem(key) { S.items = S.items.filter(i => i.key !== key); delete S.byKey[key]; S.selected.delete(key); }

  /* Optimistic save: the UI changes immediately and rolls back if the server says no. */
  async function saveItem(key, patch, opts) {
    const it = S.byKey[key];
    if (!it) return;
    const before = JSON.parse(JSON.stringify(it));
    Object.assign(it, patch);
    renderView();
    try {
      const updated = await API.patch("/api/items/" + encodeURIComponent(key), patch);
      upsert(updated);
      renderView();
      if (S.openKey === key && !(opts && opts.keepDialog)) refreshDetail();
      return updated;
    } catch (e) {
      Object.assign(it, before);
      renderView();
      if (S.openKey === key) renderDialog();
      fail(e);
    }
  }

  /* ---------- auth ---------- */
  async function showAuth(mode) {
    $("#app").hidden = true;
    const box = $("#auth");
    box.hidden = false;
    let status = { needs_setup: false, allow_signup: false };
    try { status = await API.get("/api/auth/status"); } catch (e) { fail(e); }
    const setup = status.needs_setup;
    const signup = !setup && status.allow_signup && mode === "signup";
    box.innerHTML = '<form class="auth-card" data-form="' + (setup || signup ? "register" : "login") + '">' +
      '<div class="brand big"><span class="logo" aria-hidden="true">✦</span>Freehold</div>' +
      (setup ? "<h1>Set up Freehold</h1><p class=\"muted\">This first account becomes the site admin. You can invite your team next.</p>"
        : signup ? "<h1>Create your account</h1>" : "<h1>Sign in</h1>") +
      (setup || signup ? '<label>Your name<input name="name" required autocomplete="name"></label>' : "") +
      '<label>Email<input name="email" type="email" required autocomplete="email"></label>' +
      '<label>Password<input name="password" type="password" required minlength="' + (setup || signup ? 8 : 1) + '" autocomplete="' + (setup || signup ? "new-password" : "current-password") + '"></label>' +
      '<p class="form-err" role="alert"></p>' +
      '<button class="btn wide" type="submit">' + (setup ? "Create admin account" : signup ? "Create account" : "Sign in") + "</button>" +
      (!setup && status.allow_signup ? '<p class="muted small">' + (signup ? '<a href="#" data-act="authMode" data-mode="login">I already have an account</a>' : '<a href="#" data-act="authMode" data-mode="signup">Create an account</a>') + "</p>" : "") +
      (!setup && !status.allow_signup ? '<p class="muted small">No account yet? Ask a site admin to add you.</p>' : "") +
      "</form>";
    const first = box.querySelector("input");
    if (first) first.focus();
  }

  async function submitAuth(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    const errBox = form.querySelector(".form-err");
    errBox.textContent = "";
    try {
      const res = await API.post(form.dataset.form === "register" ? "/api/auth/register" : "/api/auth/login", data);
      API.save(res.token);
      await start();
    } catch (e) { errBox.textContent = e.message; }
  }

  function logout() {
    API.save(null);
    S.me = null; S.space = null; S.items = []; S.byKey = {};
    location.hash = "";
    showAuth();
  }

  /* ---------- loading ---------- */
  async function loadUsers() {
    S.users = await API.get("/api/users");
    S.userById = {};
    S.users.forEach(u => (S.userById[u.id] = u));
  }
  async function loadSpaces() { S.spaces = await API.get("/api/spaces"); }

  async function loadSpace(key) {
    const b = await API.get("/api/spaces/" + encodeURIComponent(key));
    S.space = b.space; S.role = b.space.role; S.members = b.members; S.sprints = b.sprints; S.items = b.items;
    S.versions = b.versions || []; S.fields = b.fields || [];
    S.links = b.links; S.filters = b.filters; S.serverTime = b.server_time; S.selected.clear(); S.wf = null;
    S.importResult = "";
    b.members.forEach(m => { if (!S.userById[m.id]) { S.userById[m.id] = m; S.users.push(m); } });
    indexItems();
    try { localStorage.setItem("freehold.space", S.space.key); } catch (e) {}
  }

  async function start() {
    S.me = await API.get("/api/me");
    await Promise.all([loadUsers(), loadSpaces()]);
    $("#auth").hidden = true;
    $("#app").hidden = false;
    applyTheme();
    await route();
    pollNotes();
  }

  /* ---------- routing: #/s/KEY/view, #/item/KEY-1, #/profile, #/admin, #/new-space ---------- */
  async function route() {
    const h = location.hash.replace(/^#\/?/, "");
    const parts = h.split("/");
    try {
      if (parts[0] === "item" && parts[1]) {
        const key = parts[1].toUpperCase();
        const spaceKey = key.split("-")[0];
        if (!S.space || S.space.key !== spaceKey) { await loadSpace(spaceKey); if (!VIEWS.some(v => v[0] === S.view)) S.view = "board"; }
        render();
        return openItem(key);
      }
      closeDialog(true);
      if (parts[0] === "s" && parts[1]) {
        const key = parts[1].toUpperCase();
        if (!S.space || S.space.key !== key) await loadSpace(key);
        S.view = VIEWS.some(v => v[0] === parts[2]) ? parts[2] : "board";
        return render();
      }
      if (["profile", "admin", "new-space", "catch-up"].includes(parts[0])) { S.view = parts[0]; return render(); }
      let last = null;
      try { last = localStorage.getItem("freehold.space"); } catch (e) {}
      const target = S.spaces.find(s => s.key === last) || S.spaces[0];
      if (target) { location.replace("#/s/" + target.key + "/board"); return; }
      S.view = "new-space";
      render();
    } catch (e) {
      if (e.status === 404) {
        toast(e.message);
        S.space = null;
        const fallback = S.spaces[0];
        location.replace(fallback ? "#/s/" + fallback.key + "/board" : "#/new-space");
      } else fail(e);
    }
  }
  const go = hash => { if (location.hash === hash) route(); else location.hash = hash; };

  /* ---------- shell ---------- */
  function render() { renderNav(); renderView(); }

  function renderNav() {
    const sel = $("#spaceSel");
    sel.innerHTML = S.spaces.map(s => opt(s.key, s.name + " (" + s.key + ")", S.space && s.key === S.space.key)).join("") +
      opt("__new", "+ New space", false);
    if (!S.space) sel.value = "__new";
    $("#nav").innerHTML = VIEWS.map(([id, label], i) =>
      '<button class="nav-btn' + (S.view === id ? " on" : "") + '" data-act="go" data-to="#/s/' + (S.space ? S.space.key : "") + "/" + id + '"' +
      (S.space ? "" : " disabled") + ' title="Shortcut ' + (i + 1) + '">' + label + "</button>").join("");
    $("#savedFilters").innerHTML = S.space && S.filters.length ? S.filters.map(f =>
      '<div class="saved-row"><button class="side-link" data-act="applyFilter" data-q="' + esc(f.query) + '" title="' + esc(f.query) + '">' +
      esc(f.name) + (f.shared ? ' <span class="muted small">shared</span>' : "") + "</button>" +
      (f.mine ? '<button class="x" data-act="deleteFilter" data-id="' + f.id + '" aria-label="Delete filter ' + esc(f.name) + '">×</button>' : "") + "</div>").join("")
      : '<p class="hint">Type a filter above, then save it.</p>';
    $("#adminLink").hidden = !S.me.is_admin;
    const badge = $("#badge");
    badge.hidden = !S.notes.unread;
    badge.textContent = S.notes.unread > 99 ? "99+" : S.notes.unread;
    const titles = { profile: "Profile and notifications", admin: "People", "new-space": "New space",
      "catch-up": "While you were away" };
    $("#title").textContent = titles[S.view] || (S.space ? S.space.name : "Freehold");
    document.title = (titles[S.view] || (S.space ? S.space.name : "")) + " · Freehold";
    const q = $("#q");
    if (document.activeElement !== q) q.value = S.query;
    document.body.classList.toggle("no-filter", !S.space || ["settings", "activity", "profile", "admin", "new-space"].includes(S.view));
  }

  function renderView() {
    if (!S.me) return;
    const v = $("#view");
    const views = { board: viewBoard, backlog: viewBacklog, list: viewList, timeline: viewTimeline, calendar: viewCalendar,
      reports: viewReports, activity: viewActivity, settings: viewSettings, profile: viewProfile, admin: viewAdmin,
      "new-space": viewNewSpace, "catch-up": viewCatchUp };
    if (!S.space && !["profile", "admin", "new-space", "catch-up"].includes(S.view)) { viewNewSpace(v); return; }
    (views[S.view] || viewBoard)(v);
  }

  function emptyState(title, body, actions) {
    return '<div class="empty"><h2>' + esc(title) + "</h2><p>" + body + "</p>" + (actions || "") + "</div>";
  }

  /* ---------- board ---------- */
  function card(it, blocked) {
    const epic = it.parent_key && S.byKey[it.parent_key] && S.byKey[it.parent_key].type === "Epic" ? S.byKey[it.parent_key] : null;
    const overdue = it.due && it.due < today() && !isDone(it);
    const cl = it.checklist || [];
    const kids = S.items.filter(c => c.parent_key === it.key);
    return '<article class="card' + (isDone(it) ? " is-done" : "") + '" draggable="' + canEdit() + '" data-drag="' + esc(it.key) + '" data-act="open" data-key="' + esc(it.key) + '" tabindex="0">' +
      '<div class="card-t">' + esc(it.title) + "</div>" +
      (OQL.isStale && OQL.isStale(it, qctx()) ? '<div class="tags"><span class="flag flag-stale" title="No status change in ' + ((S.space.settings && S.space.settings.stale_days) || 14) + ' days">Stale</span></div>' : "") +
      ((epic || it.labels.length || blocked || overdue) ? '<div class="tags">' +
        (blocked ? '<span class="flag flag-block">Blocked</span>' : "") + (overdue ? '<span class="flag flag-late">Overdue</span>' : "") +
        (epic ? '<span class="chip epic">' + esc(epic.title) + "</span>" : "") +
        it.labels.map(l => '<span class="chip">' + esc(l) + "</span>").join("") + "</div>" : "") +
      '<div class="card-m">' + typeIcon(it.type) + '<span class="k">' + esc(it.key) + "</span>" + priIcon(it.priority) +
      (it.points != null ? '<span class="pts" title="Story points">' + it.points + "</span>" : "") +
      (cl.length ? '<span class="meta" title="Checklist">☑ ' + cl.filter(c => c.done).length + "/" + cl.length + "</span>" : "") +
      (kids.length ? '<span class="meta" title="Child items">↳ ' + kids.filter(isDone).length + "/" + kids.length + "</span>" : "") +
      (it.comment_count ? '<span class="meta" title="Comments">💬 ' + it.comment_count + "</span>" : "") +
      (it.attachment_count ? '<span class="meta" title="Attachments">📎 ' + it.attachment_count + "</span>" : "") +
      '<span class="grow"></span>' + avatars(it.assignee_ids) + "</div></article>";
  }

  function laneGroups(items) {
    if (S.lanes === "none") return [{ id: "", label: "", items }];
    const groups = new Map();
    const add = (id, label, it) => { if (!groups.has(id)) groups.set(id, { id, label, items: [] }); if (it) groups.get(id).items.push(it); };
    if (S.lanes === "assignee") {
      S.members.forEach(m => add(String(m.id), m.name));
      add("none", "Unassigned");
      items.forEach(it => add(it.assignee_ids.length ? String(it.assignee_ids[0]) : "none", "", it));
    } else if (S.lanes === "priority") {
      PRIORITIES.forEach(p => add(p, p));
      items.forEach(it => add(it.priority, it.priority, it));
    } else if (S.lanes === "epic") {
      S.items.filter(i => i.type === "Epic").forEach(e => add(e.key, e.title));
      add("none", "No epic");
      items.forEach(it => { const p = S.byKey[it.parent_key]; add(p && p.type === "Epic" ? p.key : "none", "", it); });
    }
    return Array.from(groups.values()).filter(g => g.items.length || S.lanes === "priority");
  }

  function viewBoard(v) {
    const kanban = (S.space.settings || {}).template === "kanban";
    const sprint = activeSprint();
    if (!kanban && !sprint) {
      v.innerHTML = emptyState("No active sprint", "Plan work in the backlog, then start a sprint to see it here.",
        '<button class="btn" data-act="go" data-to="#/s/' + S.space.key + '/backlog">Open backlog</button>');
      return;
    }
    let base = S.items.filter(i => i.type !== "Epic");
    if (kanban) { const cutoff = Date.now() - 14 * 864e5; base = base.filter(i => !(isDone(i) && ts(i.resolved_at) < cutoff)); }
    else base = base.filter(i => i.sprint_id === sprint.id);
    const { items, ordered } = filtered(base);
    if (!ordered) items.sort((a, b) => a.rank - b.rank);
    const blocked = blockedSet();
    const statuses = S.space.statuses;
    const counts = {};
    base.forEach(i => (counts[i.status] = (counts[i.status] || 0) + 1));
    let head = '<div class="toolbar">';
    if (sprint && !kanban) {
      const left = sprint.end ? Math.ceil((Date.parse(sprint.end) - Date.parse(today())) / 864e5) : null;
      head += '<div class="sprint-h"><strong>' + esc(sprint.name) + "</strong>" + (sprint.goal ? '<span class="muted"> ' + esc(sprint.goal) + "</span>" : "") +
        (left != null ? '<span class="chip ' + (left < 0 ? "late" : "") + '">' + (left < 0 ? -left + " days over" : left + " days left") + "</span>" : "") + "</div>";
    } else head += '<div class="sprint-h"><strong>Kanban</strong><span class="muted"> Done work older than 14 days is hidden.</span></div>';
    head += '<span class="grow"></span><label class="inline">Group by <select data-change="lanes">' +
      [["none", "Nothing"], ["assignee", "Assignee"], ["epic", "Epic"], ["priority", "Priority"]].map(([k, l]) => opt(k, l, S.lanes === k)).join("") +
      "</select></label>" + (sprint && !kanban && canEdit() ? '<button class="btn ghost" data-act="completeSprint" data-id="' + sprint.id + '">Complete sprint</button>' : "") + "</div>";
    const cols = "repeat(" + statuses.length + ", minmax(230px, 1fr))";
    let html = head + '<div class="board-wrap"><div class="board" style="--n:' + statuses.length + ";grid-template-columns:" + cols + '">';
    statuses.forEach(st => {
      const n = counts[st.name] || 0, over = st.wip && n > st.wip;
      html += '<div class="col-h' + (over ? " over-wip" : "") + '"><span class="dot cat-' + st.category + '"></span>' + esc(st.name) +
        '<span class="cnt">' + n + (st.wip ? " / " + st.wip : "") + "</span></div>";
    });
    laneGroups(items).forEach(g => {
      if (S.lanes !== "none") html += '<div class="lane-h" style="grid-column:1 / -1">' + esc(g.label || "") + ' <span class="muted">' + g.items.length + "</span></div>";
      statuses.forEach((st, i) => {
        const inCol = g.items.filter(it => it.status === st.name);
        html += '<div class="col" data-drop="status" data-status="' + esc(st.name) + '" data-lane="' + esc(g.id) + '">' +
          inCol.map(it => card(it, blocked.has(it.key))).join("") +
          (i === 0 && canEdit() && S.lanes === "none" ? '<input class="quick" data-quick="board" placeholder="+ Create: fix login @name !high #label ~3" aria-label="Quick create">' : "") +
          "</div>";
      });
    });
    v.innerHTML = html + "</div></div>";
  }

  /* ---------- backlog ---------- */
  function avgVelocity() {
    const closed = S.sprints.filter(s => s.state === "closed").slice(-3);
    return closed.length ? closed.reduce((a, s) => a + (s.completed_points || 0), 0) / closed.length : 0;
  }
  function backlogRow(it, blocked) {
    const epic = it.parent_key && S.byKey[it.parent_key] && S.byKey[it.parent_key].type === "Epic" ? S.byKey[it.parent_key] : null;
    return '<div class="row' + (isDone(it) ? " is-done" : "") + '" draggable="' + canEdit() + '" data-drag="' + esc(it.key) + '" data-drop="row" data-key="' + esc(it.key) + '">' +
      typeIcon(it.type) + '<button class="k linkish" data-act="open" data-key="' + esc(it.key) + '">' + esc(it.key) + "</button>" +
      '<button class="row-t linkish" data-act="open" data-key="' + esc(it.key) + '">' + esc(it.title) + "</button>" +
      (blocked.has(it.key) ? '<span class="flag flag-block">Blocked</span>' : "") +
      (epic ? '<span class="chip epic">' + esc(epic.title) + "</span>" : "") +
      it.labels.map(l => '<span class="chip">' + esc(l) + "</span>").join("") +
      '<span class="row-r">' + statusPill(it.status) + priIcon(it.priority) + avatars(it.assignee_ids) +
      '<span class="pts">' + (it.points != null ? it.points : "–") + "</span></span></div>";
  }
  function viewBacklog(v) {
    const { items, ordered } = filtered(S.items.filter(i => i.type !== "Epic"));
    if (!ordered) items.sort((a, b) => a.rank - b.rank);
    const blocked = blockedSet();
    const active = S.sprints.filter(s => s.state === "active"), future = S.sprints.filter(s => s.state === "future");
    const avg = avgVelocity();
    const section = (sprint) => {
      const list = items.filter(i => (sprint ? i.sprint_id === sprint.id : i.sprint_id == null));
      const pts = list.reduce((a, i) => a + (i.points || 0), 0);
      const id = sprint ? sprint.id : "backlog";
      let actions = "";
      if (canEdit()) {
        if (!sprint) actions = '<button class="btn ghost sm" data-act="createSprint">Create sprint</button>';
        else if (sprint.state === "active") actions = '<button class="btn sm" data-act="completeSprint" data-id="' + sprint.id + '">Complete sprint</button>';
        else actions = (!active.length ? '<button class="btn sm" data-act="startSprint" data-id="' + sprint.id + '">Start sprint</button>' : "") +
          '<button class="btn ghost sm" data-act="editSprint" data-id="' + sprint.id + '">Edit</button>' +
          '<button class="btn ghost sm" data-act="deleteSprint" data-id="' + sprint.id + '">Delete</button>';
      }
      const warn = sprint && sprint.state === "future" && avg && pts > avg * 1.1
        ? '<span class="chip late" title="Average of the last completed sprints">Over average velocity (' + avg.toFixed(0) + " pts)</span>" : "";
      return '<section class="bl-sec" data-drop="sprint" data-sprint="' + id + '">' +
        '<header class="bl-h"><strong>' + esc(sprint ? sprint.name : "Backlog") + "</strong>" +
        (sprint && sprint.state === "active" ? '<span class="chip on">Active</span>' : "") +
        (sprint && (sprint.start || sprint.end) ? '<span class="muted small">' + dateRange(sprint.start, sprint.end) + "</span>" : "") +
        (sprint && sprint.goal ? '<span class="muted small">' + esc(sprint.goal) + "</span>" : "") +
        '<span class="grow"></span><span class="muted small">' + plural(list.length, "item") + ", " + plural(pts, "point") + "</span>" + warn + actions + "</header>" +
        (list.map(i => backlogRow(i, blocked)).join("") || '<p class="drop-hint">Drag work items here.</p>') +
        (!sprint && canEdit() ? '<input class="quick" data-quick="backlog" placeholder="+ Create in backlog: title @name !priority #label ~points" aria-label="Quick create in backlog">' : "") +
        "</section>";
    };
    const epics = S.items.filter(i => i.type === "Epic");
    const epicPanel = '<aside class="epics"><h3>Epics</h3>' + (epics.map(e => {
      const kids = S.items.filter(i => i.parent_key === e.key), done = kids.filter(isDone).length;
      const pct = kids.length ? Math.round((done / kids.length) * 100) : 0;
      return '<button class="epic-card" data-act="open" data-key="' + esc(e.key) + '"><span>' + esc(e.title) + '</span><span class="muted small">' +
        done + "/" + kids.length + " done</span><span class=\"progress\"><i style=\"width:" + pct + '%"></i></span></button>';
    }).join("") || '<p class="muted small">No epics yet. Create one to group related work.</p>') + "</aside>";
    v.innerHTML = '<div class="backlog"><div class="bl-main">' + active.map(section).join("") + future.map(section).join("") + section(null) + "</div>" + epicPanel + "</div>";
  }

  /* ---------- list ---------- */
  const LIST_COLS = [["key", "Key"], ["title", "Summary"], ["type", "Type"], ["status", "Status"], ["priority", "Priority"],
    ["assignee", "Assignees"], ["sprint", "Sprint"], ["points", "Points"], ["due", "Due"], ["updated_at", "Updated"]];
  function sortValue(it, k) {
    if (k === "key") return it.number;
    if (k === "priority") return PRIORITIES.indexOf(it.priority);
    if (k === "status") return S.space.statuses.findIndex(s => s.name === it.status);
    if (k === "assignee") return it.assignee_ids.map(uname).join(", ").toLowerCase();
    if (k === "sprint") return sprintName(it.sprint_id).toLowerCase();
    if (k === "points") return it.points == null ? -1 : it.points;
    return String(it[k] || "").toLowerCase();
  }
  function viewList(v) {
    let { items, ordered } = filtered(S.items.slice());
    if (!ordered) items.sort((a, b) => { const x = sortValue(a, S.sortK), y = sortValue(b, S.sortK); return (x < y ? -1 : x > y ? 1 : 0) * S.sortDir; });
    const sel = S.selected, all = items.length && items.every(i => sel.has(i.key));
    let html = '<div id="bulkBar"></div><div class="table-wrap"><table class="tbl"><thead><tr><th class="cb"><input type="checkbox" data-change="selAll" aria-label="Select all"' + (all ? " checked" : "") + "></th>" +
      LIST_COLS.map(([k, l]) => '<th><button class="th-btn" data-act="sort" data-k="' + k + '">' + l + (S.sortK === k && !ordered ? (S.sortDir > 0 ? " ↑" : " ↓") : "") + "</button></th>").join("") + "</tr></thead><tbody>";
    html += items.map(it => '<tr class="' + (sel.has(it.key) ? "sel" : "") + '"><td class="cb"><input type="checkbox" data-change="sel" data-key="' + esc(it.key) + '"' + (sel.has(it.key) ? " checked" : "") + ' aria-label="Select ' + esc(it.key) + '"></td>' +
      '<td><button class="k linkish" data-act="open" data-key="' + esc(it.key) + '">' + esc(it.key) + "</button></td>" +
      '<td class="t"><button class="linkish" data-act="open" data-key="' + esc(it.key) + '">' + esc(it.title) + "</button></td>" +
      "<td>" + typeIcon(it.type) + " " + esc(it.type) + "</td><td>" + statusPill(it.status) + "</td><td>" + priIcon(it.priority) + " " + esc(it.priority) + "</td>" +
      "<td>" + (it.assignee_ids.length ? it.assignee_ids.map(uname).map(esc).join(", ") : '<span class="muted">Unassigned</span>') + "</td>" +
      "<td>" + esc(sprintName(it.sprint_id)) + "</td><td>" + (it.points != null ? it.points : "") + "</td>" +
      '<td class="' + (it.due && it.due < today() && !isDone(it) ? "late-t" : "") + '">' + fmtDay(it.due) + "</td><td>" + ago(it.updated_at) + "</td></tr>").join("");
    html += "</tbody></table></div>";
    html += '<div class="list-foot"><span class="muted">' + items.length + " of " + S.items.length + ' work items</span><span class="grow"></span>' +
      '<a class="btn ghost sm" href="' + API.fileUrl("/api/spaces/" + S.space.key + "/export.csv") + '" download>Export CSV</a></div>';
    if (!items.length) html = emptyState(S.items.length ? "Nothing matches this filter" : "No work items yet",
      S.items.length ? "Change or clear the filter to see more." : "Create the first one to get started.",
      S.items.length ? '<button class="btn ghost" data-act="applyFilter" data-q="">Clear filter</button>' : '<button class="btn" data-act="openCreate">Create</button>');
    v.innerHTML = html;
    renderBulk();
  }
  /* The bulk bar updates on its own so ticking a checkbox never rebuilds the table (keeps focus and scroll). */
  function renderBulk() {
    const box = $("#bulkBar");
    if (!box) return;
    const sel = S.selected;
    if (!sel.size || !canEdit()) { box.innerHTML = ""; return; }
    const sprints = S.sprints.filter(s => s.state !== "closed");
    box.innerHTML = '<div class="bulk"><strong>' + sel.size + " selected</strong>" +
      '<select data-change="bulk" data-field="status" aria-label="Set status"><option value="">Status</option>' + S.space.statuses.map(s => opt(s.name, s.name)).join("") + "</select>" +
      '<select data-change="bulk" data-field="priority" aria-label="Set priority"><option value="">Priority</option>' + PRIORITIES.map(p => opt(p, p)).join("") + "</select>" +
      '<select data-change="bulk" data-field="assignee_ids" aria-label="Set assignee"><option value="">Assignee</option>' + opt("[]", "Unassigned") + S.members.map(m => opt("[" + m.id + "]", m.name)).join("") + "</select>" +
      '<select data-change="bulk" data-field="sprint_id" aria-label="Move to sprint"><option value="">Sprint</option>' + opt("backlog", "Backlog") + sprints.map(s => opt(s.id, s.name)).join("") + "</select>" +
      '<button class="btn ghost sm danger" data-act="bulkDelete">Delete</button><button class="btn ghost sm" data-act="clearSel">Clear</button></div>';
  }

  /* ---------- timeline ---------- */
  function viewTimeline(v) {
    const { items } = filtered(S.items.slice());
    const dated = items.filter(i => i.start || i.due);
    const epics = S.items.filter(i => i.type === "Epic");
    if (!dated.length) {
      v.innerHTML = emptyState("Nothing scheduled yet", "Add a start or due date to work items to place them on the timeline.", "");
      return;
    }
    const days = dated.flatMap(i => [i.start, i.due].filter(Boolean)).concat([today()]).sort();
    const start = new Date(days[0] + "T00:00:00"); start.setDate(start.getDate() - 3);
    const end = new Date(days[days.length - 1] + "T00:00:00"); end.setDate(end.getDate() + 7);
    const span = Math.max(1, (end - start) / 864e5);
    const pos = d => (((new Date(d + "T00:00:00") - start) / 864e5) / span) * 100;
    let ticks = "";
    const m = new Date(start.getFullYear(), start.getMonth() + 1, 1);
    while (m < end) { ticks += '<span class="tick-m" style="left:' + pos(OQL.isoDay(m)) + '%">' + MONTHS[m.getMonth()] + "</span>"; m.setMonth(m.getMonth() + 1); }
    const todayPos = pos(today());
    const bar = it => {
      const s = it.start || it.due, e = it.due || it.start;
      const left = pos(s), width = Math.max(1.2, pos(e) - left + 100 / span);
      return '<div class="tl-row"><button class="tl-label linkish" data-act="open" data-key="' + esc(it.key) + '">' + typeIcon(it.type) + " " + esc(it.key) + " " + esc(it.title) + "</button>" +
        '<div class="tl-track"><span class="tl-today" style="left:' + todayPos + '%"></span><button class="tl-bar cat-' + cat(it.status) + '" data-act="open" data-key="' + esc(it.key) + '" style="left:' + left + "%;width:" + width + '%" title="' + esc(it.title + " " + fmtDay(s) + " to " + fmtDay(e)) + '"></button></div></div>';
    };
    let rows = "";
    const shown = new Set();
    epics.forEach(e => {
      const kids = dated.filter(i => i.parent_key === e.key);
      if (!kids.length && !(e.start || e.due)) return;
      rows += '<div class="tl-group">' + esc(e.title) + "</div>";
      if (e.start || e.due) { rows += bar(e); shown.add(e.key); }
      kids.forEach(k => { rows += bar(k); shown.add(k.key); });
    });
    const rest = dated.filter(i => !shown.has(i.key));
    if (rest.length) rows += '<div class="tl-group">Other work</div>' + rest.map(bar).join("");
    v.innerHTML = '<div class="tl"><div class="tl-row tl-head"><span class="tl-label"></span><div class="tl-track">' + ticks +
      '<span class="tl-today" style="left:' + pos(today()) + '%" title="Today"></span></div></div>' + rows + "</div>";
  }

  /* ---------- calendar ---------- */
  function viewCalendar(v) {
    if (!S.calMonth) { const d = new Date(); S.calMonth = new Date(d.getFullYear(), d.getMonth(), 1); }
    const m = S.calMonth, { items } = filtered(S.items.filter(i => i.due));
    const first = new Date(m.getFullYear(), m.getMonth(), 1), offset = (first.getDay() + 6) % 7;
    const daysIn = new Date(m.getFullYear(), m.getMonth() + 1, 0).getDate();
    let html = '<div class="toolbar"><button class="btn ghost sm" data-act="calNav" data-d="-1" aria-label="Previous month">‹</button><strong class="cal-title">' +
      MONTHS[m.getMonth()] + " " + m.getFullYear() + '</strong><button class="btn ghost sm" data-act="calNav" data-d="1" aria-label="Next month">›</button>' +
      '<button class="btn ghost sm" data-act="calNav" data-d="0">Today</button></div><div class="cal">' +
      ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => '<div class="cal-h">' + d + "</div>").join("");
    for (let i = 0; i < offset; i++) html += '<div class="cal-d off"></div>';
    for (let d = 1; d <= daysIn; d++) {
      const iso = OQL.isoDay(new Date(m.getFullYear(), m.getMonth(), d));
      const due = items.filter(i => i.due === iso);
      const marks = S.sprints.filter(s => s.start === iso || s.end === iso).map(s => '<span class="cal-sprint">' + esc(s.name) + (s.start === iso ? " starts" : " ends") + "</span>").join("");
      html += '<div class="cal-d' + (iso === today() ? " is-today" : "") + '"><span class="cal-n">' + d + "</span>" + marks +
        due.map(i => '<button class="cal-i cat-' + cat(i.status) + '" data-act="open" data-key="' + esc(i.key) + '" title="' + esc(i.title) + '">' + esc(i.key) + " " + esc(i.title) + "</button>").join("") + "</div>";
    }
    v.innerHTML = html + "</div>";
  }

  /* ---------- reports ---------- */
  function viewReports(v) {
    const key = S.space.key;
    const open = S.items.filter(i => !isDone(i));
    const blocked = blockedSet();
    const est = S.items.reduce((a, i) => a + (i.estimate || 0), 0), logged = S.items.reduce((a, i) => a + (i.logged || 0), 0);
    const tiles = [["Open work items", open.length], ["Open bugs", open.filter(i => i.type === "Bug").length],
      ["Overdue", open.filter(i => i.due && i.due < today()).length], ["Blocked", open.filter(i => blocked.has(i.key)).length],
      ["Hours logged / estimated", logged.toFixed(1) + " / " + est.toFixed(1)]];
    const sprints = S.sprints.filter(s => s.state !== "future");
    const chosen = S.reportSprint || (activeSprint() || sprints[sprints.length - 1] || {}).id;
    const load = {};
    open.forEach(i => (i.assignee_ids.length ? i.assignee_ids : [0]).forEach(u => { load[u] = (load[u] || 0) + (i.points || 0); }));
    const loadIds = Object.keys(load);
    v.innerHTML = '<div class="tiles">' + tiles.map(([l, n]) => '<div class="tile"><span class="tile-n">' + n + '</span><span class="tile-l">' + l + "</span></div>").join("") + "</div>" +
      '<div class="reports">' +
      '<section class="rep"><header><h3>Sprint burndown</h3>' + (sprints.length ? '<select data-change="reportSprint" aria-label="Sprint">' + sprints.map(s => opt(s.id, s.name, s.id === chosen)).join("") + "</select>" : "") + '</header><div id="r-burn" class="rep-b muted">Loading…</div></section>' +
      '<section class="rep"><header><h3>Velocity</h3></header><div id="r-vel" class="rep-b muted">Loading…</div></section>' +
      '<section class="rep"><header><h3>Cumulative flow, 30 days</h3></header><div id="r-cfd" class="rep-b muted">Loading…</div></section>' +
      '<section class="rep"><header><h3>Created vs resolved, 30 days</h3></header><div id="r-cvr" class="rep-b muted">Loading…</div></section>' +
      '<section class="rep"><header><h3>Cycle time, last 60 days</h3></header><div id="r-ct" class="rep-b muted">Loading…</div></section>' +
      '<section class="rep"><header><h3>Open points by assignee</h3></header><div class="rep-b">' +
      (loadIds.length ? Charts.bars({ labels: loadIds.map(u => (u === "0" ? "Unassigned" : uname(+u))), series: [{ name: "Open points", values: loadIds.map(u => load[u]) }] }) : '<p class="muted">No open work.</p>') +
      "</div></section></div>";
    const put = (id, html) => { const el = document.getElementById(id); if (el && S.view === "reports" && S.space && S.space.key === key) { el.classList.remove("muted"); el.innerHTML = html; } };
    const base = "/api/spaces/" + key + "/reports/";
    if (chosen) API.get(base + "burndown?sprint_id=" + chosen).then(r => put("r-burn", r.sprint ? Charts.line({ labels: r.days, title: "Burndown",
      series: [{ name: "Remaining", values: r.remaining }, { name: "Ideal", values: r.ideal, dash: true, cls: "c5" }, { name: "Completed", values: r.completed, cls: "c2" }] }) : "No sprint data.")).catch(e => put("r-burn", esc(e.message)));
    else put("r-burn", "Start a sprint to see its burndown.");
    API.get(base + "velocity").then(r => put("r-vel", r.sprints.length ? Charts.bars({ labels: r.sprints.map(s => s.name), title: "Velocity",
      series: [{ name: "Committed", values: r.sprints.map(s => s.committed), cls: "c5" }, { name: "Completed", values: r.sprints.map(s => s.completed) }] }) +
      '<p class="muted small">Average completed: ' + r.average + " points</p>" : "Complete a sprint to see velocity.")).catch(e => put("r-vel", esc(e.message)));
    API.get(base + "cfd?days=30").then(r => put("r-cfd", Charts.stacked({ labels: r.days, title: "Cumulative flow",
      series: r.series.map((s, i) => ({ name: s.status, values: s.values, cls: "c" + (i % 8) })) }))).catch(e => put("r-cfd", esc(e.message)));
    API.get(base + "created-vs-resolved?days=30").then(r => put("r-cvr", Charts.line({ labels: r.days, title: "Created vs resolved",
      series: [{ name: "Created", values: r.created, cls: "c3" }, { name: "Resolved", values: r.resolved, cls: "c2" }] }))).catch(e => put("r-cvr", esc(e.message)));
    API.get(base + "cycle-time?days=60").then(r => {
      if (!r.points.length) return put("r-ct", "Finish some work to see cycle time.");
      const labels = [], d0 = new Date(); d0.setDate(d0.getDate() - 59);
      for (let i = 0; i < 60; i++) { const d = new Date(d0); d.setDate(d0.getDate() + i); labels.push(OQL.isoDay(d)); }
      put("r-ct", Charts.scatter({ labels, points: r.points.map(p => ({ x: OQL.isoDay(new Date(ts(p.resolved))), y: p.days, label: p.key })), avg: r.average, title: "Cycle time" }) +
        '<p class="muted small">Median ' + r.median + " days across " + r.points.length + " items</p>");
    }).catch(e => put("r-ct", esc(e.message)));
  }

  /* ---------- activity ---------- */
  function describe(a) {
    const k = '<a href="#/item/' + esc(a.key) + '">' + esc(a.key) + "</a>";
    switch (a.field) {
      case "created": return "created " + k;
      case "deleted": return "deleted " + esc(a.key) + " (" + esc(a.old) + ")";
      case "comment": return "commented on " + k + ': <span class="muted">' + esc(a.new) + "</span>";
      case "attachment": return (a.new ? "attached " + esc(a.new) + " to " : "removed " + esc(a.old) + " from ") + k;
      case "worklog": return "logged " + esc(a.new) + " on " + k;
      case "link": return (a.new ? "linked " + k + " " + esc(a.new) : "removed link " + esc(a.old) + " from " + k);
      case "description": return "edited the description of " + k;
      default: return "changed " + esc(a.field) + " of " + k + (a.old ? " from <b>" + esc(a.old) + "</b>" : "") + (a.new ? " to <b>" + esc(a.new) + "</b>" : "");
    }
  }
  function viewActivity(v) {
    v.innerHTML = '<p class="muted">Loading…</p>';
    const key = S.space.key;
    API.get("/api/spaces/" + key + "/activity?limit=100").then(rows => {
      if (S.view !== "activity" || S.space.key !== key) return;
      v.innerHTML = rows.length ? '<ol class="feed">' + rows.map(a => '<li><span class="av-wrap">' + esc(initials(a.actor)) + "</span><div><b>" + esc(a.actor) + "</b> " + describe(a) +
        '<div class="muted small">' + ago(a.at) + "</div></div></li>").join("") + "</ol>" : emptyState("No activity yet", "Changes to work items will show up here.", "");
    }).catch(fail);
  }

  /* ---------- work item dialog ---------- */
  async function openItem(key) {
    S.openKey = key;
    S.descEdit = false; S.descPreview = false; S.editComment = null;
    const dlg = $("#dlg");
    dlg.innerHTML = '<div class="dlg-load">Loading ' + esc(key) + "…</div>";
    if (!dlg.open) dlg.showModal();
    try {
      S.detail = await API.get("/api/items/" + encodeURIComponent(key));
      if (S.openKey !== key) return;
      upsert(S.detail.item);
      renderDialog();
    } catch (e) {
      fail(e);
      closeDialog();
    }
  }
  async function refreshDetail() {
    if (!S.openKey) return;
    const key = S.openKey;
    try {
      const d = await API.get("/api/items/" + encodeURIComponent(key));
      if (S.openKey !== key) return;
      S.detail = d;
      upsert(d.item);
      renderDialog();
    } catch (e) { if (e.status === 404) { toast(key + " was deleted."); removeItem(key); closeDialog(); renderView(); } }
  }
  function applyDetail(d) { S.detail = d; upsert(d.item); renderDialog(); renderView(); }

  function closeDialog(fromRoute) {
    const dlg = $("#dlg");
    if (dlg.open) dlg.close();
    const wasOpen = S.openKey;
    S.openKey = null; S.detail = null;
    if (!fromRoute && wasOpen && /^#\/item\//.test(location.hash) && S.space) {
      history.replaceState(null, "", "#/s/" + S.space.key + "/" + (VIEWS.some(v => v[0] === S.view) ? S.view : "board"));
    }
  }

  const mdCtx = () => ({ handles: new Set(S.members.map(m => m.handle.toLowerCase())), keys: new Set(Object.keys(S.byKey)) });
  const editing = () => { const a = document.activeElement; return a && $("#dlg").contains(a) && (a.tagName === "TEXTAREA" || (a.tagName === "INPUT" && a.type === "text")); };

  function renderDialog() {
    const d = S.detail;
    if (!d) return;
    const it = d.item, ro = !canEdit(), dis = ro ? " disabled" : "";
    const me = S.me.id, watching = it.watcher_ids.includes(me);
    const sprints = S.sprints.filter(s => s.state !== "closed" || s.id === it.sprint_id);
    const parents = S.items.filter(i => i.key !== it.key && (it.type === "Subtask" ? i.type !== "Subtask" : i.type === "Epic") && i.parent_key !== it.key);
    const assignable = S.members.filter(m => !it.assignee_ids.includes(m.id));
    const cl = it.checklist || [], doneN = cl.filter(c => c.done).length;
    const field = (label, html) => '<div class="fld"><span class="fld-l">' + label + "</span>" + html + "</div>";
    const desc = S.descEdit
      ? '<div class="md-edit"><div class="tabs"><button class="tab' + (!S.descPreview ? " on" : "") + '" data-act="descTab" data-p="0">Write</button><button class="tab' + (S.descPreview ? " on" : "") + '" data-act="descTab" data-p="1">Preview</button><span class="grow"></span><span class="muted small">Markdown: **bold**, `code`, - [ ] task, @mention, KEY-12</span></div>' +
        (S.descPreview ? '<div class="md prev">' + (MD.render(S.descDraft, mdCtx()) || '<p class="muted">Nothing to preview.</p>') + "</div>"
          : '<textarea id="descBox" class="md-box" data-mention data-draft="description" rows="10" placeholder="Describe the work. Markdown works here.">' + esc(readDraft("description") || S.descDraft) + "</textarea>") +
        '<div class="row-actions"><button class="btn sm" data-act="saveDesc">Save</button><button class="btn ghost sm" data-act="cancelDesc">Cancel</button><span class="muted small">Ctrl Enter saves</span></div></div>'
      : '<div class="md desc' + (ro ? "" : " editable") + '"' + (ro ? "" : ' data-act="editDesc" tabindex="0" title="Click to edit"') + ">" +
        (it.description ? MD.render(it.description, mdCtx()) : '<p class="muted">' + (ro ? "No description." : "Add a description…") + "</p>") + "</div>";
    const tabs = [["comments", "Comments (" + d.comments.length + ")"], ["history", "History"], ["worklog", "Time (" + it.logged + "h)"]];
    let tabBody = "";
    if (S.dtab === "comments") {
      tabBody = d.comments.map(c => '<div class="cmt"><div class="cmt-h">' + avatar(c.author_id, "sm") + "<b>" + esc(c.author) + '</b><span class="muted small">' + ago(c.created_at) + (c.edited_at ? " (edited)" : "") + "</span>" +
        ((c.author_id === me || isAdmin()) && !ro ? '<span class="grow"></span><button class="linkish small" data-act="editComment" data-id="' + c.id + '">Edit</button><button class="linkish small danger" data-act="deleteComment" data-id="' + c.id + '">Delete</button>' : "") + "</div>" +
        (S.editComment === c.id ? '<textarea class="md-box" id="cEdit" data-mention rows="4">' + esc(c.body) + '</textarea><div class="row-actions"><button class="btn sm" data-act="saveComment" data-id="' + c.id + '">Save</button><button class="btn ghost sm" data-act="cancelComment">Cancel</button></div>'
          : '<div class="md">' + MD.render(c.body, mdCtx()) + "</div>") + "</div>").join("") +
        (ro ? "" : '<div class="cmt-new"><textarea id="cBody" class="md-box" data-mention data-draft="comment" rows="3" placeholder="Add a comment. Use @ to mention someone. Ctrl Enter posts.">' + esc(readDraft("comment")) + '</textarea>' +
          (readDraft("comment") ? '<p class="muted small">Unsent draft restored.</p>' : "") +
          '<div class="row-actions"><button class="btn sm" data-act="addComment">Comment</button></div></div>');
    } else if (S.dtab === "history") {
      tabBody = d.history.map(h => '<div class="hist"><b>' + esc(h.actor) + "</b> " + (h.field === "created" ? "created this in <b>" + esc(h.new) + "</b>" :
        h.field === "comment" ? "commented" : h.field === "description" ? "edited the description" :
        "changed " + esc(h.field) + (h.old ? ' from <span class="old">' + esc(h.old) + "</span>" : "") + (h.new ? " to <b>" + esc(h.new) + "</b>" : "")) +
        '<span class="muted small"> ' + ago(h.at) + "</span></div>").join("") || '<p class="muted">No history yet.</p>';
    } else {
      tabBody = (ro ? "" : '<div class="wl-form"><input id="wlHours" type="number" min="0.25" max="24" step="0.25" placeholder="Hours" aria-label="Hours"><input id="wlDay" type="date" value="' + today() + '" aria-label="Day"><input id="wlNote" placeholder="What did you do?" aria-label="Note"><button class="btn sm" data-act="logWork">Log time</button></div>') +
        '<p class="muted small">Estimated ' + (it.estimate || 0) + "h, logged " + it.logged + "h" + (it.estimate ? ", remaining " + Math.max(0, it.estimate - it.logged).toFixed(2) + "h" : "") + "</p>" +
        d.worklogs.map(w => '<div class="hist"><b>' + esc(w.user) + "</b> logged <b>" + w.hours + "h</b> on " + fmtDay(w.day) + (w.note ? ': <span class="muted">' + esc(w.note) + "</span>" : "") +
          (w.user_id === me || isAdmin() ? ' <button class="x" data-act="deleteWorklog" data-id="' + w.id + '" aria-label="Remove time entry">×</button>' : "") + "</div>").join("");
    }
    const html =
      '<header class="dlg-h">' +
      '<select class="type-sel" data-change="field" data-field="type" aria-label="Type"' + dis + ">" + TYPES.map(t => opt(t, TYPE_ICON[t] + " " + t, t === it.type)).join("") + "</select>" +
      (it.parent_key ? '<a class="muted small" href="#/item/' + esc(it.parent_key) + '">' + esc(it.parent_key) + "</a><span class=\"muted\">/</span>" : "") +
      '<span class="k">' + esc(it.key) + "</span>" + (it.external_key && it.external_key !== it.key ? '<span class="muted small">was ' + esc(it.external_key) + "</span>" : "") +
      '<span class="grow"></span>' +
      '<button class="btn ghost sm" data-act="watch" aria-pressed="' + watching + '">' + (watching ? "Watching" : "Watch") + "</button>" +
      '<button class="btn ghost sm" data-act="mute" aria-pressed="' + d.muted + '" title="Stop all notifications about this item">' + (d.muted ? "Muted" : "Mute") + "</button>" +
      '<button class="btn ghost sm" data-act="copyLink">Copy link</button>' +
      (ro ? "" : '<button class="btn ghost sm" data-act="cloneItem">Clone</button><button class="btn ghost sm danger" data-act="deleteItem">Delete</button>') +
      '<button class="x big" data-act="closeDlg" aria-label="Close">×</button></header>' +
      '<div class="dlg-b"><div class="dlg-title"><input class="title-in" data-change="field" data-field="title" value="' + esc(it.title) + '" aria-label="Summary"' + dis + "></div>" +
      '<div class="dlg-main"><h4>Description</h4>' + desc +
      '<h4>Checklist <span class="muted small">' + (cl.length ? doneN + "/" + cl.length : "") + "</span></h4>" +
      (cl.length ? '<div class="progress"><i style="width:' + Math.round((doneN / cl.length) * 100) + '%"></i></div>' : "") +
      '<ul class="checklist">' + cl.map((c, i) => '<li><label><input type="checkbox" data-change="check" data-i="' + i + '"' + (c.done ? " checked" : "") + dis + "> " +
        '<span class="' + (c.done ? "struck" : "") + '">' + esc(c.text) + "</span></label>" + (ro ? "" : '<button class="x" data-act="uncheck" data-i="' + i + '" aria-label="Remove">×</button>') + "</li>").join("") + "</ul>" +
      (ro ? "" : '<input class="quick" data-quick="check" placeholder="+ Add checklist item" aria-label="Add checklist item">') +
      '<h4>' + (it.type === "Epic" ? "Work in this epic" : "Child items") + "</h4>" +
      d.children.map(c => '<div class="mini"><a href="#/item/' + esc(c.key) + '">' + typeIcon(c.type) + " " + esc(c.key) + "</a> " + esc(c.title) + " " + statusPill(c.status) + "</div>").join("") +
      (ro ? "" : '<input class="quick" data-quick="child" placeholder="+ Add ' + (it.type === "Epic" ? "a story to this epic" : "a subtask") + '" aria-label="Add child item">') +
      "<h4>Links</h4>" +
      d.links.map(l => '<div class="mini"><span class="muted">' + esc(l.label) + '</span> <a href="#/item/' + esc(l.key) + '">' + esc(l.key) + "</a> " + esc(l.title) + " " + statusPill(l.status) +
        (ro ? "" : ' <button class="x" data-act="unlink" data-id="' + l.id + '" aria-label="Remove link">×</button>') + "</div>").join("") +
      (ro ? "" : '<div class="link-form"><select id="linkType" aria-label="Link type">' + LINK_TYPES.map(t => opt(t, t)).join("") + '</select><input id="linkKey" list="keyList" placeholder="Work item key, like ' + esc(S.space.key) + '-12" aria-label="Work item to link"><datalist id="keyList">' +
        S.items.filter(i => i.key !== it.key).slice(0, 400).map(i => '<option value="' + esc(i.key) + '">' + esc(i.title) + "</option>").join("") + '</datalist><button class="btn ghost sm" data-act="addLink">Link</button></div>') +
      '<h4>Attachments</h4><div class="atts">' + d.attachments.map(a => '<div class="att">' +
        (a.content_type.startsWith("image/") && !a.content_type.includes("svg") ? '<a href="' + API.fileUrl("/api/attachments/" + a.id) + '" target="_blank" rel="noopener"><img src="' + API.fileUrl("/api/attachments/" + a.id) + '" alt="' + esc(a.filename) + '"></a>' : '<span class="att-ico">📄</span>') +
        '<a href="' + API.fileUrl("/api/attachments/" + a.id) + '" target="_blank" rel="noopener">' + esc(a.filename) + '</a><span class="muted small">' + fmtSize(a.size) + ", " + esc(a.uploaded_by) + "</span>" +
        (ro ? "" : '<button class="x" data-act="deleteAtt" data-id="' + a.id + '" aria-label="Delete ' + esc(a.filename) + '">×</button>') + "</div>").join("") + "</div>" +
      (ro ? "" : '<label class="dropzone" data-filedrop>Drop files here or <u>browse</u><input type="file" multiple data-change="upload" hidden></label>') +
      '<div class="tabs act-tabs">' + tabs.map(([k, l]) => '<button class="tab' + (S.dtab === k ? " on" : "") + '" data-act="dtab" data-t="' + k + '">' + l + "</button>").join("") + "</div>" +
      '<div class="tab-b">' + tabBody + "</div>" +
      "</div>" +
      '<aside class="dlg-side">' +
      field("Status", '<select data-change="field" data-field="status" class="status-sel cat-' + cat(it.status) + '"' + dis + ">" + S.space.statuses.map(s => opt(s.name, s.name, s.name === it.status)).join("") + "</select>") +
      field("Assignees", '<div class="chips">' + it.assignee_ids.map(id => '<span class="chip user">' + avatar(id, "sm") + esc(uname(id)) + (ro ? "" : '<button class="x" data-act="unassign" data-id="' + id + '" aria-label="Remove ' + esc(uname(id)) + '">×</button>') + "</span>").join("") +
        (ro || !assignable.length ? "" : '<select data-change="assign" aria-label="Add assignee"><option value="">+ Add</option>' + assignable.map(m => opt(m.id, m.name)).join("") + "</select>") +
        (!ro && !it.assignee_ids.includes(me) && S.members.some(m => m.id === me) ? '<button class="linkish small" data-act="assignMe">Assign to me</button>' : "") + "</div>") +
      field("Reporter", '<select data-change="field" data-field="reporter_id"' + dis + ">" + opt("", "None", !it.reporter_id) + S.members.map(m => opt(m.id, m.name, m.id === it.reporter_id)).join("") + "</select>") +
      field("Priority", '<select data-change="field" data-field="priority"' + dis + ">" + PRIORITIES.map(p => opt(p, PRI_ICON[p] + " " + p, p === it.priority)).join("") + "</select>") +
      field("Sprint", '<select data-change="field" data-field="sprint_id"' + dis + ">" + opt("", "Backlog", it.sprint_id == null) + sprints.map(s => opt(s.id, s.name + (s.state === "active" ? " (active)" : s.state === "closed" ? " (completed)" : ""), s.id === it.sprint_id)).join("") + "</select>") +
      field(it.type === "Subtask" ? "Parent" : "Epic", '<select data-change="field" data-field="parent_key"' + dis + ">" + opt("", "None", !it.parent_key) + parents.map(p => opt(p.key, p.key + " " + p.title, p.key === it.parent_key)).join("") + "</select>") +
      field("Labels", '<input data-change="labels" value="' + esc(it.labels.join(", ")) + '" placeholder="Comma separated" aria-label="Labels"' + dis + ">") +
      field("Story points", '<input type="number" min="0" step="0.5" data-change="field" data-field="points" value="' + (it.points != null ? it.points : "") + '" aria-label="Story points"' + dis + ">") +
      field("Estimate (hours)", '<input type="number" min="0" step="0.5" data-change="field" data-field="estimate" value="' + (it.estimate != null ? it.estimate : "") + '" aria-label="Estimate in hours"' + dis + ">") +
      field("Start date", '<input type="date" data-change="field" data-field="start" value="' + (it.start || "") + '" aria-label="Start date"' + dis + ">") +
      field("Due date", '<input type="date" data-change="field" data-field="due" value="' + (it.due || "") + '" aria-label="Due date"' + dis + ">") +
      (S.fields || []).map(f => field(esc(f.name), customInput(f, (it.custom || {})[f.key], dis))).join("") +
      '<div class="stamps muted small">Created ' + ago(it.created_at) + "<br>Updated " + ago(it.updated_at) + (it.resolved_at ? "<br>Resolved " + ago(it.resolved_at) : "") +
      "<br>Watchers: " + (it.watcher_ids.map(uname).map(esc).join(", ") || "none") + "</div>" +
      "</aside></div>";
    const dlg = $("#dlg");
    const keep = [".dlg-main", ".dlg-b"].map(sel => { const el = dlg.querySelector(sel); return [sel, el ? el.scrollTop : 0]; });
    dlg.innerHTML = html;
    keep.forEach(([sel, top]) => { const el = dlg.querySelector(sel); if (el) el.scrollTop = top; });
    if (S.descEdit && !S.descPreview) { const box = $("#descBox"); if (box) { box.focus(); box.setSelectionRange(box.value.length, box.value.length); } }
    if (S.editComment) { const box = $("#cEdit"); if (box) box.focus(); }
  }

  async function itemAction(path, body, method) {
    try {
      const d = method === "DELETE" ? await API.del(path) : await API.post(path, body || {});
      applyDetail(d);
      return d;
    } catch (e) { fail(e); }
  }

  /* ---------- quick create syntax: "Fix login @kiran !high #web ~3", optional "bug:" prefix ---------- */
  function findMember(h) {
    const q = h.toLowerCase();
    return S.members.find(m => m.handle.toLowerCase() === q) || S.members.find(m => m.handle.toLowerCase().startsWith(q)) ||
      S.members.find(m => m.name.toLowerCase().replace(/\s+/g, ".").startsWith(q) || m.name.toLowerCase().split(/\s+/)[0] === q);
  }
  function parseQuick(text) {
    const out = { assignee_ids: [], labels: [] };
    let t = " " + text;
    t = t.replace(/(\s)@([\w.-]+)/g, (m, pre, h) => { const u = findMember(h); if (u) { if (!out.assignee_ids.includes(u.id)) out.assignee_ids.push(u.id); return pre; } return m; });
    t = t.replace(/(\s)!(highest|high|medium|low)\b/gi, (m, pre, p) => { out.priority = p[0].toUpperCase() + p.slice(1).toLowerCase(); return pre; });
    t = t.replace(/(\s)#([\w-]+)/g, (m, pre, l) => { out.labels.push(l); return pre; });
    t = t.replace(/(\s)~(\d+(?:\.\d+)?)(?=\s|$)/g, (m, pre, n) => { out.points = +n; return pre; });
    const tm = t.match(/^\s*(bug|story|task|epic|subtask):\s*/i);
    if (tm) { out.type = tm[1][0].toUpperCase() + tm[1].slice(1).toLowerCase(); t = t.slice(tm[0].length); }
    out.title = t.replace(/\s+/g, " ").trim();
    if (!out.labels.length) delete out.labels;
    return out;
  }
  function similar(title) {
    const words = title.toLowerCase().split(/\W+/).filter(w => w.length > 3);
    if (words.length < 2) return [];
    return S.items.map(i => { const t = i.title.toLowerCase(); return [words.filter(w => t.includes(w)).length / words.length, i]; })
      .filter(([s]) => s >= 0.6).sort((a, b) => b[0] - a[0]).slice(0, 3).map(x => x[1]);
  }

  async function createItem(data, silent) {
    try {
      const it = await API.post("/api/spaces/" + S.space.key + "/items", data);
      upsert(it);
      renderView();
      if (!silent) toast("Created " + it.key, "Open", () => go("#/item/" + it.key));
      return it;
    } catch (e) { fail(e); }
  }

  async function quickCreate(input) {
    const text = input.value.trim();
    if (!text) return;
    const kind = input.dataset.quick;
    if (kind === "check") {
      const it = S.detail.item;
      input.value = "";
      return saveItem(it.key, { checklist: (it.checklist || []).concat([{ text, done: false }]) });
    }
    const data = parseQuick(text);
    if (!data.title) return toast("Add a summary before the shortcuts.");
    if (kind === "board") { const sp = activeSprint(); if (sp && (S.space.settings || {}).template !== "kanban") data.sprint_id = sp.id; }
    if (kind === "child") {
      const parent = S.detail.item;
      data.parent_key = parent.key;
      data.type = data.type || (parent.type === "Epic" ? "Story" : "Subtask");
      if (parent.sprint_id && !data.sprint_id) data.sprint_id = parent.sprint_id;
    }
    input.value = "";
    const it = await createItem(data, kind === "child");
    if (it && kind === "child") refreshDetail();
    const again = $$('[data-quick="' + kind + '"]')[0];
    if (again) again.focus();
  }

  function openCreate(prefill) {
    if (!S.space) return go("#/new-space");
    if (!canEdit()) return toast("You have view-only access to " + S.space.key + ".");
    const sp = activeSprint();
    const epics = S.items.filter(i => i.type === "Epic");
    const m = $("#modal");
    m.innerHTML = '<form class="mform" data-form="create"><h2>Create work item</h2>' +
      '<label>Summary<input name="title" required autocomplete="off" data-input="dupes" placeholder="Fix login timeout @name !high #web ~3" value="' + esc(prefill || "") + '"></label>' +
      '<div id="dupes" class="dupes"></div>' +
      '<div class="grid2"><label>Type<select name="type">' + TYPES.map(t => opt(t, t, t === "Task")).join("") + "</select></label>" +
      '<label>Priority<select name="priority">' + PRIORITIES.map(p => opt(p, p, p === "Medium")).join("") + "</select></label>" +
      '<label>Assignee<select name="assignee">' + opt("", "Unassigned") + S.members.map(u => opt(u.id, u.name, false)).join("") + "</select></label>" +
      '<label>Sprint<select name="sprint_id">' + opt("", "Backlog") + S.sprints.filter(s => s.state !== "closed").map(s => opt(s.id, s.name + (s.state === "active" ? " (active)" : ""), sp && s.id === sp.id && S.view === "board")).join("") + "</select></label>" +
      '<label>Epic<select name="parent_key">' + opt("", "None") + epics.map(e => opt(e.key, e.key + " " + e.title)).join("") + "</select></label>" +
      '<label>Story points<input name="points" type="number" min="0" step="0.5"></label></div>' +
      '<label>Description<textarea name="description" rows="5" data-mention placeholder="Markdown works here"></textarea></label>' +
      '<p class="form-err" role="alert"></p><div class="row-actions"><label class="inline"><input type="checkbox" name="another"> Create another</label><span class="grow"></span>' +
      '<button type="button" class="btn ghost" data-act="closeModal">Cancel</button><button class="btn" type="submit">Create</button></div></form>';
    m.showModal();
    m.querySelector('[name="title"]').focus();
  }

  async function submitCreate(form) {
    const f = Object.fromEntries(new FormData(form).entries());
    const quick = parseQuick(f.title || "");
    if (!quick.title) { form.querySelector(".form-err").textContent = "Enter a summary."; return; }
    const data = { title: quick.title, type: quick.type || f.type, priority: quick.priority || f.priority, description: f.description || "",
      assignee_ids: quick.assignee_ids.length ? quick.assignee_ids : f.assignee ? [+f.assignee] : [] };
    if (quick.labels) data.labels = quick.labels;
    if (quick.points != null) data.points = quick.points; else if (f.points) data.points = +f.points;
    if (f.sprint_id) data.sprint_id = +f.sprint_id;
    if (f.parent_key) data.parent_key = f.parent_key;
    const it = await createItem(data);
    if (!it) return;
    if (f.another) { form.reset(); $("#dupes").innerHTML = ""; form.querySelector('[name="title"]').focus(); }
    else $("#modal").close();
  }

  /* ---------- @mention suggestions for any textarea with data-mention ---------- */
  function mentionSuggest(ta) {
    let box = $("#mentionBox");
    const upto = ta.value.slice(0, ta.selectionStart);
    const m = upto.match(/(^|\s)@([\w.-]*)$/);
    if (!m) { if (box) box.remove(); return; }
    const q = m[2].toLowerCase();
    const hits = S.members.filter(u => u.handle.toLowerCase().includes(q) || u.name.toLowerCase().includes(q)).slice(0, 6);
    if (!hits.length) { if (box) box.remove(); return; }
    if (!box) { box = document.createElement("div"); box.id = "mentionBox"; box.className = "mention-box"; }
    ta.insertAdjacentElement("afterend", box);
    box.innerHTML = hits.map(u => '<button type="button" data-act="pickMention" data-h="' + esc(u.handle) + '">' + avatar(u.id, "sm") + esc(u.name) + ' <span class="muted">@' + esc(u.handle) + "</span></button>").join("");
    S.mentionTarget = ta;
  }
  function pickMention(handle) {
    const ta = S.mentionTarget;
    const box = $("#mentionBox");
    if (box) box.remove();
    if (!ta) return;
    const pos = ta.selectionStart, before = ta.value.slice(0, pos).replace(/@([\w.-]*)$/, "@" + handle + " ");
    ta.value = before + ta.value.slice(pos);
    ta.focus();
    ta.setSelectionRange(before.length, before.length);
    if (ta.id === "descBox") S.descDraft = ta.value;
  }

  /* ---------- settings ---------- */
  async function loadFields() {
    const box = document.getElementById("cfs");
    if (!box) return;
    try {
      const d = await API.get("/api/spaces/" + S.space.key + "/fields");
      box.classList.remove("muted");
      box.innerHTML = d.fields.length ? d.fields.map(f =>
        '<div class="mini"><span class="grow">' + esc(f.name) + ' <code>' + esc(f.key) + "</code></span>" +
        '<span class="muted small">' + esc(f.type) + (f.options.length ? ": " + esc(f.options.join(", ")) : "") + "</span>" +
        (f.archived ? '<span class="chip">archived</span>' : "") +
        '<button class="btn ghost sm" data-act="archiveField" data-id="' + f.id + '" data-on="' + (f.archived ? "0" : "1") + '">' +
        (f.archived ? "Restore" : "Archive") + "</button>" +
        '<button class="x danger" data-act="deleteField" data-id="' + f.id + '" data-name="' + esc(f.name) + '" aria-label="Delete ' + esc(f.name) + '">x</button></div>').join("")
        : '<p class="muted small">None yet.</p>';
    } catch (e) { box.textContent = e.message; }
  }

  async function loadHooks() {
    const box = document.getElementById("hooks");
    if (!box) return;
    try {
      const d = await API.get("/api/spaces/" + S.space.key + "/webhooks");
      box.classList.remove("muted");
      box.innerHTML = d.webhooks.length ? d.webhooks.map(h =>
        '<div class="mini"><span class="grow">' + esc(h.url) + "</span>" +
        '<span class="muted small">' + (h.events.length ? esc(h.events.join(", ")) : "all events") + "</span>" +
        (h.last_at ? '<span class="' + (h.last_error ? "danger" : "muted") + ' small">' +
          (h.last_error ? esc(h.last_error.slice(0, 40)) : "HTTP " + h.last_status) + "</span>" : '<span class="muted small">never fired</span>') +
        '<button class="btn ghost sm" data-act="testWebhook" data-id="' + h.id + '">Test</button>' +
        '<button class="x danger" data-act="deleteWebhook" data-id="' + h.id + '" aria-label="Delete webhook">x</button></div>').join("")
        : '<p class="muted small">None yet.</p>';
    } catch (e) { box.textContent = e.message; }
  }

  function viewSettings(v) {
    const sp = S.space, admin = isAdmin(), dis = admin ? "" : " disabled";
    if (!S.wf) S.wf = sp.statuses.map(s => Object.assign({ orig: s.name }, s));
    const removed = sp.statuses.filter(s => !S.wf.some(w => w.orig === s.name)).map(s => s.name);
    v.innerHTML = '<div class="settings">' +
      '<section class="card-sec"><h3>Details</h3><form data-form="spaceDetails"><label>Name<input name="name" value="' + esc(sp.name) + '"' + dis + "></label>" +
      '<label>Description<textarea name="description" rows="2"' + dis + ">" + esc(sp.description || "") + "</textarea></label>" +
      '<p class="muted small">Key ' + esc(sp.key) + ", " + ((sp.settings || {}).template === "kanban" ? "Kanban" : "Scrum") + " space. Your role: " + esc(S.role) + ".</p>" +
      (admin ? '<button class="btn sm" type="submit">Save details</button>' : "") + "</form></section>" +

      '<section class="card-sec"><h3>Workflow</h3><p class="muted small">Order is left to right on the board. The category decides what counts as started and finished in reports. A WIP limit of 0 means no limit.</p>' +
      '<table class="tbl wf"><thead><tr><th>Status</th><th>Category</th><th>WIP limit</th><th></th></tr></thead><tbody>' +
      S.wf.map((s, i) => "<tr><td><input data-change=\"wf\" data-i=\"" + i + '" data-k="name" value="' + esc(s.name) + '" aria-label="Status name"' + dis + "></td>" +
        '<td><select data-change="wf" data-i="' + i + '" data-k="category" aria-label="Category"' + dis + ">" + [["todo", "To do"], ["doing", "In progress"], ["done", "Done"]].map(([k, l]) => opt(k, l, s.category === k)).join("") + "</select></td>" +
        '<td><input type="number" min="0" data-change="wf" data-i="' + i + '" data-k="wip" value="' + (s.wip || 0) + '" aria-label="WIP limit"' + dis + "></td>" +
        "<td>" + (admin ? '<button class="x" data-act="wfMove" data-i="' + i + '" data-d="-1" aria-label="Move left">↑</button><button class="x" data-act="wfMove" data-i="' + i + '" data-d="1" aria-label="Move right">↓</button><button class="x danger" data-act="wfDel" data-i="' + i + '" aria-label="Remove status">×</button>' : "") + "</td></tr>").join("") +
      "</tbody></table>" +
      (removed.length ? '<p class="warn small">Work in ' + removed.map(esc).join(", ") + ' will move to <b>' + esc(S.wf[0] ? S.wf[0].name : "") + "</b> when you save.</p>" : "") +
      (admin ? '<div class="row-actions"><button class="btn ghost sm" data-act="wfAdd">Add status</button><span class="grow"></span><button class="btn ghost sm" data-act="wfReset">Discard changes</button><button class="btn sm" data-act="wfSave">Save workflow</button></div>' : "") + "</section>" +

      '<section class="card-sec"><h3>Members</h3><table class="tbl"><tbody>' + S.members.map(m => "<tr><td>" + avatar(m.id, "sm") + " " + esc(m.name) + ' <span class="muted small">@' + esc(m.handle) + "</span></td><td class=\"muted\">" + esc(m.email) + "</td><td>" +
        (admin ? '<select data-change="role" data-id="' + m.id + '" aria-label="Role for ' + esc(m.name) + '">' + ["viewer", "member", "admin"].map(r => opt(r, r[0].toUpperCase() + r.slice(1), r === m.role)).join("") + "</select>" : esc(m.role)) + "</td><td>" +
        (admin ? '<button class="x danger" data-act="removeMember" data-id="' + m.id + '" aria-label="Remove ' + esc(m.name) + '">×</button>' : "") + "</td></tr>").join("") + "</tbody></table>" +
      (admin ? '<form class="inline-form" data-form="addMember"><input name="email" type="email" required placeholder="teammate@company.com" aria-label="Email"><select name="role" aria-label="Role">' + opt("member", "Member", true) + opt("viewer", "Viewer") + opt("admin", "Admin") + '</select><button class="btn sm" type="submit">Add member</button></form><p class="muted small">Viewers can see everything but change nothing. Members create, edit and comment. Admins also manage settings and members. People need an account first' + (S.me.is_admin ? ' (create one under <a href="#/admin">People</a>).' : ", created by a site admin.") + "</p>" : "") + "</section>" +

      (admin ? '<section class="card-sec"><h3>Import</h3><p class="muted small">From Jira: open your filter, choose Export, then CSV (all fields). People are matched to members by name or email, unknown statuses are added to the workflow, and comments, sprints, parents, estimates and time spent come across.</p>' +
        '<label class="btn ghost sm file-btn">Import Jira CSV<input type="file" accept=".csv,text/csv" data-change="importJira" hidden></label> ' +
        '<label class="btn ghost sm file-btn">Import Freehold JSON or prototype backup<input type="file" accept=".json,application/json" data-change="importOT" hidden></label>' +
        (S.importResult ? '<div class="import-res">' + S.importResult + "</div>" : "") + "</section>" : "") +

      '<section class="card-sec"><h3>Export</h3><p class="muted small">Your data is yours. Exports include every work item with comments, time logs and links.</p>' +
      '<a class="btn ghost sm" href="' + API.fileUrl("/api/spaces/" + sp.key + "/export") + '" download>Download JSON</a> <a class="btn ghost sm" href="' + API.fileUrl("/api/spaces/" + sp.key + "/export.csv") + '" download>Download CSV</a></section>' +

      (admin ? '<section class="card-sec"><h3>Custom fields</h3><p class="muted small">Extra fields on every work item in this space. Each one is filterable by its key, so a field called Severity is <code>severity = High</code> in the filter box. A type cannot change once values exist, so archive instead.</p>' +
        '<div id="cfs" class="muted small">Loading…</div>' +
        '<form class="inline-form" data-form="addField"><input name="name" required placeholder="Field name, e.g. Severity" aria-label="Field name">' +
        '<select name="type" aria-label="Type">' + ["text", "number", "date", "select", "multiselect", "checkbox", "url", "user"].map(t => opt(t, t)).join("") + "</select>" +
        '<input name="options" placeholder="Options, comma separated (select only)" aria-label="Options">' +
        '<button class="btn sm" type="submit">Add field</button></form></section>' : "") +
      (admin ? '<section class="card-sec"><h3>Webhooks</h3><p class="muted small">Freehold POSTs to these when things happen here. Each is signed with its own secret, which is shown once when you create it. A receiver that is down never blocks anyone\'s work.</p>' +
        '<div id="hooks" class="muted small">Loading…</div>' +
        '<form class="inline-form" data-form="addWebhook"><input name="url" type="url" required placeholder="https://example.com/freehold-hook" aria-label="Webhook URL"><button class="btn sm" type="submit">Add webhook</button></form></section>' : "") +
      (admin ? '<section class="card-sec danger-zone"><h3>Delete space</h3><p class="muted small">This removes every work item, comment and attachment in ' + esc(sp.key) + '. Export first if you might need it.</p><button class="btn danger sm" data-act="deleteSpace">Delete ' + esc(sp.key) + "</button></section>" : "") +
      "</div>";
    if (admin) { loadHooks(); loadFields(); }
  }

  async function loadTokens() {
    const box = document.getElementById("tokens");
    if (!box) return;
    try {
      const rows = await API.get("/api/me/tokens");
      box.classList.remove("muted");
      box.innerHTML = rows.length ? rows.map(t =>
        '<div class="mini"><span class="grow">' + esc(t.name) + ' <code>' + esc(t.prefix) + '…</code></span>' +
        '<span class="muted small">' + (t.last_used_at ? "last used " + ago(t.last_used_at) : "never used") +
        (t.expires_at ? ", expires " + esc(t.expires_at.slice(0, 10)) : "") + "</span>" +
        '<button class="x danger" data-act="revokeToken" data-id="' + t.id + '" aria-label="Revoke ' + esc(t.name) + '">x</button></div>').join("")
        : '<p class="muted small">None. Create one to use the API from a script.</p>';
    } catch (e) { box.textContent = e.message; }
  }

  /* ---------- custom fields ---------- */
  function customInput(f, value, dis) {
    const at = ' data-change="custom" data-key="' + esc(f.key) + '" aria-label="' + esc(f.name) + '"' + dis;
    const v = value == null ? "" : value;
    if (f.type === "checkbox")
      return '<label class="inline"><input type="checkbox"' + at + (v ? " checked" : "") + "> " + esc(f.description || "Yes") + "</label>";
    if (f.type === "select")
      return "<select" + at + ">" + opt("", "None", v === "") +
        f.options.map(o => opt(o, o, String(v) === o)).join("") + "</select>";
    if (f.type === "multiselect") {
      const chosen = Array.isArray(v) ? v.map(String) : [];
      return '<div class="chips">' + f.options.map(o =>
        '<label class="inline"><input type="checkbox" data-change="customMulti" data-key="' + esc(f.key) +
        '" data-opt="' + esc(o) + '"' + (chosen.includes(o) ? " checked" : "") + dis + "> " + esc(o) + "</label>").join("") + "</div>";
    }
    if (f.type === "user")
      return "<select" + at + ">" + opt("", "Nobody", v === "") +
        S.members.map(m => opt(m.id, m.name, String(v) === String(m.id))).join("") + "</select>";
    const type = f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "url" ? "url" : "text";
    return '<input type="' + type + '" value="' + esc(String(v)) + '"' + at +
      (f.description ? ' placeholder="' + esc(f.description) + '"' : "") + ">";
  }

  /* ---------- catch up ---------- */
  function viewCatchUp(v) {
    const days = S.catchDays || 7;
    v.innerHTML = '<div class="settings"><section class="card-sec"><h3>While you were away</h3>' +
      '<p class="muted small">Changes other people made to work you are assigned, watching or raised. Your own edits are not news to you.</p>' +
      '<label class="inline">Last <select data-change="catchDays">' +
      [1, 3, 7, 14, 30].map(d => opt(d, d + (d === 1 ? " day" : " days"), d === days)).join("") + "</select></label>" +
      '<div id="catch" class="muted small">Loading…</div></section></div>';
    loadCatchUp();
  }

  async function loadCatchUp() {
    const box = document.getElementById("catch");
    if (!box) return;
    try {
      const d = await API.get("/api/catch-up?days=" + (S.catchDays || 7));
      box.classList.remove("muted");
      if (d.nothing) { box.innerHTML = '<p class="muted">Nothing changed on your work. Enjoy it.</p>'; return; }
      const group = (title, rows, line) => rows.length
        ? "<h4>" + esc(title) + ' <span class="muted small">' + rows.length + "</span></h4>" +
          rows.map(r => '<div class="mini"><a href="#/item/' + esc(r.key) + '">' + esc(r.key) + "</a>" +
            '<span class="grow">' + esc(r.title) + "</span>" +
            '<span class="muted small">' + line(r) + "</span></div>").join("")
        : "";
      box.innerHTML =
        group("Newly assigned to you", d.assigned, r => "by " + esc(r.by) + " " + ago(r.at)) +
        group("Blocked right now", d.blocked, () => "waiting on something unfinished") +
        group("Overdue", d.overdue, r => "due " + esc(r.due)) +
        group("Moved", d.moved, r => esc(r.from) + " to " + esc(r.to) + ", by " + esc(r.by) + " " + ago(r.at)) +
        group("New comments", d.commented, r => esc(r.by) + " " + ago(r.at));
    } catch (e) { box.textContent = e.message; }
  }

  /* ---------- profile ---------- */
  function viewProfile(v) {
    const p = S.me.prefs, muted = p.muted || [];
    v.innerHTML = '<div class="settings">' +
      '<section class="card-sec"><h3>Profile</h3><form data-form="profile"><label>Name<input name="name" value="' + esc(S.me.name) + '" required></label>' +
      '<p class="muted small">' + esc(S.me.email) + ". People mention you as @" + esc(S.me.handle) + '.</p><button class="btn sm" type="submit">Save name</button></form></section>' +
      '<section class="card-sec"><h3>Password</h3><form data-form="password"><label>Current password<input name="current_password" type="password" required autocomplete="current-password"></label>' +
      '<label>New password<input name="new_password" type="password" minlength="8" required autocomplete="new-password"></label><button class="btn sm" type="submit">Change password</button></form></section>' +
      '<section class="card-sec"><h3>Notifications</h3><p class="muted small">You decide what reaches you. Nothing here affects anyone else.</p>' +
      '<form data-form="prefs"><table class="tbl prefs"><thead><tr><th>When</th><th>In app</th><th>Email</th></tr></thead><tbody>' +
      EVENTS.map(([k, label]) => "<tr><td>" + label + '</td><td><input type="checkbox" name="' + k + '.inapp"' + (p.events[k].inapp ? " checked" : "") + ' aria-label="' + label + ' in app"></td>' +
        '<td><input type="checkbox" name="' + k + '.email"' + (p.events[k].email ? " checked" : "") + ' aria-label="' + label + ' by email"></td></tr>').join("") + "</tbody></table>" +
      '<div class="grid2"><label>Email delivery<select name="email_mode">' + [["instant", "Right away"], ["digest", "One daily summary"], ["off", "Never email me"]].map(([k, l]) => opt(k, l, p.email_mode === k)).join("") + "</select></label>" +
      '<label>Daily summary time (UTC)<select name="digest_hour">' + Array.from({ length: 24 }, (_, h) => opt(h, String(h).padStart(2, "0") + ":00", +p.digest_hour === h)).join("") + "</select></label></div>" +
      '<button class="btn sm" type="submit">Save notification settings</button></form>' +
      "<h4>Muted work items</h4>" + (muted.length ? muted.map(k => '<span class="chip">' + esc(k) + ' <button class="x" data-act="unmute" data-k="' + esc(k) + '" aria-label="Unmute ' + esc(k) + '">×</button></span>').join(" ") : '<p class="muted small">None. Use Mute on a work item to silence it completely.</p>') +
      "</section>" +
      '<section class="card-sec"><h3>API tokens</h3><p class="muted small">For scripts and integrations. A token acts as you, and is shown once when you create it. Send it as <code>Authorization: Bearer fh_…</code>.</p>' +
      '<div id="tokens" class="muted small">Loading…</div>' +
      '<form class="inline-form" data-form="addToken"><input name="name" required placeholder="What is it for? e.g. CI pipeline" aria-label="Token name"><button class="btn sm" type="submit">Create token</button></form>' +
      "</section></div>";
    loadTokens();
  }

  /* ---------- site admin: people ---------- */
  function viewAdmin(v) {
    if (!S.me.is_admin) { v.innerHTML = emptyState("Site admins only", "Ask a site admin if you need an account created or changed.", ""); return; }
    v.innerHTML = '<div class="settings"><section class="card-sec"><h3>Add a person</h3><form class="grid2" data-form="newUser">' +
      '<label>Name<input name="name" required></label><label>Email<input name="email" type="email" required></label>' +
      '<label>Temporary password<input name="password" minlength="8" required></label><label class="inline"><input type="checkbox" name="is_admin"> Site admin</label>' +
      '<button class="btn sm" type="submit">Create account</button></form><p class="muted small">Share the temporary password privately. They can change it under Profile.</p></section>' +
      '<section class="card-sec"><h3>Everyone</h3><table class="tbl"><thead><tr><th>Name</th><th>Email</th><th>Site admin</th><th>Active</th><th></th></tr></thead><tbody>' +
      S.users.map(u => "<tr><td>" + avatar(u.id, "sm") + " " + esc(u.name) + "</td><td>" + esc(u.email) + '</td><td><input type="checkbox" data-change="userFlag" data-id="' + u.id + '" data-k="is_admin"' + (u.is_admin ? " checked" : "") + (u.id === S.me.id ? " disabled" : "") + ' aria-label="Site admin"></td>' +
        '<td><input type="checkbox" data-change="userFlag" data-id="' + u.id + '" data-k="is_active"' + (u.is_active !== false ? " checked" : "") + (u.id === S.me.id ? " disabled" : "") + ' aria-label="Active"></td>' +
        '<td><button class="btn ghost sm" data-act="resetPw" data-id="' + u.id + '">Reset password</button></td></tr>').join("") + "</tbody></table></section></div>";
  }

  function viewNewSpace(v) {
    v.innerHTML = '<div class="settings narrow"><section class="card-sec"><h3>' + (S.spaces.length ? "Create a space" : "Create your first space") + "</h3>" +
      '<p class="muted small">A space holds one team\'s or project\'s work. The key prefixes every work item, like WEB-12.</p>' +
      '<form data-form="newSpace"><label>Name<input name="name" required placeholder="Website relaunch" data-input="suggestKey"></label>' +
      '<label>Key<input name="key" required pattern="[A-Za-z][A-Za-z0-9]{1,9}" placeholder="WEB" style="text-transform:uppercase"></label>' +
      '<fieldset class="choice"><legend>How does the team work?</legend><label><input type="radio" name="template" value="scrum" checked> <b>Scrum</b> <span class="muted small">Sprints, backlog, burndown and velocity</span></label>' +
      '<label><input type="radio" name="template" value="kanban"> <b>Kanban</b> <span class="muted small">Continuous flow with WIP limits</span></label></fieldset>' +
      '<p class="form-err" role="alert"></p><button class="btn" type="submit">Create space</button></form></section></div>';
  }

  /* ---------- sprint modals ---------- */
  function sprintModal(sprint, starting) {
    const m = $("#modal");
    const start = (sprint && sprint.start) || today();
    const endD = new Date(start + "T00:00:00"); endD.setDate(endD.getDate() + 13);
    const pts = S.items.filter(i => sprint && i.sprint_id === sprint.id).reduce((a, i) => a + (i.points || 0), 0), avg = avgVelocity();
    m.innerHTML = '<form class="mform" data-form="sprint" data-id="' + (sprint ? sprint.id : "") + '" data-start="' + (starting ? 1 : 0) + '"><h2>' + (starting ? "Start " + esc(sprint.name) : sprint ? "Edit sprint" : "Create sprint") + "</h2>" +
      '<label>Name<input name="name" value="' + esc(sprint ? sprint.name : "Sprint " + (S.sprints.length + 1)) + '" required></label>' +
      '<label>Goal<input name="goal" value="' + esc(sprint ? sprint.goal : "") + '" placeholder="What should this sprint achieve?"></label>' +
      '<div class="grid2"><label>Start<input type="date" name="start" value="' + start + '"></label><label>End<input type="date" name="end" value="' + ((sprint && sprint.end) || OQL.isoDay(endD)) + '"></label></div>' +
      (starting && avg && pts > avg * 1.1 ? '<p class="warn small">This sprint has ' + pts + " points; the team averaged " + avg.toFixed(0) + " in recent sprints.</p>" : "") +
      '<p class="form-err" role="alert"></p><div class="row-actions"><span class="grow"></span><button type="button" class="btn ghost" data-act="closeModal">Cancel</button><button class="btn" type="submit">' + (starting ? "Start sprint" : "Save") + "</button></div></form>";
    m.showModal();
  }

  function completeModal(id) {
    const sprint = S.sprints.find(s => s.id === +id);
    const items = S.items.filter(i => i.sprint_id === sprint.id), open = items.filter(i => !isDone(i));
    const future = S.sprints.filter(s => s.state === "future");
    const m = $("#modal");
    m.innerHTML = '<form class="mform" data-form="complete" data-id="' + sprint.id + '"><h2>Complete ' + esc(sprint.name) + "</h2>" +
      "<p>" + (items.length - open.length) + " of " + items.length + " work items are done (" + items.filter(isDone).reduce((a, i) => a + (i.points || 0), 0) + " points).</p>" +
      (open.length ? '<label>Move ' + open.length + " unfinished items to<select name=\"move_to\">" + opt("next", "A new sprint") + opt("backlog", "The backlog") + future.map(s => opt(s.id, s.name)).join("") + "</select></label>" : "") +
      '<p class="form-err" role="alert"></p><div class="row-actions"><span class="grow"></span><button type="button" class="btn ghost" data-act="closeModal">Cancel</button><button class="btn" type="submit">Complete sprint</button></div></form>';
    m.showModal();
  }

  function confirmModal(title, body, label, onYes, requireText) {
    const m = $("#modal");
    m.innerHTML = '<form class="mform" data-form="confirm"><h2>' + esc(title) + "</h2><p>" + body + "</p>" +
      (requireText ? '<label>Type ' + esc(requireText) + ' to confirm<input name="confirm" autocomplete="off" required></label>' : "") +
      '<div class="row-actions"><span class="grow"></span><button type="button" class="btn ghost" data-act="closeModal">Cancel</button><button class="btn danger" type="submit">' + esc(label) + "</button></div></form>";
    S.confirm = { onYes, requireText };
    m.showModal();
    const inp = m.querySelector("input");
    (inp || m.querySelector(".btn.danger")).focus();
  }

  function promptModal(title, label, value, onOk, extra) {
    const m = $("#modal");
    m.innerHTML = '<form class="mform" data-form="prompt"><h2>' + esc(title) + '</h2><label>' + esc(label) + '<input name="value" value="' + esc(value || "") + '" required autocomplete="off"></label>' + (extra || "") +
      '<div class="row-actions"><span class="grow"></span><button type="button" class="btn ghost" data-act="closeModal">Cancel</button><button class="btn" type="submit">Save</button></div></form>';
    S.prompt = onOk;
    m.showModal();
    m.querySelector("input").focus();
  }

  /* ---------- notifications ---------- */
  async function pollNotes() {
    try {
      const n = await API.get("/api/notifications?limit=30");
      S.notes = n;
      renderNav();
      if (!$("#notifs").hidden) renderNotifs();
    } catch (e) { /* quiet: polling */ }
  }
  function renderNotifs() {
    const n = S.notes;
    $("#notifs").innerHTML = '<div class="notifs-h"><b>Notifications</b><span class="grow"></span>' + (n.unread ? '<button class="linkish small" data-act="readAll">Mark all read</button>' : "") +
      '<button class="linkish small" data-act="go" data-to="#/profile">Settings</button></div>' +
      (n.items.length ? n.items.map(x => '<button class="note' + (x.read ? "" : " unread") + '" data-act="openNote" data-id="' + x.id + '" data-key="' + esc(x.key) + '">' + esc(x.text) + '<span class="muted small">' + ago(x.at) + "</span></button>").join("")
        : '<p class="muted small pad">You are all caught up.</p>');
  }

  /* ---------- polling for teammates' changes ---------- */
  async function poll() {
    if (document.hidden || !S.me) return;
    pollNotes();
    if (!S.space || !S.serverTime || S.dragging) return;
    const key = S.space.key;
    try {
      const ch = await API.get("/api/spaces/" + key + "/changes?since=" + encodeURIComponent(S.serverTime));
      if (!S.space || S.space.key !== key) return;
      S.serverTime = ch.server_time;
      const touched = new Set(ch.items.map(i => i.key));
      ch.items.forEach(upsert);
      ch.deleted.forEach(removeItem);
      const role = S.role;
      S.sprints = ch.sprints; S.versions = ch.versions || S.versions; S.links = ch.links; S.members = ch.members; S.space = ch.space; S.role = ch.space.role || role;
      const active = document.activeElement;
      const typing = active && $("#view").contains(active) && /INPUT|TEXTAREA|SELECT/.test(active.tagName);
      if ((touched.size || ch.deleted.length) && !typing && !["settings", "profile", "admin", "activity", "reports"].includes(S.view)) renderView();
      if (S.openKey && (touched.has(S.openKey) || ch.deleted.includes(S.openKey)) && !editing() && !S.descEdit && !S.editComment) refreshDetail();
    } catch (e) { /* quiet: polling */ }
  }

  /* ---------- command palette ---------- */
  function paletteCommands(q) {
    const cmds = [["Create work item", () => openCreate()]];
    if (S.space) VIEWS.forEach(([id, l]) => cmds.push(["Go to " + l, () => go("#/s/" + S.space.key + "/" + id)]));
    S.spaces.forEach(s => cmds.push(["Switch to " + s.name + " (" + s.key + ")", () => go("#/s/" + s.key + "/board")]));
    cmds.push(["New space", () => go("#/new-space")], ["Profile and notifications", () => go("#/profile")], ["Switch light or dark theme", toggleTheme], ["Sign out", logout]);
    if (S.me.is_admin) cmds.push(["People (site admin)", () => go("#/admin")]);
    const ql = q.trim().toLowerCase();
    let out = ql ? cmds.filter(([l]) => ql.split(/\s+/).every(w => l.toLowerCase().includes(w))) : cmds.slice(0, 8);
    if (ql) {
      const up = q.trim().toUpperCase();
      const items = S.items.filter(i => i.key === up || i.key.startsWith(up + "") && /-\d/.test(up) || i.title.toLowerCase().includes(ql)).slice(0, 8);
      out = items.map(i => ["Open " + i.key + " " + i.title, () => go("#/item/" + i.key)]).concat(out);
      if (S.space && canEdit()) out.push(['Create "' + q.trim() + '"', () => openCreate(q.trim())]);
    }
    return out.slice(0, 12);
  }
  function openPalette() {
    const p = $("#palette");
    p.hidden = false;
    const inp = $("#palQ");
    inp.value = "";
    S.palIndex = 0;
    renderPalette();
    inp.focus();
  }
  function closePalette() { $("#palette").hidden = true; }
  function renderPalette() {
    S.palCmds = paletteCommands($("#palQ").value);
    S.palIndex = Math.min(S.palIndex, Math.max(0, S.palCmds.length - 1));
    $("#palList").innerHTML = S.palCmds.map(([l], i) => '<button class="pal-i' + (i === S.palIndex ? " on" : "") + '" data-act="palRun" data-i="' + i + '" role="option" aria-selected="' + (i === S.palIndex) + '">' + esc(l) + "</button>").join("") ||
      '<p class="muted small pad">No matches.</p>';
  }
  function runPalette(i) { const c = S.palCmds && S.palCmds[i]; closePalette(); if (c) c[1](); }

  /* ---------- theme ---------- */
  function applyTheme() {
    let t = null;
    try { t = localStorage.getItem("freehold.theme"); } catch (e) {}
    if (!t) t = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.dataset.theme = t;
  }
  function toggleTheme() {
    const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("freehold.theme", t); } catch (e) {}
  }

  /* ---------- click actions (event delegation keeps the markup free of inline handlers) ---------- */
  const ACT = {
    go: el => { document.body.classList.remove("side-open"); $("#notifs").hidden = true; go(el.dataset.to); },
    open: el => go("#/item/" + el.dataset.key),
    logout,
    toggleSide: () => document.body.classList.toggle("side-open"),
    toggleTheme,
    openCreate: () => openCreate(),
    closeModal: () => $("#modal").close(),
    closeDlg: () => closeDialog(),
    toastAction: () => { $("#toast").classList.remove("show"); if (S.toastAction) S.toastAction(); },
    authMode: el => showAuth(el.dataset.mode),
    applyFilter: el => { S.query = el.dataset.q; $("#q").value = S.query; renderView(); },
    deleteFilter: async el => { try { S.filters = await API.del("/api/filters/" + el.dataset.id); renderNav(); } catch (e) { fail(e); } },
    saveFilter: () => {
      if (!S.space) return;
      if (!S.query.trim()) return toast("Type a filter first, then save it.");
      promptModal("Save filter", "Name", "", async (name, form) => {
        try { S.filters = await API.post("/api/spaces/" + S.space.key + "/filters", { name, query: S.query, shared: !!fld(form, "shared").checked }); renderNav(); toast("Saved " + name); }
        catch (e) { fail(e); }
      }, '<label class="inline"><input type="checkbox" name="shared"> Share with everyone in ' + esc(S.space.key) + "</label>");
    },
    toggleNotifs: () => { const p = $("#notifs"); p.hidden = !p.hidden; if (!p.hidden) { renderNotifs(); pollNotes(); } },
    readAll: async () => { try { await API.post("/api/notifications/read", { all: true }); pollNotes(); } catch (e) { fail(e); } },
    openNote: async el => {
      $("#notifs").hidden = true;
      API.post("/api/notifications/read", { ids: [+el.dataset.id] }).then(pollNotes).catch(() => {});
      if (el.dataset.key) go("#/item/" + el.dataset.key);
    },
    sort: el => { const k = el.dataset.k; if (S.sortK === k) S.sortDir *= -1; else { S.sortK = k; S.sortDir = 1; } renderView(); },
    clearSel: () => { S.selected.clear(); renderView(); },
    bulkDelete: () => confirmModal("Delete " + S.selected.size + " work items?", "This cannot be undone.", "Delete", async () => {
      try {
        const keys = Array.from(S.selected);
        await API.post("/api/items/bulk", { keys, delete: true });
        keys.forEach(removeItem);
        renderView();
        toast("Deleted " + keys.length + " work items");
      } catch (e) { fail(e); }
    }),
    calNav: el => { const d = +el.dataset.d; const m = S.calMonth; S.calMonth = d === 0 ? null : new Date(m.getFullYear(), m.getMonth() + d, 1); renderView(); },
    createSprint: () => sprintModal(null, false),
    editSprint: el => sprintModal(S.sprints.find(s => s.id === +el.dataset.id), false),
    startSprint: el => sprintModal(S.sprints.find(s => s.id === +el.dataset.id), true),
    completeSprint: el => completeModal(el.dataset.id),
    deleteSprint: el => confirmModal("Delete this sprint?", "Its work items move back to the backlog.", "Delete sprint", async () => {
      try { await API.del("/api/sprints/" + el.dataset.id); await loadSpace(S.space.key); renderView(); } catch (e) { fail(e); }
    }),
    /* dialog */
    editDesc: () => { if (!canEdit()) return; S.descEdit = true; S.descPreview = false; S.descDraft = S.detail.item.description || ""; renderDialog(); },
    descTab: el => { const box = $("#descBox"); if (box) S.descDraft = box.value; S.descPreview = el.dataset.p === "1"; renderDialog(); },
    cancelDesc: () => { S.descEdit = false; renderDialog(); },
    saveDesc: async () => {
      const box = $("#descBox");
      if (box) S.descDraft = box.value;
      S.descEdit = false;
      clearDraft("description");
      await saveItem(S.detail.item.key, { description: S.descDraft });
    },
    dtab: el => { S.dtab = el.dataset.t; renderDialog(); },
    addComment: async () => {
      const box = $("#cBody");
      const body = box && box.value.trim();
      if (!body) return;
      box.disabled = true;
      clearDraft("comment");
      await itemAction("/api/items/" + S.openKey + "/comments", { body });
    },
    editComment: el => { S.editComment = +el.dataset.id; renderDialog(); },
    cancelComment: () => { S.editComment = null; renderDialog(); },
    saveComment: async el => {
      const body = $("#cEdit").value.trim();
      if (!body) return;
      try { const d = await API.patch("/api/comments/" + el.dataset.id, { body }); S.editComment = null; applyDetail(d); } catch (e) { fail(e); }
    },
    deleteComment: el => confirmModal("Delete this comment?", "This cannot be undone.", "Delete", () => itemAction("/api/comments/" + el.dataset.id, null, "DELETE")),
    logWork: async () => {
      const hours = parseFloat($("#wlHours").value);
      if (!(hours > 0)) return toast("Enter the hours you worked.");
      await itemAction("/api/items/" + S.openKey + "/worklogs", { hours, day: $("#wlDay").value, note: $("#wlNote").value });
    },
    deleteWorklog: el => itemAction("/api/worklogs/" + el.dataset.id, null, "DELETE"),
    watch: () => itemAction("/api/items/" + S.openKey + "/watch", { on: !S.detail.item.watcher_ids.includes(S.me.id) }),
    mute: async () => {
      const d = await itemAction("/api/items/" + S.openKey + "/mute", { on: !S.detail.muted });
      if (d) { S.me = await API.get("/api/me"); toast(d.muted ? "You will not get notifications about " + S.openKey : "Notifications for " + S.openKey + " are back on"); }
    },
    copyLink: () => {
      const url = location.origin + location.pathname + "#/item/" + S.openKey;
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(() => toast("Link copied"), () => toast(url));
      else toast(url);
    },
    cloneItem: async () => {
      try { const c = await API.post("/api/items/" + S.openKey + "/clone"); upsert(c); renderView(); go("#/item/" + c.key); toast("Cloned as " + c.key); } catch (e) { fail(e); }
    },
    deleteItem: () => {
      const key = S.openKey;
      confirmModal("Delete " + key + "?", "Comments, attachments and time logs go with it. Child items stay and lose their parent.", "Delete", async () => {
        try { await API.del("/api/items/" + key); removeItem(key); closeDialog(); renderView(); toast("Deleted " + key); } catch (e) { fail(e); }
      });
    },
    unassign: el => saveItem(S.openKey, { assignee_ids: S.detail.item.assignee_ids.filter(id => id !== +el.dataset.id) }),
    assignMe: () => saveItem(S.openKey, { assignee_ids: S.detail.item.assignee_ids.concat([S.me.id]) }),
    uncheck: el => { const it = S.detail.item; saveItem(it.key, { checklist: it.checklist.filter((_, i) => i !== +el.dataset.i) }); },
    addLink: async () => {
      const raw = $("#linkKey").value.trim().toUpperCase().split(/\s+/)[0];
      if (!raw) return toast("Enter the key of the work item to link.");
      await itemAction("/api/items/" + S.openKey + "/links", { type: $("#linkType").value, target_key: raw });
    },
    unlink: el => itemAction("/api/links/" + el.dataset.id + "?key=" + encodeURIComponent(S.openKey), null, "DELETE"),
    deleteAtt: el => confirmModal("Delete this attachment?", "The file is removed for everyone.", "Delete", () => itemAction("/api/attachments/" + el.dataset.id, null, "DELETE")),
    pickMention: el => pickMention(el.dataset.h),
    /* settings */
    wfAdd: () => { S.wf.push({ name: "New status", category: "doing", wip: 0 }); renderView(); },
    wfDel: el => { if (S.wf.length <= 2) return toast("A workflow needs at least two statuses."); S.wf.splice(+el.dataset.i, 1); renderView(); },
    wfMove: el => { const i = +el.dataset.i, j = i + +el.dataset.d; if (j < 0 || j >= S.wf.length) return; [S.wf[i], S.wf[j]] = [S.wf[j], S.wf[i]]; renderView(); },
    wfReset: () => { S.wf = null; renderView(); },
    wfSave: async () => {
      const status_map = {};
      S.wf.forEach(w => { if (w.orig && w.orig !== w.name) status_map[w.orig] = w.name; });
      try {
        const sp = await API.patch("/api/spaces/" + S.space.key, { statuses: S.wf.map(w => ({ name: w.name, category: w.category, wip: +w.wip || 0 })), status_map });
        S.space = sp; S.role = sp.role; S.wf = null;
        await loadSpace(S.space.key);
        render();
        toast("Workflow saved");
      } catch (e) { fail(e); }
    },
    removeMember: el => confirmModal("Remove " + uname(+el.dataset.id) + " from " + S.space.key + "?", "Their work stays assigned to them.", "Remove", async () => {
      try { S.members = await API.del("/api/spaces/" + S.space.key + "/members/" + el.dataset.id); renderView(); } catch (e) { fail(e); }
    }),
    deleteSpace: () => confirmModal("Delete " + S.space.key + "?", "Everything in this space is deleted for everyone.", "Delete space", async () => {
      try { const key = S.space.key; await API.del("/api/spaces/" + key); S.space = null; await loadSpaces(); toast("Deleted " + key); go("#/"); } catch (e) { fail(e); }
    }, S.space.key),
    revokeToken: async el => {
      try { await API.del("/api/me/tokens/" + el.dataset.id); await loadTokens(); toast("Token revoked"); }
      catch (e) { fail(e); }
    },
    archiveField: async el => {
      try {
        await API.patch("/api/fields/" + el.dataset.id, { archived: el.dataset.on === "1" });
        await loadFields(); await loadSpace(S.space.key); renderView();
      } catch (e) { fail(e); }
    },
    deleteField: el => confirmModal("Delete " + el.dataset.name + "?",
      "Values already saved under this field stay in the database but stop being readable. Archiving keeps them visible.",
      "Delete field", async () => {
        try { await API.del("/api/fields/" + el.dataset.id); await loadFields(); await loadSpace(S.space.key); renderView(); toast("Field deleted"); }
        catch (e) { fail(e); }
      }),
    testWebhook: async el => {
      try { await API.post("/api/webhooks/" + el.dataset.id + "/test"); toast("Ping queued"); setTimeout(loadHooks, 1200); }
      catch (e) { fail(e); }
    },
    deleteWebhook: async el => {
      try { await API.del("/api/webhooks/" + el.dataset.id); await loadHooks(); toast("Webhook removed"); }
      catch (e) { fail(e); }
    },
    unmute: async el => {
      const prefs = Object.assign({}, S.me.prefs, { muted: (S.me.prefs.muted || []).filter(k => k !== el.dataset.k) });
      try { S.me = await API.patch("/api/me", { prefs }); renderView(); } catch (e) { fail(e); }
    },
    resetPw: el => {
      const u = S.userById[+el.dataset.id];
      promptModal("Reset password for " + u.name, "New temporary password (8+ characters)", "", async (pw) => {
        try { await API.patch("/api/users/" + u.id, { password: pw }); toast("Password reset for " + u.name); } catch (e) { fail(e); }
      });
    },
    palRun: el => runPalette(+el.dataset.i),
  };

  /* ---------- change handlers ---------- */
  const CHG = {
    custom: async el => {
      const f = (S.fields || []).find(x => x.key === el.dataset.key);
      let value = el.type === "checkbox" ? el.checked : el.value;
      if (value === "") value = null;
      await saveItem(S.detail.item.key, { custom: { [el.dataset.key]: value } });
    },
    customMulti: async el => {
      const key = el.dataset.key;
      const picked = $$('input[data-change="customMulti"][data-key="' + key + '"]')
        .filter(b => b.checked).map(b => b.dataset.opt);
      await saveItem(S.detail.item.key, { custom: { [key]: picked.length ? picked : null } });
    },
    catchDays: el => { S.catchDays = +el.value; loadCatchUp(); },
    switchSpace: el => { if (el.value === "__new") go("#/new-space"); else go("#/s/" + el.value + "/" + (VIEWS.some(v => v[0] === S.view) ? S.view : "board")); },
    lanes: el => { S.lanes = el.value; renderView(); },
    sel: el => {
      el.checked ? S.selected.add(el.dataset.key) : S.selected.delete(el.dataset.key);
      const row = el.closest("tr");
      if (row) row.classList.toggle("sel", el.checked);
      const boxes = $$('input[data-change="sel"]'), head = $('input[data-change="selAll"]');
      if (head) head.checked = boxes.length > 0 && boxes.every(b => b.checked);
      renderBulk();
    },
    selAll: el => {
      $$('input[data-change="sel"]').forEach(b => {
        b.checked = el.checked;
        el.checked ? S.selected.add(b.dataset.key) : S.selected.delete(b.dataset.key);
        const row = b.closest("tr");
        if (row) row.classList.toggle("sel", el.checked);
      });
      renderBulk();
    },
    bulk: async el => {
      if (!el.value) return;
      const field = el.dataset.field;
      let value = el.value;
      if (field === "assignee_ids") value = JSON.parse(value);
      if (field === "sprint_id") value = value === "backlog" ? null : +value;
      const keys = Array.from(S.selected);
      try {
        const r = await API.post("/api/items/bulk", { keys, set: { [field]: value } });
        r.updated.forEach(upsert);
        renderView();
        toast("Updated " + keys.length + " work items");
      } catch (e) { fail(e); renderView(); }
    },
    reportSprint: el => { S.reportSprint = +el.value; renderView(); },
    field: el => {
      const f = el.dataset.field;
      let v = el.value;
      if (f === "title" && !v.trim()) { el.value = S.detail.item.title; return toast("A work item needs a summary."); }
      if (["points", "estimate"].includes(f)) v = v === "" ? null : +v;
      if (["start", "due", "parent_key"].includes(f)) v = v || null;
      if (f === "reporter_id" || f === "sprint_id") v = v === "" ? null : +v;
      saveItem(S.openKey, { [f]: v });
    },
    labels: el => saveItem(S.openKey, { labels: el.value.split(",").map(s => s.trim()).filter(Boolean) }),
    assign: el => { if (el.value) saveItem(S.openKey, { assignee_ids: S.detail.item.assignee_ids.concat([+el.value]) }); },
    check: el => { const it = S.detail.item; saveItem(it.key, { checklist: it.checklist.map((c, i) => (i === +el.dataset.i ? { text: c.text, done: el.checked } : c)) }); },
    upload: el => uploadFiles(el.files),
    wf: el => { const w = S.wf[+el.dataset.i]; w[el.dataset.k] = el.dataset.k === "wip" ? +el.value || 0 : el.value; if (el.dataset.k === "category") renderView(); },
    role: async el => { try { S.members = await API.patch("/api/spaces/" + S.space.key + "/members/" + el.dataset.id, { role: el.value }); toast("Role updated"); } catch (e) { fail(e); } renderView(); },
    importJira: el => importFile(el, "jira"),
    importOT: el => importFile(el, "freehold"),
    userFlag: async el => {
      try { await API.patch("/api/users/" + el.dataset.id, { [el.dataset.k]: el.checked }); await loadUsers(); toast("Saved"); } catch (e) { fail(e); }
      renderView();
    },
  };

  async function uploadFiles(files) {
    const key = S.openKey;
    for (const f of Array.from(files || [])) {
      toast("Uploading " + f.name + "…");
      try { const d = await API.upload("/api/items/" + key + "/attachments", f); if (S.openKey === key) applyDetail(d); toast("Attached " + f.name); }
      catch (e) { fail(e); }
    }
  }
  async function importFile(el, kind) {
    const file = el.files && el.files[0];
    if (!file) return;
    S.importResult = "Importing " + esc(file.name) + "…";
    renderView();
    try {
      const r = await API.upload("/api/spaces/" + S.space.key + "/import/" + kind, file);
      S.importResult = "<b>Imported " + r.created + " work items" + (r.sprints ? " and " + r.sprints + " sprints" : "") + ".</b>" + (r.warnings || []).map(w => "<br>" + esc(w)).join("");
      const res = S.importResult;
      await loadSpace(S.space.key);
      S.importResult = res;
    } catch (e) { S.importResult = '<span class="danger">' + esc(e.message) + "</span>"; }
    renderView();
  }

  /* ---------- forms ---------- */
  const FORMS = {
    login: submitAuth, register: submitAuth,
    create: submitCreate,
    newSpace: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      try {
        const sp = await API.post("/api/spaces", { name: f.name, key: f.key.toUpperCase(), template: f.template });
        await loadSpaces();
        go("#/s/" + sp.key + "/" + (f.template === "kanban" ? "board" : "backlog"));
        toast("Created " + sp.name);
      } catch (e) { form.querySelector(".form-err").textContent = e.message; }
    },
    spaceDetails: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      try { S.space = await API.patch("/api/spaces/" + S.space.key, f); await loadSpaces(); render(); toast("Saved"); } catch (e) { fail(e); }
    },
    addToken: async form => {
      try {
        const t = await API.post("/api/me/tokens", { name: fld(form, "name").value });
        form.reset();
        await loadTokens();
        confirmModal("Token created", "Copy it now, it cannot be shown again:\n\n" + t.token, "Done", () => {});
      } catch (e) { fail(e); }
    },
    addField: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      const body = { name: f.name, type: f.type,
        options: (f.options || "").split(",").map(o => o.trim()).filter(Boolean) };
      try {
        await API.post("/api/spaces/" + S.space.key + "/fields", body);
        form.reset();
        await loadFields();
        await loadSpace(S.space.key);
        toast("Added " + f.name);
      } catch (e) { fail(e); }
    },
    addWebhook: async form => {
      try {
        const h = await API.post("/api/spaces/" + S.space.key + "/webhooks", { url: fld(form, "url").value });
        form.reset();
        await loadHooks();
        // Shown once and never again, so it has to be copyable now.
        confirmModal("Webhook added", "Signing secret, shown once:\n\n" + h.secret +
          "\n\nVerify it as the X-Freehold-Signature header: sha256 HMAC of the request body.", "Done", () => {});
      } catch (e) { fail(e); }
    },
    addMember: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      try { S.members = await API.post("/api/spaces/" + S.space.key + "/members", f); await loadUsers(); renderView(); toast("Added " + f.email); } catch (e) { fail(e); }
    },
    profile: async form => { try { S.me = await API.patch("/api/me", { name: fld(form, "name").value }); await loadUsers(); render(); toast("Saved"); } catch (e) { fail(e); } },
    password: async form => {
      try { await API.patch("/api/me", { current_password: fld(form, "current_password").value, new_password: fld(form, "new_password").value }); form.reset(); toast("Password changed"); } catch (e) { fail(e); }
    },
    prefs: async form => {
      const events = {};
      EVENTS.forEach(([k]) => (events[k] = { inapp: fld(form, k + ".inapp").checked, email: fld(form, k + ".email").checked }));
      const prefs = { events, email_mode: fld(form, "email_mode").value, digest_hour: +fld(form, "digest_hour").value, muted: S.me.prefs.muted || [] };
      try { S.me = await API.patch("/api/me", { prefs }); toast("Notification settings saved"); } catch (e) { fail(e); }
    },
    newUser: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      try { await API.post("/api/users", { name: f.name, email: f.email, password: f.password, is_admin: !!f.is_admin }); await loadUsers(); form.reset(); renderView(); toast("Created an account for " + f.name); } catch (e) { fail(e); }
    },
    sprint: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      const id = form.dataset.id, starting = form.dataset.start === "1";
      const body = { name: f.name, goal: f.goal, start: f.start || null, end: f.end || null };
      try {
        if (!id) await API.post("/api/spaces/" + S.space.key + "/sprints", body);
        else await API.patch("/api/sprints/" + id, starting ? Object.assign(body, { state: "active" }) : body);
        $("#modal").close();
        await loadSpace(S.space.key);
        if (starting) { toast(f.name + " started"); go("#/s/" + S.space.key + "/board"); } else renderView();
      } catch (e) { form.querySelector(".form-err").textContent = e.message; }
    },
    complete: async form => {
      const f = Object.fromEntries(new FormData(form).entries());
      try {
        const r = await API.post("/api/sprints/" + form.dataset.id + "/complete", { move_to: f.move_to || "backlog" });
        $("#modal").close();
        await loadSpace(S.space.key);
        renderView();
        toast("Sprint completed: " + r.completed + " done, " + r.moved + " moved");
      } catch (e) { form.querySelector(".form-err").textContent = e.message; }
    },
    confirm: async form => {
      const c = S.confirm;
      const box = fld(form, "confirm");
      if (c.requireText && box.value.trim().toUpperCase() !== c.requireText.toUpperCase()) { box.setCustomValidity("Type " + c.requireText); form.reportValidity(); box.addEventListener("input", () => box.setCustomValidity(""), { once: true }); return; }
      $("#modal").close();
      await c.onYes();
    },
    prompt: async form => { const v = fld(form, "value").value.trim(); if (!v) return; $("#modal").close(); await S.prompt(v, form); },
  };

  /* ---------- drop targets ---------- */
  const DROP = {
    status: (zone, key) => {
      const it = S.byKey[key];
      if (!it) return;
      const patch = {};
      if (it.status !== zone.dataset.status) patch.status = zone.dataset.status;
      const lane = zone.dataset.lane;
      if (S.lanes === "assignee" && lane) { const ids = lane === "none" ? [] : [+lane]; if (JSON.stringify(ids) !== JSON.stringify(it.assignee_ids.slice(0, 1))) patch.assignee_ids = ids; }
      if (S.lanes === "priority" && lane && lane !== it.priority) patch.priority = lane;
      if (S.lanes === "epic" && lane && (lane === "none" ? null : lane) !== (it.parent_key || null)) patch.parent_key = lane === "none" ? null : lane;
      const col = S.space.statuses.find(s => s.name === zone.dataset.status);
      if (patch.status && col && col.wip && S.items.filter(i => i.status === col.name && i.sprint_id === it.sprint_id).length >= col.wip) toast(col.name + " is over its WIP limit of " + col.wip);
      if (Object.keys(patch).length) saveItem(key, patch);
    },
    sprint: (zone, key) => {
      const it = S.byKey[key];
      const sid = zone.dataset.sprint === "backlog" ? null : +zone.dataset.sprint;
      if (it && it.sprint_id !== sid) saveItem(key, { sprint_id: sid });
    },
    row: (zone, key) => {
      const target = S.byKey[zone.dataset.key], it = S.byKey[key];
      if (!target || !it || target.key === it.key) return;
      const sec = zone.closest("[data-sprint]");
      const sid = sec && sec.dataset.sprint !== "backlog" ? +sec.dataset.sprint : null;
      const siblings = S.items.filter(i => i.sprint_id === sid && i.type !== "Epic" && i.key !== it.key).sort((a, b) => a.rank - b.rank);
      const idx = siblings.indexOf(target);
      const prev = siblings[idx - 1];
      const rank = prev ? (prev.rank + target.rank) / 2 : target.rank - 1;
      const patch = { rank };
      if (it.sprint_id !== sid) patch.sprint_id = sid;
      saveItem(key, patch);
    },
  };

  /* ---------- global listeners ---------- */
  document.addEventListener("click", e => {
    const el = e.target.closest("[data-act]");
    if (!$("#notifs").hidden && !e.target.closest("#notifs") && !e.target.closest('[data-act="toggleNotifs"]')) $("#notifs").hidden = true;
    if (!e.target.closest("#mentionBox") && $("#mentionBox")) $("#mentionBox").remove();
    if (!el || el.disabled) return;
    const link = e.target.closest("a[href]");
    if (link && link !== el && el.contains(link)) return;
    const fn = ACT[el.dataset.act];
    if (!fn) return;
    if (el.tagName === "A" || el.tagName === "BUTTON") e.preventDefault();
    Promise.resolve(fn(el, e)).catch(fail);
  });
  document.addEventListener("change", e => {
    const el = e.target.closest("[data-change]");
    if (el && CHG[el.dataset.change]) Promise.resolve(CHG[el.dataset.change](el, e)).catch(fail);
  });
  document.addEventListener("submit", e => {
    const form = e.target.closest("form[data-form]");
    if (!form || !FORMS[form.dataset.form]) return;
    e.preventDefault();
    Promise.resolve(FORMS[form.dataset.form](form)).catch(fail);
  });
  document.addEventListener("input", e => {
    const el = e.target;
    if (el.dataset && el.dataset.draft) {
      clearTimeout(S.draftTimer);
      const kind = el.dataset.draft, text = el.value;
      S.draftTimer = setTimeout(() => saveDraft(kind, text), 300);
    }
    if (el.id === "q") {
      clearTimeout(S.qTimer);
      S.qTimer = setTimeout(() => { S.query = el.value; renderView(); }, 120);
      return;
    }
    if (el.id === "palQ") { S.palIndex = 0; renderPalette(); return; }
    if (el.id === "descBox") S.descDraft = el.value;
    if (el.matches("[data-mention]")) mentionSuggest(el);
    if (el.dataset.input === "dupes") {
      const hits = similar(parseQuick(el.value).title || "");
      $("#dupes").innerHTML = hits.length ? '<p class="muted small">Similar work already exists:</p>' + hits.map(h => '<a href="#/item/' + esc(h.key) + '" class="dupe">' + esc(h.key) + " " + esc(h.title) + " " + statusPill(h.status) + "</a>").join("") : "";
    }
    if (el.dataset.input === "suggestKey") {
      const keyIn = fld(el.closest("form"), "key");
      if (!keyIn.dataset.touched) {
        let k = el.value.split(/\s+/).filter(Boolean).map(w => w[0]).join("").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 4);
        if (k.length < 2) k = el.value.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
        keyIn.value = /^[A-Z]/.test(k) ? k : "";
      }
    }
    if (el.getAttribute("name") === "key" && el.closest('form[data-form="newSpace"]')) el.dataset.touched = "1";
  });
  $("#q").addEventListener("focus", () => { if (S.space) $("#qhelp").hidden = false; });
  $("#q").addEventListener("blur", () => setTimeout(() => ($("#qhelp").hidden = true), 150));

  document.addEventListener("keydown", e => {
    const t = e.target, typing = /INPUT|TEXTAREA|SELECT/.test(t.tagName) || t.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#palette").hidden ? openPalette() : closePalette(); return; }
    if (!$("#palette").hidden) {
      if (e.key === "Escape") { e.preventDefault(); closePalette(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); S.palIndex = Math.min(S.palIndex + 1, S.palCmds.length - 1); renderPalette(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); S.palIndex = Math.max(S.palIndex - 1, 0); renderPalette(); }
      else if (e.key === "Enter") { e.preventDefault(); runPalette(S.palIndex); }
      return;
    }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      if (t.id === "cBody") { e.preventDefault(); ACT.addComment(); return; }
      if (t.id === "descBox") { e.preventDefault(); ACT.saveDesc(); return; }
      if (t.id === "cEdit") { e.preventDefault(); const b = document.querySelector('[data-act="saveComment"]'); if (b) ACT.saveComment(b); return; }
    }
    if (e.key === "Enter" && t.matches && t.matches("input[data-quick]")) { e.preventDefault(); quickCreate(t); return; }
    if (e.key === "Enter" && t.matches && t.matches(".card[data-key]")) { e.preventDefault(); go("#/item/" + t.dataset.key); return; }
    if (e.key === "Escape") {
      if ($("#mentionBox")) { $("#mentionBox").remove(); e.preventDefault(); return; }
      if (!$("#notifs").hidden) { $("#notifs").hidden = true; return; }
      if (S.descEdit && t.id === "descBox") { e.preventDefault(); S.descEdit = false; renderDialog(); return; }
    }
    if (typing || e.ctrlKey || e.metaKey || e.altKey || $("#dlg").open || $("#modal").open || !S.me || $("#app").hidden) return;
    if (e.key === "c") { e.preventDefault(); openCreate(); }
    else if (e.key === "/") { e.preventDefault(); $("#q").focus(); }
    else if (/^[1-8]$/.test(e.key) && S.space) { e.preventDefault(); go("#/s/" + S.space.key + "/" + VIEWS[+e.key - 1][0]); }
  });

  $("#dlg").addEventListener("close", () => { if (S.openKey) closeDialog(); });
  $("#dlg").addEventListener("click", e => { if (e.target === $("#dlg")) closeDialog(); });
  $("#modal").addEventListener("click", e => { if (e.target === $("#modal")) $("#modal").close(); });
  $("#palette").addEventListener("click", e => { if (e.target === $("#palette")) closePalette(); });

  document.addEventListener("dragstart", e => {
    const el = e.target.closest && e.target.closest("[data-drag]");
    if (!el || !canEdit()) return;
    S.dragging = el.dataset.drag;
    e.dataTransfer.setData("text/plain", S.dragging);
    e.dataTransfer.effectAllowed = "move";
    el.classList.add("dragging");
  });
  document.addEventListener("dragend", () => { S.dragging = null; $$(".dragging, .over").forEach(x => x.classList.remove("dragging", "over")); });
  document.addEventListener("dragover", e => {
    const files = e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
    const fz = files && e.target.closest && e.target.closest("[data-filedrop]");
    if (fz) { e.preventDefault(); fz.classList.add("over"); return; }
    const z = e.target.closest && e.target.closest("[data-drop]");
    if (z && S.dragging) { e.preventDefault(); $$(".over").forEach(x => x !== z && x.classList.remove("over")); z.classList.add("over"); }
  });
  document.addEventListener("dragleave", e => {
    const z = e.target.closest && e.target.closest("[data-drop], [data-filedrop]");
    if (z && !z.contains(e.relatedTarget)) z.classList.remove("over");
  });
  document.addEventListener("drop", e => {
    const fz = e.target.closest && e.target.closest("[data-filedrop]");
    if (fz && e.dataTransfer.files.length) { e.preventDefault(); fz.classList.remove("over"); uploadFiles(e.dataTransfer.files); return; }
    const z = e.target.closest && e.target.closest("[data-drop]");
    if (!z || !S.dragging) return;
    e.preventDefault();
    z.classList.remove("over");
    const key = S.dragging;
    S.dragging = null;
    DROP[z.dataset.drop](z, key, e);
  });

  window.addEventListener("hashchange", () => { if (S.me) route(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  API.onUnauthorized = () => { if (S.me) { toast("Your session ended. Sign in again."); logout(); } };

  /* ---------- boot ---------- */
  applyTheme();
  setInterval(poll, 15000);
  (async function boot() {
    if (!API.load()) return showAuth();
    try { await start(); } catch (e) { if (e.status === 401) showAuth(); else { fail(e); showAuth(); } }
  })();

  window.Freehold = { S, parseQuick, route, uploadFiles, openItem, saveItem };
})();
