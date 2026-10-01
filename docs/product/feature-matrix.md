# Feature matrix

What Jira does, what Freehold does, and what Freehold should do that Jira does not.

Status is honest and checked against the code, not aspirational:

| | Meaning |
|---|---|
| **Built** | Works today in 0.1.0-beta |
| **Partial** | Works for the common case, with a named gap |
| **Planned** | Agreed, not written |
| **Deliberate no** | We are choosing not to build this, with a reason |

## Where this stands

| Area | State |
|---|---|
| Work items, boards, backlog, sprints, search, reports, notifications | Broadly at parity |
| Permissions | Deliberately simpler than Jira, and sufficient |
| Migration | Imports Jira CSV, with named gaps (attachments, links, custom fields) |
| **Custom fields** | **Not built. The most-cited parity gap** |
| Versions and releases | Built |
| **Automation** | **Not built. The largest single functional block Jira has and we do not** |
| **Development tooling** (branches, PRs, builds) | **Not built. Why engineers tolerate Jira** |
| **Dashboards** | **Not built** |
| **SSO and password reset** | **Not built. Blocks company adoption.** Rate limiting is now built |
| Schema migrations | Built. Upgrades are safe now |
| Service management (portal, SLAs) | Out of scope. Freehold is a tracker, not a service desk |

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
| Versions / fix version / releases | Yes | **Built** | Named releases with dates, fix version on work, release gated on unfinished work, archive, safe delete |
| Environment field | Yes | **Deliberate no** | A label or custom field does this |
| Custom fields | Yes | **Planned** | Biggest single parity gap |

### Hierarchy

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Epic → Story → Subtask | Yes | **Built** | |
| Arbitrary nesting depth | **No** | **Built** | A subtask of a subtask works, to any depth, cycles rejected. [JRA-4446](https://jira.atlassian.com/browse/JRA-4446) has 1,000+ votes and is still open in Jira |
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
| Login rate limiting | Yes | **Built** | Per address and per address+email. In-memory, so still put a limiter at the proxy |
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
| Schema migrations | Yes | **Built** | Alembic at startup. Databases predating migrations are adopted automatically |
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

### Reports

Jira ships a long report catalogue. Most teams use four of them, but the rest is what people hunt for
after a migration.

| Report | Jira | Freehold | Notes |
|---|---|---|---|
| **Rebuilt from audit history** | No | **Built** | Jira reports read current state, so historical charts shift after an edit. Ours replay History and stay honest |
| Sprint burndown | Yes | **Built** | |
| Velocity | Yes | **Built** | |
| Cumulative flow | Yes | **Built** | |
| Created vs resolved | Yes | **Built** | |
| Cycle time / control chart | Yes | **Built** | |
| Open points by assignee | Yes | **Built** | |
| Sprint report (committed vs added mid-sprint) | Yes | **Planned** | Scope-creep visibility; we record the data already |
| Epic report / epic burndown | Yes | **Planned** | |
| Release burndown | Yes | **Planned** | Needs versions first |
| Average age of open items | Yes | **Planned** | |
| Recently created | Yes | **Planned** | |
| Resolution time | Yes | **Partial** | Cycle time covers most of it |
| Time tracking report / timesheets | Yes | **Planned** | Worklogs are captured; there is no report over them |
| User workload | Yes | **Partial** | Open points by assignee |
| Pie chart by any field | Yes | **Planned** | |
| Custom report builder | Add-on (eazyBI) | **Planned** | Jira needs a paid add-on for this, which is a gap worth beating |
| Cross-space reporting | Premium | **Planned** | |

### Dashboards

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Personal dashboard | Yes | **Not built** | You land in a space, not on an overview |
| Shared/team dashboards | Yes | **Not built** | |
| Gadgets (filter results, charts, counts) | Yes | **Not built** | |
| Cross-space rollup | Premium | **Not built** | |
| "What changed since I was away" | No | **Planned** | Nobody does this well; see Part 2 |

### Automation

Jira Automation is a large product in its own right, and one of the most-cited reasons teams stay.

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Rule triggers (created, transitioned, field changed, commented) | Yes | **Not built** | |
| Conditions and branching | Yes | **Not built** | |
| Actions (assign, transition, comment, notify, create linked item) | Yes | **Not built** | |
| Scheduled rules | Yes | **Not built** | |
| Cross-project rules | Yes | **Not built** | |
| Rule audit log | Yes | **Not built** | |
| Usage limits by plan | Yes | **Deliberate no** | Automation is metered in Jira Cloud. Self-hosted has no reason to meter it |

Nothing here exists today. It is the single largest functional block Jira has and Freehold does not.

### Development tooling

Jira's dev panel is why engineers tolerate Jira. This is a complete gap.

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Linked branches, commits, PRs on the item | Yes | **Not built** | |
| Smart commits (`WEB-12 #close #time 2h`) | Yes | **Planned** | Cheap to add, high daily value |
| Build and deployment status | Yes | **Not built** | |
| Create a branch from an item | Yes | **Not built** | |
| Git host integration (GitHub, GitLab, Bitbucket) | Yes | **Planned** | |
| Webhooks out | Yes | **Planned** | The integration floor; nothing else can be built on top until this exists |
| Incoming webhooks / REST-driven automation | Yes | **Partial** | The full REST API is there; no event push |

### Releases and versions

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Versions per project | Yes | **Built** | Name, description, release date, unique per space |
| Fix version on work | Yes | **Built** | Recorded in history by name, so the trail survives a rename |
| Release gating | Partial | **Built** | A version refuses to be released while work in it is unfinished. Jira only warns |
| Archive a version | Yes | **Built** | Archived versions stop accepting new work |
| Safe delete | Yes | **Built** | Deleting a version never deletes the work in it |
| Release hub view | Yes | **Partial** | The API is complete; there is no dedicated release screen yet |
| Generated release notes | Yes | **Planned** | The data is all there now |
| Affects version | Yes | **Planned** | |

### Planning and roadmaps

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Timeline / Gantt within a space | Yes | **Built** | Bars by start and due date, grouped by epic |
| Cross-project roadmap | Advanced Roadmaps (Premium) | **Not built** | |
| Dependency lines between items | Advanced Roadmaps | **Partial** | Links exist and show on the item; the timeline does not draw them |
| Capacity planning by team | Advanced Roadmaps | **Not built** | |
| Scenario planning ("what if we slip this") | Advanced Roadmaps | **Not built** | |
| Baselines | Advanced Roadmaps | **Not built** | |

Jira gates all of this behind Premium. That makes it a fair target rather than a parity obligation.

### Editor and content

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Rich text editing | WYSIWYG | **Built** (markdown) | Markdown with live preview. A deliberate difference, not a gap |
| Tables in descriptions | Yes | **Built** | With column alignment, escape-first like the rest of the renderer |
| Inline images | Yes | **Built** | |
| Mentions | Yes | **Built** | |
| Item templates | Add-on | **Planned** | |
| Space documents / wiki | Confluence (separate product) | **Planned** | See Part 2, tool sprawl |
| Draft recovery | Patchy in Jira | **Planned** | Losing a long comment is a common Jira complaint |

### Service management

Jira Service Management is a separate paid product. Listed so the boundary is explicit rather than an
accidental gap.

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Customer portal | JSM | **Not built** | |
| Request types and forms | JSM | **Not built** | |
| SLAs and breach reporting | JSM | **Not built** | |
| Queues | JSM | **Partial** | A saved filter plus the list view does most of it |
| Knowledge base | JSM + Confluence | **Not built** | |
| Asset / config management | JSM Premium | **Deliberate no** | A different product |
| Approvals | JSM | **Planned** | Wanted for change management |

**Freehold is a work tracker, not a service desk.** Teams needing a customer-facing portal should know
that now rather than discover it mid-migration.

### Platform

The quiet things people only notice when missing.

| Capability | Jira | Freehold | Notes |
|---|---|---|---|
| Keyboard shortcuts | Yes | **Built** | |
| Command palette | Yes | **Built** | `Ctrl`/`Cmd` + `K` |
| Dark mode | Yes | **Built** | Follows the OS by default |
| Offline / air-gapped operation | No | **Built** | No CDN, no build step, no outbound calls |
| Personal access tokens for scripts | Yes | **Planned** | Session tokens only today; a script has to log in as a user |
| Email-to-item (create and comment by email) | Yes | **Not built** | |
| Filter subscriptions (emailed on a schedule) | Yes | **Not built** | Digests exist, but not over a saved filter |
| Bulk change driven by a query | Yes | **Partial** | Bulk edit works from the list selection, not from a query |
| Archive items and spaces | Yes | **Not built** | |
| Localisation | ~25 languages | **Not built** | English only. Blocks non-English teams outright |
| Accessibility | Partial, audited | **Partial** | Keyboard reachable, labelled, focus rings, contrast verified. No screen-reader audit |
| Anonymous / public read-only spaces | Yes | **Not built** | |
| Global audit log | Yes | **Partial** | Per-item history exists; no instance-wide view |

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

### 9. Sub-tasks cannot have sub-tasks

[JRA-4446](https://jira.atlassian.com/browse/JRA-4446) asks for sub-issues to contain their own
sub-issues. It has over a thousand votes and has been open for years. Real work nests deeper than three
levels and teams fake it with links and naming conventions.

**Freehold:** Epic → Story → Subtask today, same as Jira. **Planned:** arbitrary depth, because the
constraint is a database decision, not a methodology.

### 10. Reporting beyond the basics needs a paid add-on

Jira's built-in reports stop at a fixed list. Anything bespoke means eazyBI or a similar Marketplace
product, billed per user on top of Jira itself.

**Freehold:** reports are computed server-side from history and exposed on the REST API, so any team that
can write a query already has its data. **Planned:** a report builder in the product, not sold separately.

### 11. Nobody can answer "what changed while I was away"

Come back from a week off and Jira offers you an inbox of individual notifications and an activity stream.
Neither answers the actual question: what moved, what is now blocked, what needs me.

**Planned:** a catch-up view scoped to a date range and to work you are involved in: status changes,
new blockers, items that became overdue, and comments that mention you, collapsed into one screen.
Nothing in Jira does this, and it is the first thing anyone does on a Monday.

### 12. Long comments get lost

Losing a half-written comment or description to a navigation, a session timeout or a failed save is a
recurring complaint.

**Planned:** local draft capture on every editor, restored on return. Cheap to build, disproportionately
appreciated, and the self-hosted case makes it safe because the draft never leaves the browser.

### 13. Nothing notices stale work

Items rot. A ticket sitting in "In progress" for six weeks looks identical to one opened yesterday, and
Jira will not tell you unless somebody builds a filter and remembers to look at it.

**Planned:** stale detection surfaced on the board and in reports, driven by time in status rather than
by age, which is the number that actually matters.

### 14. Duplicates are found by accident

Jira will happily take the same bug five times.

**Freehold:** the create dialog already warns on likely duplicates while you type the summary.
**Planned:** extend it to description text and to recently closed items, which is where duplicates
actually hide.

### 15. Per-seat cost decides the tool, not merit

Once past the free tier, Jira's per-user pricing compounds, and teams report it as a direct reason to
leave. The cost also distorts behaviour: read-only stakeholders get excluded to save money, so the tool
stops being the single source of truth.

**Freehold:** no per-seat cost at all. Add every stakeholder as a viewer, because viewers cost nothing
and a tracker that excludes people is not a system of record.

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

| # | Item | Why here |
|---|---|---|
| 1 | **Alembic migrations** | Nothing else can ship safely until upgrades are safe. Everything below is blocked by this |
| 2 | **SSO/OIDC, login rate limiting, password reset** | Blocks company adoption outright, and the missing rate limit is a live security gap |
| 3 | **Custom fields** | The most-cited parity gap. Many teams cannot migrate without it |
| 4 | **Webhooks** | The integration floor. Automation and dev tooling both sit on top of it |
| 5 | **Importer: attachments, links, custom fields** | Every missing piece is a reason not to migrate, and migration is the whole acquisition path |
| 6 | **Versions and releases** | Blocks anyone shipping versioned software |
| 7 | **Development tooling** (smart commits, branch and PR links) | Why engineers tolerate Jira. Smart commits alone are cheap and earn daily use |
| 8 | **Automation rules** | The largest functional block we lack. Deliberately smaller than Jira's |
| 9 | **Visual query builder** | Turns OQL from a barrier into a reason to stay, and reaches the non-engineers Jira loses |
| 10 | **Dashboards and the catch-up view** | The first screen people want, and nobody does catch-up well |
| 11 | **Paging the space bundle** | The known ceiling on the thing that makes Freehold feel fast |
| 12 | **Permission preview, notification "why", stale detection** | The differentiators. Worth nothing until the table stakes above are done |

Items 1 and 2 are not features. They are the difference between a project people try and a project people
deploy.
