# OpenTrack

Free, open-source, self-hosted work tracker (a Jira alternative), released free to the public. Status: beta. Phase 1 of the roadmap in README.md is built: real backend, accounts and space roles, markdown with attachments, personal notification rules, Jira import, one-command Docker install.

## Commands

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080      # from backend/, SQLite in backend/data/
pytest -q                                      # from backend/, API tests on SQLite
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/opentrack_test pytest -q
sh frontend/tests/run.sh                       # UI click-through, own server on :8099, needs Node 18+
docker compose up -d --build                   # full stack on http://localhost:8080
```

Run pytest and the UI test before every commit. CI (.github/workflows/ci.yml) runs both, plus PostgreSQL.

## Architecture

backend/app (FastAPI, SQLAlchemy 2, PostgreSQL or SQLite):
- `main.py`: app, security headers and CSP, serves `frontend/` as static files, digest email loop.
- `models.py`: Space.statuses is JSON `[{name, category: todo|doing|done, wip}]`; Membership roles viewer|member|admin; Sprint states future|active|closed; WorkItem has multiple assignees and watchers via association tables; Link is one row per link (blocks, relates to, duplicates) and inverse labels are computed.
- `security.py`: scrypt passwords, JWT bearer tokens. `get_space(db, key, user, need)` is the single permission check. Downloads and exports also accept `?token=`.
- `services.py`: `apply_changes()` validates every field change, writes History and sends notifications; `create_item()` builds new items. Routers go through these, never set WorkItem fields directly.
- `query.py`: the OQL query language. `frontend/js/oql.js` mirrors it; change both and keep the same test cases passing in each.
- `notify.py`: per-user prefs (event x in-app/email, instant/digest/off, muted items). `dispatch()` is the only way to notify anyone.
- `reports.py`: burndown, velocity, cumulative flow, created vs resolved, cycle time, all rebuilt from History. Invariant: each item's first History row has field `created` with the starting status as `new_value`; later status changes use field `status`.
- `importer.py`: Jira CSV (duplicate column names, comments as `date;account;text`, seconds to hours, backdated history) and OpenTrack JSON (own export and the old browser prototype backup).
- `routers/`: `auth_users`, `spaces` (members, sprints, filters, activity, `/changes` polling), `items` (bulk, comments, links, worklogs, watch, mute, attachments, search), `reports_io` (reports, notifications, import, export).

frontend/ (plain JavaScript, no build step, no CDNs, classic scripts sharing globals):
- `js/api.js` fetch wrapper with the token in localStorage; `js/md.js` escape-first markdown; `js/oql.js`; `js/charts.js` SVG charts; `js/app.js` everything else (state `S`, hash router `#/s/KEY/view` and `#/item/KEY`, views, dialogs, events).
- The browser loads one space bundle (`GET /api/spaces/KEY`), filters in memory, saves optimistically through `saveItem()`, and polls `/changes` every 15 seconds.

## Conventions

- The CSP forbids inline scripts and handlers. Wire events with `data-act` (click), `data-change`, `data-form` (submit) and `data-drop` attributes and the `ACT`, `CHG`, `FORMS` and `DROP` maps in app.js.
- Escape all user text with `MD.esc` or render it with `MD.render`. Never build HTML from raw user input.
- Read form fields with `fld(form, name)`, not `form.name` (in browsers that returns the form's own name attribute).
- Keep the frontend dependency-free so it runs on networks without internet access.
- Timestamps are naive UTC in the database (`db.utcnow()`); date-only fields travel as ISO strings.
- UI copy: sentence case, plain verbs, buttons say what happens ("Save workflow"), errors say how to fix the problem.
- Write docs, UI text and commit messages without em dashes.
- Commit messages: short imperative subject, no AI attribution trailers or session links (also turned off in `.claude/settings.json`).

## Next work, roughly in order

1. Verify the Docker image. `docker compose up -d --build` has never been run (it was built without Docker). Fix anything that breaks.
2. Add Alembic migrations with a baseline matching models.py, replacing `create_all` on startup.
3. Phase 1 gate: a real team runs sprints on it. Expect fixes from that.
4. Phase 2, depth on demand: custom fields and forms, workflow transition rules and approvals, a visual query builder over OQL, dashboards.
5. Smaller gaps: Jira import of attachments, links and custom fields; server-sent events instead of polling; password reset by email; login rate limiting; per-user time zones (digests are UTC); paging the space bundle for very large spaces; an accessibility audit.
6. There is no LICENSE yet. The owner decides between AGPL-3.0 and MIT or Apache-2.0; ask before adding one.

## Testing notes

- `backend/tests/test_api.py`: 9 end-to-end tests. conftest uses a temp data dir and SQLite unless `DATABASE_URL` is set.
- `frontend/tests`: `seed.py` creates demo data and `smoke.js` drives the app in jsdom (57 checks). jsdom lacks `dialog.showModal` and named form access, so the test polyfills dialogs and the app uses `fld()`.
- For visual review, screenshot desktop (1440x900) and mobile (390x844) with a headless browser. Past bugs only showed up this way, such as a `.bar` class collision that flattened the SVG bar charts.
