# Freehold

[![tests](https://github.com/kirannarayanak/freehold/actions/workflows/ci.yml/badge.svg)](https://github.com/kirannarayanak/freehold/actions/workflows/ci.yml)
[![licence: AGPL v3](https://img.shields.io/badge/licence-AGPL--3.0-blue)](LICENSE)

Free, open-source work tracking for software teams. Boards, backlogs, sprints and reports like Jira, without the weight, the per-seat bill or admin-controlled notification schemes. You host it, you own the data, and it starts with one command.

![Sprint board](docs/screenshots/board.png)

> **Status: beta.** This is Phase 1 of the roadmap. Expect rough edges, and use Settings > Export before upgrading.

## Why this exists

Atlassian is ending self-managed Jira. New Data Center subscriptions [closed to new customers on 30 March 2026](https://www.atlassian.com/licensing/data-center-end-of-life); existing customers can renew until 30 March 2028, and everything goes **read-only on 28 March 2029**.

If you want your tracker on your own infrastructure, you can no longer buy Jira for it at any price.

Freehold is a freehold, not a lease: your server, your database, your data, no licence check, no telemetry, and a complete export whenever you want to leave.

## Run it

```bash
docker compose up -d
```

Open http://localhost:8080. The first account you create becomes the site admin. Then:

1. Create a space (Scrum or Kanban).
2. Add teammates under **People**, then add them to the space under **Settings > Members**.
3. Plan in **Backlog**, start a sprint, and work from the **Board**.

To change the port, database password, sign-up policy or email settings, copy `.env.example` to `.env` and edit it before starting.

**Update:** `git pull && docker compose up -d --build`. Your data lives in the `db` and `data` volumes.

**Back up:** `docker compose exec db pg_dump -U freehold freehold > freehold.sql`, plus the `data` volume (attachments and the signing key).

### Without Docker (development)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080
```

This uses SQLite in `backend/data/`. Set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db` for PostgreSQL. The web app in `frontend/` is plain JavaScript with no build step and no CDNs, so it works on locked-down and offline networks. Edit a file and reload.

## Licence

[AGPL-3.0-or-later](LICENSE).

Run it unmodified for your own team and this asks nothing of you. If you **modify** Freehold and serve it
over a network, section 13 requires you to offer your users the corresponding source: set `SOURCE_URL` to
your repository and the app will show it.

AGPL rather than a permissive licence for one reason. The whole point of this project is that self-hosting
was taken away; a permissive licence would let someone take it closed and hosted, which is the thing it
exists to be an alternative to.

## Documentation

Full documentation is in [docs/](docs/README.md).

| | |
|---|---|
| [Install with Docker](docs/getting-started/install-docker.md) | The supported way to run it |
| [Your first space](docs/getting-started/first-space.md) | Empty install to a running sprint |
| [Running a pilot](docs/getting-started/pilot.md) | Putting it in front of a real team |
| [Migrating from Jira](docs/migrating/from-jira.md) | CSV import, what transfers, what does not |
| [OQL query language](docs/reference/oql.md) | The filter language, in full |
| [REST API](docs/reference/rest-api.md) | |
| [Configuration](docs/admin-guide/configuration.md) | Every environment variable |
| [Feature matrix](docs/product/feature-matrix.md) | Jira parity, real gaps, and what we will not build |
| [What we cannot build yet](docs/product/not-yet.md) | Why each gap is still a gap, and what unblocks it |

## What's in the beta

- **Spaces** with Scrum or Kanban templates and your own workflow: statuses, categories (to do, in progress, done) and WIP limits.
- **Work items**: epics, stories, tasks, bugs and subtasks, with multiple assignees, story points, estimates, start and due dates, labels, checklists, links (blocks, relates to, duplicates), attachments, time logs and full history.
- **Markdown** descriptions and comments with preview, @mentions and links to other work items like WEB-12.
- **Views**: board with swimlanes and drag and drop, backlog with sprint planning, ranking and an overcommit warning, list with bulk edit, timeline and calendar.
- **Reports** built from history: burndown, velocity, cumulative flow, created vs resolved, cycle time and workload.
- **Search** with a JQL-style query language, plus saved and shared filters.
- **People and permissions**: site admins, and viewer, member or admin roles per space.
- **Notifications each person controls**: in-app or email per event, instant or a daily digest, and mute for any single item. Admins cannot turn on noise for you.
- **Import** from Jira CSV and from the Freehold browser prototype; **export** to JSON or CSV at any time.
- **Speed**: the browser loads a space once and filters in memory; changes save optimistically and teammates' edits sync every 15 seconds.
- **Command palette** (Ctrl K or Cmd K), keyboard shortcuts, one-line quick create, duplicate warnings, light and dark themes.
- **REST API** with interactive docs at `/docs`.

![A work item with markdown, links and per-field editing](docs/screenshots/work-item.png)

## Query language

Type in the filter bar on any view. The same language works in the API (`GET /api/search?q=`).

| You want | Type |
|---|---|
| My open work | `assignee = me AND is:open` |
| High priority bugs | `type = Bug AND priority in (Highest, High)` |
| Due in the next week | `due < 7d AND -is:done` |
| Payments work that is stuck | `label:payments AND (is:blocked OR is:overdue)` |
| Nobody owns it | `assignee is empty` |
| Words in the summary or description | `"checkout flow"` |
| Sorted | `sprint = active ORDER BY priority DESC, due` |

**Fields:** `key`, `title` (or `summary`), `description`, `text`, `status`, `category`, `type`, `priority`, `assignee`, `reporter`, `watcher`, `label`, `parent` (or `epic`), `sprint` (a name, `active` or `backlog`), `points`, `estimate`, `logged`, `start`, `due`, `created`, `updated`, `resolved`, `space`.

**Operators:** `=` exact, `!=`, `:` contains, `~` contains, `<` `>` `<=` `>=` for dates and numbers, `in (a, b)`, `not in (a, b)`, `is empty`, `is not empty`, `AND`, `OR`, `NOT`, `-` before a term, parentheses, `ORDER BY field [ASC|DESC]`.

**Shortcuts:** `is:open`, `is:done`, `is:blocked`, `is:overdue`, `is:unassigned`, `is:mine`, `is:watching`, `is:backlog`.

**Values:** `me` or `currentUser()`; dates as `2026-10-01`, `today`, `-7d` (a week ago), `2w` (in two weeks), `startOfWeek()`, `endOfWeek()`, `startOfMonth()`.

## Quick create

Anywhere you can create, one line can set most fields:

```
bug: Fix login timeout @kiran !high #web ~3
```

That creates a Bug assigned to the member whose handle starts with `kiran`, with High priority, the label `web` and 3 story points. Prefixes: `bug:`, `story:`, `task:`, `epic:`, `subtask:`.

## Keyboard

| Key | Does |
|---|---|
| Ctrl K or Cmd K | Command palette: jump to views, spaces or work items, or create |
| C | Create a work item |
| / | Focus the filter bar |
| 1 to 8 | Board, Backlog, List, Timeline, Calendar, Reports, Activity, Settings |
| Ctrl Enter | Save a description or post a comment |
| Esc | Close the open dialog or panel |

## Moving from Jira

1. In Jira, open a filter showing the work you want and export it as CSV with all fields.
2. In Freehold, create the space and add your teammates as members first. People are matched by display name or email.
3. Go to **Settings > Import** and choose **Import Jira CSV**.

What comes across: summary, description (as text), type, status, priority, assignee, reporter, labels, sprints, story points, parent and epic, comments, original estimate, time spent, and created, updated and resolved dates. Statuses Freehold does not know are added to your workflow with a sensible category. If the space key matches the Jira project key, work items keep their numbers; otherwise the old key is shown on each item.

Not yet imported: attachments, custom fields, issue links and workflow rules.

**From the browser prototype:** download its backup JSON, then use **Settings > Import > Import Freehold JSON**.

## API

Every endpoint lives under `/api`. Sign in to get a token:

```bash
TOKEN=$(curl -s localhost:8080/api/auth/login -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"your-password"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

curl -s -G localhost:8080/api/search --data-urlencode 'q=assignee = me AND is:open' \
  -H "Authorization: Bearer $TOKEN"
```

The full, interactive reference is at http://localhost:8080/docs.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | SQLite in the data folder | `postgresql+psycopg://user:pass@host:5432/db` for PostgreSQL |
| `FREEHOLD_DATA` | `./data` (`/data` in Docker) | Attachments, signing key, SQLite file |
| `BASE_URL` | `http://localhost:8080` | Address used in email links |
| `SECRET_KEY` | generated and stored in the data folder | Signs sign-in tokens; changing it signs everyone out |
| `TOKEN_HOURS` | `168` | How long a sign-in lasts |
| `ALLOW_SIGNUP` | `false` | `true` lets anyone who can reach the page create an account |
| `MAX_UPLOAD_MB` | `25` | Attachment size limit |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS` | off | Email notifications. Without a host, emails go to the app log |

## Tests

```bash
cd backend && pytest                                  # API tests on SQLite
DATABASE_URL=postgresql+psycopg://... pytest          # the same tests on PostgreSQL
sh frontend/tests/run.sh                              # clicks through the web app headlessly (Node 18+)
```

GitHub Actions runs all three on every push and pull request.

## Project layout

```
backend/app/
  main.py          app, security headers, static web app
  models.py        data model
  security.py      passwords, tokens, roles
  services.py      validation, history, notifications for changes
  query.py         the query language (mirrored in frontend/js/oql.js)
  notify.py        per-person notification rules, email, digests
  reports.py       burndown, velocity, flow, cycle time
  importer.py      Jira CSV and Freehold JSON
  routers/         HTTP endpoints
frontend/
  index.html, styles.css
  js/api.js        fetch wrapper
  js/md.js         safe markdown
  js/oql.js        query language in the browser
  js/charts.js     SVG charts
  js/app.js        views, dialogs, events
```

## Roadmap

- **Phase 2, depth on demand:** custom fields and forms, workflow rules and approvals, a visual query builder, dashboards.
- **Phase 3, connect and automate:** webhooks, GitHub, GitLab and Bitbucket, Slack and Teams, automation rules, an MCP server for AI agents, SSO, SCIM and an audit log.
- **Phase 4, scale and AI:** cross-space plans and scenarios, bring-your-own-model AI, plugins, mobile, service desk and product discovery.

## Known limits of the beta

- Tables are created on first start; there are no database migrations yet (planned before 1.0). Export before upgrading.
- Teammates' changes arrive by polling every 15 seconds rather than live.
- Digest times are in UTC.
- Attachments are stored on local disk in the data volume.

## License

Maintainer note: add a `LICENSE` file before the first public release. AGPL-3.0 keeps hosted forks open; MIT or Apache-2.0 allow the widest reuse. On GitHub, use Add file > Create new file, name it `LICENSE`, and pick a template.
