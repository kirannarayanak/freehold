/* Freehold Query Language in the browser. Mirrors backend/app/query.py so filtering is instant. */
(function () {
  const PRIORITY_ORDER = ["Highest", "High", "Medium", "Low"];
  const ALIASES = { summary: "title", issuetype: "type", worktype: "type", labels: "label", epic: "parent",
    duedate: "due", startdate: "start", storypoints: "points", statuscategory: "category", project: "space",
    watchers: "watcher", assignees: "assignee",
    fixversion: "version", fixversions: "version", release: "version" };
  const DATE_FIELDS = { due: "due", start: "start", created: "created_at", updated: "updated_at", resolved: "resolved_at" };
  const NUM_FIELDS = { points: "points", estimate: "estimate", logged: "logged" };
  const EXACT_FIELDS = new Set(["priority", "type", "category", "space", "key"]);
  const TOKEN_RE = /\s*(?:(\()|(\))|(,)|("(?:[^"\\]|\\.)*")|(!=|<=|>=|=|<|>|~|:)|([^\s()",=<>!~:]+))/y;

  class QueryError extends Error {}

  function tokenize(q) {
    const toks = [];
    q = q || "";
    TOKEN_RE.lastIndex = 0;
    let pos = 0;
    while (pos < q.length) {
      TOKEN_RE.lastIndex = pos;
      const m = TOKEN_RE.exec(q);
      if (!m) {
        if (!q.slice(pos).trim()) break;
        throw new QueryError("Unexpected character '" + q[pos] + "' at position " + (pos + 1) + ".");
      }
      pos = TOKEN_RE.lastIndex;
      if (m[1]) toks.push(["lp", "("]);
      else if (m[2]) toks.push(["rp", ")"]);
      else if (m[3]) toks.push(["comma", ","]);
      else if (m[4]) toks.push(["str", m[4].slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, "\\")]);
      else if (m[5]) toks.push(["op", m[5]]);
      else if (m[6]) toks.push(["word", m[6]]);
    }
    return toks;
  }

  function parse(q) {
    let t = tokenize(q), i = 0;
    const peek = (k = 0) => t[i + k] || [null, null];
    const next = () => t[i++] || [null, null];
    const isWord = (tok, ...w) => tok[0] === "word" && w.includes(tok[1].toLowerCase());
    let order = [];
    for (let j = 0; j < t.length - 1; j++) {
      if (isWord(t[j], "order") && isWord(t[j + 1], "by")) {
        const rest = t.slice(j + 2);
        t = t.slice(0, j);
        for (let k = 0; k < rest.length; k++) {
          const [kind, val] = rest[k];
          if (kind === "comma") continue;
          if (kind !== "word") throw new QueryError("ORDER BY needs field names, like ORDER BY priority DESC.");
          let dir = "asc";
          if (rest[k + 1] && isWord(rest[k + 1], "asc", "desc")) { dir = rest[k + 1][1].toLowerCase(); k++; }
          order.push([ALIASES[val.toLowerCase()] || val.toLowerCase(), dir]);
        }
        break;
      }
    }
    function value() {
      const tok = next();
      if (tok[0] !== "word" && tok[0] !== "str") throw new QueryError("A value is missing after the operator.");
      let v = tok[1];
      if (tok[0] === "word" && peek()[0] === "lp" && peek(1)[0] === "rp") { next(); next(); v += "()"; }
      return v;
    }
    function list() {
      if (next()[0] !== "lp") throw new QueryError('IN needs a list, like status in (Done, "In review").');
      const vals = [];
      for (;;) {
        const tok = peek();
        if (tok[0] === "rp") { next(); return vals; }
        if (tok[0] === null) throw new QueryError("A closing parenthesis is missing.");
        if (tok[0] === "comma") { next(); continue; }
        vals.push(value());
      }
    }
    function atom() {
      const tok = next();
      if (tok[0] === null) throw new QueryError("The query ends too early.");
      if (tok[0] === "lp") { const e = orExpr(); if (next()[0] !== "rp") throw new QueryError("A closing parenthesis is missing."); return e; }
      if (tok[0] === "str") return ["text", tok[1]];
      if (tok[0] !== "word") throw new QueryError("Unexpected '" + tok[1] + "'.");
      const name = tok[1].toLowerCase(), nx = peek();
      if (nx[0] === "op") { next(); return ["clause", name, nx[1], [value()]]; }
      if (isWord(nx, "in")) { next(); return ["clause", name, "in", list()]; }
      if (isWord(nx, "not") && isWord(peek(1), "in")) { next(); next(); return ["clause", name, "not in", list()]; }
      if (isWord(nx, "is") && name !== "is") {
        next();
        let neg = false;
        if (isWord(peek(), "not")) { next(); neg = true; }
        const v = next();
        if (!isWord(v, "empty", "null")) throw new QueryError("Use IS EMPTY or IS NOT EMPTY.");
        return ["clause", name, neg ? "is not" : "is", ["empty"]];
      }
      return ["text", tok[1]];
    }
    function notExpr() {
      const tok = peek();
      if (isWord(tok, "not") && !isWord(peek(1), "in")) { next(); return ["not", notExpr()]; }
      if (tok[0] === "word" && tok[1].length > 1 && tok[1][0] === "-") { t[i] = ["word", tok[1].slice(1)]; return ["not", atom()]; }
      return atom();
    }
    function andExpr() {
      let left = notExpr();
      for (;;) {
        const tok = peek();
        if (tok[0] === null || tok[0] === "rp" || isWord(tok, "or")) return left;
        if (isWord(tok, "and")) next();
        left = ["and", left, notExpr()];
      }
    }
    function orExpr() {
      let left = andExpr();
      while (isWord(peek(), "or")) { next(); left = ["or", left, andExpr()]; }
      return left;
    }
    const expr = t.length ? orExpr() : null;
    if (i < t.length) throw new QueryError("Unexpected '" + t[i][1] + "'.");
    return { expr, order };
  }

  const pad = n => String(n).padStart(2, "0");
  const isoDay = d => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
  function addDays(d, n) { const x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() + n); return x; }

  function parseDate(v, today) {
    const s = v.toLowerCase();
    if (["today", "today()", "now", "now()"].includes(s)) return isoDay(today);
    const m = s.match(/^([+-]?)(\d+)([dwm])$/);
    if (m) { const n = +m[2] * { d: 1, w: 7, m: 30 }[m[3]]; return isoDay(addDays(today, m[1] === "-" ? -n : n)); }
    if (s === "startofweek()") return isoDay(addDays(today, -((today.getDay() + 6) % 7)));
    if (s === "endofweek()") return isoDay(addDays(today, 6 - ((today.getDay() + 6) % 7)));
    if (s === "startofmonth()") return isoDay(new Date(today.getFullYear(), today.getMonth(), 1));
    if (/^\d{4}-\d{2}-\d{2}/.test(v)) return v.slice(0, 10);
    throw new QueryError("'" + v + "' is not a date. Try 2026-10-01, today, -7d or 2w.");
  }

  function cmp(a, op, b) {
    switch (op) { case "=": case ":": return a === b; case "<": return a < b; case ">": return a > b; case "<=": return a <= b; case ">=": return a >= b; }
    return false;
  }
  function userHit(uid, value, ctx, exact) {
    const v = value.toLowerCase();
    if (v === "me" || v === "currentuser()") return uid === ctx.me;
    const u = ctx.users[uid];
    if (!u) return false;
    const names = [u.name.toLowerCase(), u.handle.toLowerCase(), u.email.toLowerCase()];
    return exact ? names.includes(v) : names.some(n => n.includes(v));
  }
  function strings(f, it, ctx) {
    switch (f) {
      case "key": return [it.key];
      case "title": return [it.title];
      case "description": return [it.description || ""];
      case "text": return [it.key, it.title, it.description || ""].concat(it.labels || []);
      case "status": return [it.status];
      case "category": return [ctx.categories[it.status] || "todo"];
      case "type": return [it.type];
      case "priority": return [it.priority];
      case "label": return (it.labels || []).slice();
      case "parent": return it.parent_key ? [it.parent_key, ctx.parents[it.parent_key] || ""] : [];
      case "sprint": { const s = ctx.sprints[it.sprint_id]; return s ? [s.name, s.state] : ["backlog"]; }
      case "version": { const v = (ctx.versions || {})[it.version_id];
        return v ? [v.name, v.released ? "released" : "unreleased"] : ["none"]; }
      case "space": return [it.key.split("-")[0]];
      default: break;
    }
    if (ctx.custom && f in ctx.custom) {
      const raw = (it.custom || {})[f];
      if (raw == null) return [];
      if (Array.isArray(raw)) return raw.map(String);
      if (ctx.custom[f] === "user") {
        const who = ctx.users[raw];
        return who ? [who.name, who.handle] : [String(raw)];
      }
      return [String(raw)];
    }
    return null;
  }
  // Mirrors _is_stale in query.py: only work in progress rots, and it is measured from the last
  // status change rather than from creation.
  function isStale(it, ctx) {
    if ((ctx.categories || {})[it.status] !== "doing" || !it.status_since) return false;
    const moved = new Date(String(it.status_since).slice(0, 10));
    if (isNaN(moved)) return false;
    return Math.floor((ctx.today - moved) / 86400000) >= (ctx.staleDays || 14);
  }

  function isCheck(value, it, ctx) {
    const v = value.toLowerCase(), done = ctx.categories[it.status] === "done";
    const checks = { open: !done, done, closed: done, resolved: done, blocked: ctx.blocked.has(it.key),
      overdue: !!it.due && it.due < ctx.todayIso && !done, unassigned: !it.assignee_ids.length, assigned: !!it.assignee_ids.length,
      mine: it.assignee_ids.includes(ctx.me), watching: (it.watcher_ids || []).includes(ctx.me),
      backlog: it.sprint_id == null, epic: it.type === "Epic",
      unversioned: it.version_id == null, stale: isStale(it, ctx) };
    if (!(v in checks)) throw new QueryError("is:" + value + " is not supported. Try is:open, is:done, is:blocked, is:overdue or is:mine.");
    return checks[v];
  }
  function empty(f, it, ctx) {
    if (ctx && ctx.custom && f in ctx.custom) {
      const v = (it.custom || {})[f];
      return v == null || v === "" || (Array.isArray(v) && !v.length);
    }
    if (f === "assignee") return !it.assignee_ids.length;
    if (f === "reporter") return !it.reporter_id;
    if (f === "version") return it.version_id == null;
    if (f === "label") return !(it.labels || []).length;
    if (f === "sprint") return it.sprint_id == null;
    if (f === "parent") return !it.parent_key;
    if (f in DATE_FIELDS) return !it[DATE_FIELDS[f]];
    if (f in NUM_FIELDS) return it[NUM_FIELDS[f]] == null || it[NUM_FIELDS[f]] === 0;
    if (f === "description") return !(it.description || "").trim();
    throw new QueryError("'" + f + "' cannot be checked for EMPTY.");
  }
  function clause(name, op, values, it, ctx) {
    const f = ALIASES[name] || name;
    if (f === "is") return isCheck(values[0], it, ctx);
    if (op === "is" || op === "is not") return empty(f, it, ctx) === (op === "is");
    if (op === "in" || op === "not in") { const hit = values.some(v => clause(name, "=", [v], it, ctx)); return op === "in" ? hit : !hit; }
    if (op === "!=") return !clause(name, "=", values, it, ctx);
    const value = values[0];
    if (["empty", "null"].includes(value.toLowerCase()) && (op === "=" || op === ":")) return empty(f, it, ctx);
    const kind = ctx.custom ? ctx.custom[f] : undefined;
    if (kind) {
      const raw = (it.custom || {})[f];
      if (raw == null) return false;
      if (kind === "user") return userHit(raw, value, ctx, op === "=");
      if (kind === "number") {
        const target = Number(value);
        if (isNaN(target)) throw new QueryError("'" + value + "' is not a number, and " + f + " holds numbers.");
        return cmp(Number(raw), op, target);
      }
      if (kind === "date") return cmp(String(raw).slice(0, 10), op, parseDate(value, ctx.today));
      if (kind === "checkbox") return !!raw === ["true", "yes", "1"].includes(value.toLowerCase());
    }
    if (f in DATE_FIELDS) { const raw = it[DATE_FIELDS[f]]; return !!raw && cmp(raw.slice(0, 10), op, parseDate(value, ctx.today)); }
    if (f in NUM_FIELDS) {
      const target = Number(value);
      if (value.trim() === "" || isNaN(target)) throw new QueryError(name + " needs a number.");
      const raw = it[NUM_FIELDS[f]];
      return raw != null && cmp(Number(raw), op, target);
    }
    if (f === "assignee" || f === "reporter" || f === "watcher") {
      const ids = f === "assignee" ? it.assignee_ids : f === "watcher" ? (it.watcher_ids || []) : (it.reporter_id ? [it.reporter_id] : []);
      if (value.toLowerCase() === "unassigned") return !ids.length;
      return ids.some(u => userHit(u, value, ctx, op === "="));
    }
    const strs = strings(f, it, ctx);
    if (strs === null) throw new QueryError("Unknown field '" + name + "'. Try status, assignee, type, priority, label, sprint, due or text.");
    const v = value.toLowerCase();
    if (op === "=" || (op === ":" && EXACT_FIELDS.has(f))) return strs.some(s => s.toLowerCase() === v);
    if (op === ":" || op === "~") return strs.some(s => s.toLowerCase().includes(v));
    throw new QueryError("'" + op + "' does not work with " + name + ".");
  }
  function evaluate(node, it, ctx) {
    switch (node[0]) {
      case "and": return evaluate(node[1], it, ctx) && evaluate(node[2], it, ctx);
      case "or": return evaluate(node[1], it, ctx) || evaluate(node[2], it, ctx);
      case "not": return !evaluate(node[1], it, ctx);
      case "text": { const t = node[1].toLowerCase(); return strings("text", it, ctx).some(s => s.toLowerCase().includes(t)); }
    }
    return clause(node[1], node[2], node[3], it, ctx);
  }
  function sortKey(f, it, ctx) {
    if (f === "key") return [0, +it.key.split("-").pop()];
    if (f === "priority") { const p = PRIORITY_ORDER.indexOf(it.priority); return [0, p < 0 ? 9 : p]; }
    if (f in DATE_FIELDS) { const v = it[DATE_FIELDS[f]]; return [v ? 0 : 1, v || ""]; }
    if (f in NUM_FIELDS) { const v = it[NUM_FIELDS[f]]; return [v != null ? 0 : 1, v || 0]; }
    if (f === "rank") return [0, it.rank || 0];
    const s = strings(f, it, ctx);
    return [0, ((s && s[0]) || "").toLowerCase()];
  }
  function compareKeys(a, b) { for (let i = 0; i < a.length; i++) { if (a[i] < b[i]) return -1; if (a[i] > b[i]) return 1; } return 0; }

  function run(q, items, ctx) {
    ctx.today = ctx.today || new Date();
    ctx.todayIso = isoDay(ctx.today);
    const { expr, order } = parse(q);
    let out = items.filter(it => !expr || evaluate(expr, it, ctx));
    for (let k = order.length - 1; k >= 0; k--) {
      const [f, dir] = order[k];
      out = out.map((it, idx) => [sortKey(f, it, ctx), idx, it])
        .sort((a, b) => (dir === "desc" ? -1 : 1) * compareKeys(a[0], b[0]) || a[1] - b[1]).map(x => x[2]);
    }
    return { items: out, ordered: order.length > 0 };
  }

  window.OQL = { run, parse, QueryError, isoDay, isStale };
})();
