"""Freehold Query Language (OQL): a small, JQL-style filter language.

    assignee = me AND status != Done
    type in (Bug, Task) and priority:high due < 7d
    label:payments OR is:blocked ORDER BY priority DESC, due
    "checkout flow" -is:done         (free text; quote phrases)

The browser has a mirror of this parser (frontend/oql.js) so filtering feels instant.
"""
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

TOKEN_RE = re.compile(
    r'\s*(?:(?P<lp>\()|(?P<rp>\))|(?P<comma>,)|(?P<str>"(?:[^"\\]|\\.)*")'
    r'|(?P<op>!=|<=|>=|=|<|>|~|:)|(?P<word>[^\s()",=<>!~:]+))'
)
PRIORITY_ORDER = ["Highest", "High", "Medium", "Low"]
ALIASES = {
    "summary": "title", "issuetype": "type", "worktype": "type", "labels": "label", "epic": "parent",
    "duedate": "due", "startdate": "start", "storypoints": "points", "statuscategory": "category",
    "project": "space", "watchers": "watcher", "assignees": "assignee",
    "fixversion": "version", "fixversions": "version", "release": "version",
}
DATE_FIELDS = {"due": "due", "start": "start", "created": "created_at", "updated": "updated_at",
               "resolved": "resolved_at"}
NUM_FIELDS = {"points": "points", "estimate": "estimate", "logged": "logged"}
EXACT_FIELDS = {"priority", "type", "category", "space", "key"}  # "priority:high" must not match Highest


class QueryError(ValueError):
    pass


@dataclass
class Context:
    users: dict = field(default_factory=dict)        # id -> {"name","handle","email"}
    sprints: dict = field(default_factory=dict)      # id -> {"name","state"}
    versions: dict = field(default_factory=dict)     # id -> {"name","released"}
    custom: dict = field(default_factory=dict)       # custom field key -> type
    categories: dict = field(default_factory=dict)   # status name -> todo|doing|done
    parents: dict = field(default_factory=dict)      # key -> title
    blocked: set = field(default_factory=set)        # keys blocked by an unfinished item
    me: int | None = None
    stale_days: int = 14
    today: date = field(default_factory=date.today)


def tokenize(q: str) -> list[tuple[str, str]]:
    toks, pos, q = [], 0, q or ""
    while pos < len(q):
        m = TOKEN_RE.match(q, pos)
        if not m:
            if q[pos:].strip() == "":
                break
            raise QueryError(f"Unexpected character '{q[pos]}' at position {pos + 1}.")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "str":
            val = val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        toks.append((kind, val))
    return toks


class _Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    @staticmethod
    def word(tok, *words):
        return tok[0] == "word" and tok[1].lower() in words

    def parse(self):
        order = []
        for j in range(len(self.t) - 1):
            if self.word(self.t[j], "order") and self.word(self.t[j + 1], "by"):
                order = self.parse_order(self.t[j + 2:])
                self.t = self.t[:j]
                break
        expr = self.parse_or() if self.t else None
        if self.i < len(self.t):
            raise QueryError(f"Unexpected '{self.t[self.i][1]}'.")
        return expr, order

    def parse_order(self, toks):
        out, i = [], 0
        while i < len(toks):
            kind, val = toks[i]
            if kind == "comma":
                i += 1
                continue
            if kind != "word":
                raise QueryError("ORDER BY needs field names, like ORDER BY priority DESC.")
            direction = "asc"
            if i + 1 < len(toks) and self.word(toks[i + 1], "asc", "desc"):
                direction = toks[i + 1][1].lower()
                i += 1
            out.append((ALIASES.get(val.lower(), val.lower()), direction))
            i += 1
        return out

    def parse_or(self):
        left = self.parse_and()
        while self.word(self.peek(), "or"):
            self.next()
            left = ("or", left, self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_not()
        while True:
            tok = self.peek()
            if tok[0] is None or tok[0] == "rp" or self.word(tok, "or"):
                return left
            if self.word(tok, "and"):
                self.next()
            left = ("and", left, self.parse_not())

    def parse_not(self):
        tok = self.peek()
        if self.word(tok, "not") and not self.word(self.peek(1), "in"):
            self.next()
            return ("not", self.parse_not())
        if tok[0] == "word" and tok[1].startswith("-") and len(tok[1]) > 1:
            # -is:done or -word means NOT
            self.t[self.i] = ("word", tok[1][1:])
            return ("not", self.parse_atom())
        return self.parse_atom()

    def parse_atom(self):
        tok = self.next()
        if tok[0] is None:
            raise QueryError("The query ends too early.")
        if tok[0] == "lp":
            expr = self.parse_or()
            if self.next()[0] != "rp":
                raise QueryError("A closing parenthesis is missing.")
            return expr
        if tok[0] == "str":
            return ("text", tok[1])
        if tok[0] != "word":
            raise QueryError(f"Unexpected '{tok[1]}'.")
        name, nxt = tok[1].lower(), self.peek()
        if nxt[0] == "op":
            self.next()
            return ("clause", name, nxt[1], [self.parse_value()])
        if self.word(nxt, "in"):
            self.next()
            return ("clause", name, "in", self.parse_list())
        if self.word(nxt, "not") and self.word(self.peek(1), "in"):
            self.next()
            self.next()
            return ("clause", name, "not in", self.parse_list())
        if self.word(nxt, "is") and name != "is":
            self.next()
            negate = False
            if self.word(self.peek(), "not"):
                self.next()
                negate = True
            val = self.next()
            if not self.word(val, "empty", "null"):
                raise QueryError("Use IS EMPTY or IS NOT EMPTY.")
            return ("clause", name, "is not" if negate else "is", ["empty"])
        return ("text", tok[1])

    def parse_value(self):
        tok = self.next()
        if tok[0] not in ("word", "str"):
            raise QueryError("A value is missing after the operator.")
        val = tok[1]
        if tok[0] == "word" and self.peek()[0] == "lp" and self.peek(1)[0] == "rp":
            self.next()
            self.next()
            val += "()"
        return val

    def parse_list(self):
        if self.next()[0] != "lp":
            raise QueryError("IN needs a list, like status in (Done, \"In review\").")
        vals = []
        while True:
            tok = self.peek()
            if tok[0] == "rp":
                self.next()
                return vals
            if tok[0] is None:
                raise QueryError("A closing parenthesis is missing.")
            if tok[0] == "comma":
                self.next()
                continue
            vals.append(self.parse_value())


def parse(q: str):
    return _Parser(tokenize(q)).parse()


def parse_date(value: str, today: date) -> date:
    s = value.lower()
    if s in ("today", "today()", "now", "now()"):
        return today
    m = re.fullmatch(r"([+-]?)(\d+)([dwm])", s)
    if m:
        days = int(m.group(2)) * {"d": 1, "w": 7, "m": 30}[m.group(3)]
        return today + timedelta(days=-days if m.group(1) == "-" else days)
    if s == "startofweek()":
        return today - timedelta(days=today.weekday())
    if s == "endofweek()":
        return today + timedelta(days=6 - today.weekday())
    if s == "startofmonth()":
        return today.replace(day=1)
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise QueryError(f"'{value}' is not a date. Try 2026-10-01, today, -7d or 2w.")


def _compare(a, op, b):
    return {"=": a == b, ":": a == b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}.get(op, False)


def _user_hit(uid, value, ctx, exact):
    v = value.lower()
    if v in ("me", "currentuser()"):
        return uid == ctx.me
    u = ctx.users.get(uid)
    if not u:
        return False
    names = (u["name"].lower(), u["handle"].lower(), u["email"].lower())
    return v in names if exact else any(v in n for n in names)


def _strings(f, item, ctx):
    if f == "key":
        return [item["key"]]
    if f == "title":
        return [item["title"]]
    if f == "description":
        return [item.get("description") or ""]
    if f == "text":
        return [item["key"], item["title"], item.get("description") or ""] + list(item["labels"])
    if f == "status":
        return [item["status"]]
    if f == "category":
        return [ctx.categories.get(item["status"], "todo")]
    if f == "type":
        return [item["type"]]
    if f == "priority":
        return [item["priority"]]
    if f == "label":
        return list(item["labels"])
    if f == "parent":
        pk = item.get("parent_key")
        return [pk, ctx.parents.get(pk, "")] if pk else []
    if f == "sprint":
        s = ctx.sprints.get(item.get("sprint_id"))
        return [s["name"], s["state"]] if s else ["backlog"]
    if f == "version":
        v = ctx.versions.get(item.get("version_id"))
        return [v["name"], "released" if v["released"] else "unreleased"] if v else ["none"]
    if f == "space":
        return [item["key"].split("-")[0]]
    if f in ctx.custom:
        raw = (item.get("custom") or {}).get(f)
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(v) for v in raw]
        if ctx.custom[f] == "user":
            who = ctx.users.get(raw)
            return [who["name"], who["handle"]] if who else [str(raw)]
        return [str(raw)]
    return None


def _is_stale(item, ctx) -> bool:
    """Sitting in the same status too long. Finished work is never stale, and neither is anything
    still in a to-do column: not started is a backlog question, not a rot question."""
    if ctx.categories.get(item["status"]) != "doing":
        return False
    since = item.get("status_since")
    if not since:
        return False
    try:
        moved = date.fromisoformat(str(since)[:10])
    except ValueError:
        return False
    return (ctx.today - moved).days >= ctx.stale_days


def _is(value, item, ctx):
    v = value.lower()
    done = ctx.categories.get(item["status"]) == "done"
    checks = {
        "open": not done, "done": done, "closed": done, "resolved": done,
        "blocked": item["key"] in ctx.blocked,
        "overdue": bool(item.get("due")) and item["due"] < ctx.today.isoformat() and not done,
        "unassigned": not item["assignee_ids"], "assigned": bool(item["assignee_ids"]),
        "mine": ctx.me in item["assignee_ids"], "watching": ctx.me in item.get("watcher_ids", []),
        "backlog": item.get("sprint_id") is None, "epic": item["type"] == "Epic",
        "unversioned": item.get("version_id") is None,
        "stale": _is_stale(item, ctx),
    }
    if v not in checks:
        raise QueryError(f"is:{value} is not supported. Try is:open, is:done, is:blocked, is:overdue or is:mine.")
    return checks[v]


def _empty(f, item, ctx=None):
    if f == "assignee":
        return not item["assignee_ids"]
    if f == "reporter":
        return not item.get("reporter_id")
    if f == "version":
        return not item.get("version_id")
    if f == "label":
        return not item["labels"]
    if f == "sprint":
        return item.get("sprint_id") is None
    if f == "parent":
        return not item.get("parent_key")
    if f in DATE_FIELDS:
        return not item.get(DATE_FIELDS[f])
    if f in NUM_FIELDS:
        return item.get(NUM_FIELDS[f]) in (None, 0)
    if f == "description":
        return not (item.get("description") or "").strip()
    if ctx and f in ctx.custom:
        v = (item.get("custom") or {}).get(f)
        return v is None or v == "" or v == []
    raise QueryError(f"'{f}' cannot be checked for EMPTY.")


def _clause(name, op, values, item, ctx):
    f = ALIASES.get(name, name)
    if f == "is":
        return _is(values[0], item, ctx)
    if op in ("is", "is not"):
        return _empty(f, item, ctx) == (op == "is")
    if op in ("in", "not in"):
        hit = any(_clause(name, "=", [v], item, ctx) for v in values)
        return hit if op == "in" else not hit
    if op == "!=":
        return not _clause(name, "=", values, item, ctx)
    value = values[0]
    if value.lower() in ("empty", "null") and op in ("=", ":"):
        return _empty(f, item, ctx)
    if f in ctx.custom and ctx.custom[f] == "user":
        raw = (item.get("custom") or {}).get(f)
        if raw is None:
            return False
        return _user_hit(raw, value, ctx, exact=False)
    if f in ctx.custom and ctx.custom[f] in ("number", "date", "checkbox"):
        raw = (item.get("custom") or {}).get(f)
        if raw is None:
            return False
        kind = ctx.custom[f]
        if kind == "number":
            try:
                return _compare(float(raw), op, float(value))
            except (TypeError, ValueError):
                raise QueryError(f"'{value}' is not a number, and {f} holds numbers.")
        if kind == "date":
            return _compare(date.fromisoformat(str(raw)[:10]), op, parse_date(value, ctx.today))
        if kind == "checkbox":
            want = value.lower() in ("true", "yes", "1")
            return bool(raw) == want
    if f in DATE_FIELDS:
        raw = item.get(DATE_FIELDS[f])
        if not raw:
            return False
        return _compare(date.fromisoformat(raw[:10]), op, parse_date(value, ctx.today))
    if f in NUM_FIELDS:
        raw = item.get(NUM_FIELDS[f])
        try:
            target = float(value)
        except ValueError:
            raise QueryError(f"{name} needs a number.")
        return raw is not None and _compare(float(raw), op, target)
    if f in ("assignee", "reporter", "watcher"):
        ids = {"assignee": item["assignee_ids"], "watcher": item.get("watcher_ids", []),
               "reporter": [item["reporter_id"]] if item.get("reporter_id") else []}[f]
        if value.lower() == "unassigned":
            return not ids
        return any(_user_hit(u, value, ctx, exact=(op == "=")) for u in ids)
    strings = _strings(f, item, ctx)
    if strings is None:
        raise QueryError(f"Unknown field '{name}'. Try status, assignee, type, priority, label, sprint, due or text.")
    v = value.lower()
    if op == "=" or (op == ":" and f in EXACT_FIELDS):
        return any(s.lower() == v for s in strings)
    if op in (":", "~"):
        return any(v in s.lower() for s in strings)
    raise QueryError(f"'{op}' does not work with {name}.")


def evaluate(node, item, ctx) -> bool:
    kind = node[0]
    if kind == "and":
        return evaluate(node[1], item, ctx) and evaluate(node[2], item, ctx)
    if kind == "or":
        return evaluate(node[1], item, ctx) or evaluate(node[2], item, ctx)
    if kind == "not":
        return not evaluate(node[1], item, ctx)
    if kind == "text":
        t = node[1].lower()
        return any(t in s.lower() for s in _strings("text", item, ctx))
    return _clause(node[1], node[2], node[3], item, ctx)


def _sort_key(f, item, ctx):
    if f == "key":
        return (0, int(item["key"].split("-")[-1]))
    if f == "priority":
        p = item["priority"]
        return (0, PRIORITY_ORDER.index(p) if p in PRIORITY_ORDER else 9)
    if f in DATE_FIELDS:
        v = item.get(DATE_FIELDS[f])
        return (0 if v else 1, v or "")
    if f in NUM_FIELDS:
        v = item.get(NUM_FIELDS[f])
        return (0 if v is not None else 1, v or 0)
    if f == "rank":
        return (0, item.get("rank") or 0)
    strings = _strings(f, item, ctx)
    return (0, (strings[0] if strings else "").lower())


def run(q: str, items: list[dict], ctx: Context) -> list[dict]:
    expr, order = parse(q)
    out = [it for it in items if expr is None or evaluate(expr, it, ctx)]
    for f, direction in reversed(order):
        out.sort(key=lambda it: _sort_key(f, it, ctx), reverse=direction == "desc")
    return out
