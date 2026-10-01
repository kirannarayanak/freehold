# Feature matrix

What Jira does, what Freehold does, and what Freehold should do that Jira does not.

Status is honest and checked against the code, not aspirational:

| | Meaning |
|---|---|
| **Built** | Works today in 0.1.0-beta |
| **Partial** | Works for the common case, with a named gap |
| **Planned** | Agreed, not written |
| **Deliberate no** | We are choosing not to build this, with a reason |

---

## Part 1: Jira parity

### Work items

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Types (Epic, Story, Task, Bug, Subtask) | Yes | **Built** | Fixed set |
| Custom issue types per project | Yes | **Planned** | |
| Summary, description, markdown | Yes | **Built** | Escape-first renderer, no HTML injection |
| Priority | Yes | **Built** | Highest to Lowest |
| Multiple assignees | No (one) | **Built** | Jira allows exactly one; real work often has two |
| Reporter | Yes | **Built** | |
| Watchers | Yes | **Built** | |
| Labels | Yes | **Built** | |
| Story points | Yes | **Built** | |
| Original estimate / time logged | Yes | **Built** | Worklogs with per-entry notes |
| Start and due dates | Yes | **Built** | |
| Checklists | Add-on only | **Built** | Jira needs a paid Marketplace app for this |
| Attachments | Yes | **Built** | Token-auth downloads |
| Comments with @mentions | Yes | **Built** | |
| Issue links (blocks, relates, duplicates) | Yes | **Built** | Inverse labels computed, one row per link |
| Clone | Yes | **Built** | |
| Voting | Yes | **Deliberate no** | Vote counts drive politics, not prioritisation |
| Resolution separate from status | Yes | **Planned** | Jira's status/resolution split confuses everyone; needs a better design |
| Components | Yes | **Planned** | Labels cover most of it today |
| Versions / fix version / releases | Yes | **Planned** | Real gap for anyone shipping versioned software |
| Environment field | Yes | **Deliberate no** | A label or custom field does this |
| Custom fields | Yes | **Planned** | Biggest single parity gap |

### Hierarchy

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Epic → Story → Subtask | Yes | **Built** | |
| Arbitrary nesting depth | No | **Planned** | [JRA-4446](https://jira.atlassian.com/browse/JRA-4446) has 1,000+ votes and is still open |
| Cross-project parents | Advanced Roadmaps only | **Planned** | |

### Workflow

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Custom statuses | Yes | **Built** | Per space, reorderable |
| Status categories (to do / doing / done) | Yes | **Built** | Drives every report |
| WIP limits | Board only | **Built** | Per status |
| Transition rules (who, when, from where) | Yes | **Planned** | |
| Conditions, validators, post-functions | Yes | **Planned** | Jira's version of this is the main admin tax; ours must stay small |
| Approvals | JSM | **Planned** | |
| Workflow per issue type | Yes | **Deliberate no** | A top source of Jira configuration sprawl |

### Boards, backlog, sprints

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Kanban board, drag and drop | Yes | **Built** | |
| Scrum board | Yes | **Built** | |
| Swimlanes / group by | Yes | **Built** | |
| Backlog with drag to sprint | Yes | **Built** | |
| Sprints (future, active, closed) | Yes | **Built** | Goal, dates, committed vs completed |
| Epics panel | Yes | **Built** | |
| Board per filter / multiple boards per project | Yes | **Partial** | One board per space; saved filters narrow it |
| Parallel sprints | Yes | **Planned** | |
| Card colours and card layout config | Yes | **Planned** | |

### Search

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Query language | JQL | **Built** | OQL. Same idea, smaller surface, same grammar in browser and server |
| Saved filters, shared filters | Yes | **Built** | |
| Visual query builder | Yes | **Planned** | Jira has one; ours should teach OQL as you click |
| Full-text search | Yes | **Built** | |
| Regex / subqueries | No | **Planned** | A named JQL limitation we can beat |
| Search across all spaces | Yes | **Partial** | Command palette searches; no cross-space result page |

### Reports

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Burndown | Yes | **Built** | |
| Velocity | Yes | **Built** | |
| Cumulative flow | Yes | **Built** | |
| Created vs resolved | Yes | **Built** | |
| Cycle time / control chart | Yes | **Built** | |
| Open points by assignee | Yes | **Built** | |
| Rebuilt from audit history | No | **Built** | Jira reports read current state; ours replay History, so they stay honest after edits |
| Dashboards and gadgets | Yes | **Planned** | |
| Cross-project reporting | Premium | **Planned** | |

### Users, permissions, security

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Accounts, site admin | Yes | **Built** | |
| Project roles | Yes | **Built** | viewer / member / admin |
| Permission schemes | Yes | **Deliberate no** | Three roles and one check beat a scheme matrix nobody can audit |
| Issue-level security | Yes | **Planned** | |
| SSO / SAML / OIDC | Paid tiers | **Planned** | Table stakes for company adoption |
| LDAP / Active Directory | Data Center | **Planned** | |
| Two-factor auth | Yes | **Planned** | |
| Login rate limiting | Yes | **Planned** | Security gap today |
| Password reset by email | Yes | **Planned** | Admin-set passwords only today |
| Global audit log | Yes | **Partial** | Per-item history exists; no instance-wide view |

### Notifications

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| In-app notifications | Yes | **Built** | |
| Email notifications | Yes | **Built** | SMTP, or written to log if unset |
| Per-user preferences | Limited | **Built** | Jira's are per-project schemes set by admins; ours are per person |
| Digest instead of instant | No | **Built** | |
| Mute a single item | Yes | **Built** | |
| Per-user time zones | Yes | **Planned** | Digests are UTC today |

### Administration

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| One-command install | No | **Built** | `docker compose up -d` |
| Self-hosted | **Ending** | **Built** | New Data Center sales closed 30 Mar 2026 |
| Schema migrations | Yes | **Planned** | `create_all` today; needs Alembic before 1.0 |
| Backup and restore | Yes | **Partial** | JSON export per space; no instance-wide backup command |
| Archiving projects | Yes | **Planned** | |
| Instance-wide settings UI | Yes | **Partial** | Environment variables |

### Integration

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| REST API | Yes | **Built** | Whole app is API-first; OpenAPI at `/docs` |
| Webhooks | Yes | **Planned** | |
| Automation rules | Yes | **Planned** | |
| Git / CI integration | Yes | **Planned** | Smart commits, branch and PR linking |
| Chat integration | Yes | **Planned** | |
| Marketplace / plugins | Yes | **Deliberate no** | Plugin APIs are why Jira cannot be made fast |
| Mobile app | Yes | **Deliberate no** | Responsive web works offline-capable and on every device |

### Migration

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Jira CSV import | n/a | **Built** | Duplicate columns, backdated history, comments, sprints, time |
| Jira attachments, links, custom fields | n/a | **Planned** | Named gap in the importer |
| Full JSON export | Partial | **Built** | Everything, no lock-in. See [migrating from Jira](../migrating/from-jira.md) |

---

## Part 2: Beyond Jira

Problems Jira users report that Jira has not solved. This is where the product earns a switch rather than merely matching.

### 1. Self-hosting is being taken away

Atlassian closed new Data Center sales on **30 March 2026**. Existing customers can renew until **30 March 2028** and go **read-only on 28 March 2029**.

A team that wants its tracker on its own infrastructure today cannot buy Jira for it at any price. That is the whole reason this product exists, and the deadline is a countdown, not a hypothetical.

**Freehold:** self-hosted is the only mode. No telemetry, no licence server, runs air-gapped.

### 2. The admin tax

Configuring Jira workflows is, in one engineering leader's words, "almost a full-time job." Permission schemes multiply until, as one admin guide puts it, the combinatorial space is effectively unauditable, and too many schemes become a measurable performance problem.

**Freehold:** three roles, one permission check (`get_space`) for the entire codebase, and a workflow editor that is one screen. **Planned:** a permission preview that answers "what can this person actually see?" — a question Jira cannot answer without reading several schemes side by side.

### 3. Nobody knows why they got that email

Each Jira project carries its own notification scheme mapping dozens of events to dozens of recipients; within a year no two projects notify the same way, so no engineer can reason about what Jira will send them.

**Freehold:** notification preferences belong to the person, not the project, so they are the same everywhere. **Planned:** a "why am I getting this?" line on every notification naming the rule that produced it, and a weekly notification budget.

### 4. JQL is a wall for non-engineers

JQL is powerful and widely described as unintuitive; it has no regex and no subqueries, and non-technical users avoid it. Product managers and designers end up tracking work in spreadsheets instead.

**Freehold:** OQL has the same grammar in the browser and on the server, so errors surface as you type instead of after a round trip. **Planned:** a visual builder that writes OQL into the box as you click, so the query language is learned by use rather than studied; plus regex and saved-filter composition.

### 5. It gets slow exactly when it matters

Jira is widely reported to slow down with large datasets and many boards.

**Freehold:** one bundle request per space, then filtering in memory, which is why the UI is instant. **This has a ceiling** and we know it: very large spaces need paging, which is unbuilt. Honest limit, named here rather than discovered by a user.

### 6. Reports quietly lie after an edit

Jira reports read current state. Move an item between sprints or rewrite its status and historical charts shift under you.

**Freehold:** every report replays the History table, so a chart of last quarter stays the chart of last quarter. Already built, and a genuine differentiator worth saying out loud.

### 7. Tool sprawl

Teams need Jira *plus* Confluence *plus* a docs tool *plus* chat integrations, and pay for each.

**Freehold:** markdown with attachments is in the work item. **Planned:** space-level documents, so decisions live next to the work instead of in a second product.

### 8. Exit cost

Lock-in is the quiet reason teams stay.

**Freehold:** complete JSON export of everything, documented format, re-importable. The exit is a supported feature, not an obstacle.

---

## Part 3: What we will not build

Scope discipline is a feature. Every item here is a thing Jira has that made Jira worse.

- **A plugin marketplace.** Third-party code in the request path is why Jira cannot be made fast.
- **Permission schemes.** Three roles that fit in your head beat a matrix that does not.
- **Workflow per issue type.** The single largest source of configuration sprawl.
- **A native mobile app.** The responsive web app already works on a phone.
- **Voting.** It measures who is loudest.

---

## Priority order

Judged by what blocks adoption, not by what is interesting to build.

1. **Alembic migrations** — nothing else can ship safely until upgrades are safe
2. **SSO/OIDC + login rate limiting + password reset** — blocks company adoption outright
3. **Custom fields** — the most-cited parity gap
4. **Versions and releases** — blocks anyone shipping versioned software
5. **Importer: attachments, links, custom fields** — every missing piece is a reason not to migrate
6. **Visual query builder** — turns OQL from a barrier into the reason to stay
7. **Webhooks and automation** — the integration floor
8. **Permission preview and notification "why"** — the differentiators, once the table stakes are done
