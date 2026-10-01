# What we cannot build yet, and why

A companion to the [feature matrix](feature-matrix.md). The matrix says *what* is missing. This says
*why it is still missing*, what would unblock it, and roughly what it costs.

Nothing here is on the list because it is hard. Everything is on the list for a specific reason, and
every reason has a way out.

---

## Shipped in this pass

For contrast, these were blocked an hour ago and are not any more.

| | Why it was blocked | How it got unblocked |
|---|---|---|
| **Schema migrations** | Nothing. It was simply unbuilt, and it blocked everything else | Alembic at startup; databases predating it are adopted at the baseline |
| **Versions and releases** | Needed a new column on an existing table, which `create_all` can never add | Migrations landed first |
| **Login rate limiting** | Nothing | Built; a live security gap closed |
| **Markdown tables** | Nothing | Built, escape-first, with alignment |
| **Arbitrary nesting depth** | Nothing — it already worked | A test so nobody removes it |

The migration point is the general lesson: **the order matters more than the effort.** Versions is a
small feature that was impossible to ship safely until a piece of invisible plumbing existed.

---

## Group A: blocked on something I cannot stand up or verify

These are not hard. They are untestable from here, and shipping authentication or data-import code that
has never run against the real thing is how people lose accounts and data.

### Single sign-on (SAML / OIDC)

**Why not now.** An SSO integration is only as good as the provider it was tested against. Entra ID,
Okta, Google Workspace and Keycloak all differ in claim names, signature handling and logout behaviour.
Writing it blind produces code that passes its own unit tests and fails on your actual IdP, and the
failure mode is "nobody can sign in".

**What unblocks it.** Tell me which provider you care about and give me a test tenant, or accept
Keycloak in Docker as the reference implementation and treat the rest as unverified.

**Cost.** Two to three days with a provider to test against. **Priority: highest of everything below.**
This is the single thing most likely to stop a company adopting Freehold.

### LDAP and Active Directory

**Why not now.** Same reason, more so: AD deployments differ in schema, group nesting and referral
behaviour. There is no honest way to test this without a directory.

**What unblocks it.** A test directory, or a decision to support OIDC only and let an identity broker
handle LDAP. **I would recommend the second**: it is less code and one less thing to get wrong.

### Password reset by email

**Why not now.** This one is half-blocked and worth being precise about. The token flow is
straightforward and I could write it today. What I cannot do is verify that the mail actually arrives,
and a reset flow that silently fails to deliver is worse than no reset flow, because people lock
themselves out believing a mail is coming.

**What unblocks it.** SMTP credentials on a real instance, even a throwaway account.

**Cost.** Half a day, then testing against your mail server.

### Email-to-item

**Why not now.** Needs an inbound mail path — an IMAP mailbox to poll or an address routed into the app.
Neither exists here.

**What unblocks it.** A mailbox. IMAP polling is the pragmatic choice and works without changing your
mail infrastructure.

**Cost.** Two days.

### Git host integration (branches, commits, PRs, builds)

**Why not now.** Needs OAuth credentials for GitHub or GitLab and a publicly reachable callback URL.
Localhost cannot receive a webhook from github.com.

**Partial exception worth noting.** *Smart commits* — parsing `FH-12 #done #time 2h` out of commit
messages — needs none of that on our side. It needs the webhook receiver, which is unblocked and is
the next thing I would build.

**What unblocks it.** An OAuth app on your Git host and a reachable URL, or a tunnel for development.

**Cost.** Three to four days for the full dev panel. The smart-commit receiver alone is a day.

### Jira attachment import

**Why not now.** This one is a genuine hard blocker, not a convenience. **A Jira CSV export does not
contain attachment files.** It contains URLs pointing back into the Jira instance, which require
authentication to fetch. No amount of work on the importer changes that.

**What unblocks it.** Jira API credentials and a reachable Jira instance, so the importer can fetch each
file while the instance is still alive. Note the deadline: this stops being possible when an instance
goes read-only or is decommissioned.

**Cost.** A day, once credentials exist. **Worth doing before anyone's Jira is switched off**, because
afterwards the files are simply gone.

---

## Group B: unblocked, just not built yet

Nothing external is needed. These are a question of time, and they are listed in the order I would do
them.

| | Cost | Why this order |
|---|---|---|
| **Webhooks out** | 1–2 days | The integration floor. Automation, git integration and chat all sit on it, so it unblocks the most |
| **Personal access tokens** | 1 day | Scripts currently have to log in as a human with a password. Small, and it makes the API genuinely usable |
| **Custom fields** | 1–2 weeks | The most-cited parity gap. Large because it touches the model, the API, OQL, both parsers, the UI and the importer |
| **Stale-work detection** | 2 days | Beyond Jira, and cheap: time-in-status is already derivable from the history table, which we never delete |
| **Catch-up view** | 3 days | "What changed while I was away." Nothing does this well. The data exists today |
| **Draft recovery** | 1 day | Pure frontend, `localStorage`. Disproportionately appreciated |
| **Automation rules** | 2–3 weeks | The largest block Jira has that we do not. Needs webhooks first, and needs to stay deliberately smaller than Jira's |
| **Dashboards** | 1–2 weeks | Wanted, but a tracker that opens on a board rather than a dashboard is a defensible choice |
| **Release notes generation** | 1 day | All the data landed with versions this pass |
| **Paging the space bundle** | 3 days | The known ceiling on what makes Freehold feel fast. Not urgent until someone has a very large space, but it is a cliff rather than a slope |
| **Per-user time zones** | 2 days | Digests are UTC. Real annoyance outside UTC, which includes you |
| **Localisation** | 1 week + translators | The code work is a week. Finding translators is the actual blocker |

---

## Group C: needs a decision from you, not from me

I should not pick these unilaterally.

### Service management (customer portal, SLAs, queues)

A customer-facing service desk is a **different product** sharing a database. It roughly doubles the
surface area and changes who the user is.

**The question:** is Freehold a work tracker for internal teams, or a Jira *and* Jira Service Management
replacement? I would say tracker, and say so plainly in the docs, because a focused tool that admits its
boundary beats a vague one. But it is a market decision, not a technical one.

### A licence

There is still no LICENSE file. Without one, the default is **all rights reserved** — nobody can legally
use, fork or contribute to this, which rather undercuts "free and open source".

The real choice is between **AGPL-3.0** (a competitor cannot run it as a closed SaaS; some companies ban
AGPL internally) and **Apache-2.0** (maximum adoption, and someone can take it commercial). Given the
market opening is self-hosting, I lean AGPL. **This is yours to decide and it is blocking: an
open-source project without a licence is not open source.**

### Accessibility

Currently partial: keyboard reachable, labelled, focus rings, and contrast verified at every pair this
session. What does not exist is a screen-reader audit, which needs either a specialist or real time with
NVDA and VoiceOver.

**The question:** is this a compliance requirement for your target customers (public sector and large
enterprises often say yes)? If so it moves up the list sharply.

---

## Group D: deliberately not building

Reasons in the [feature matrix](feature-matrix.md). Briefly: **a plugin marketplace** (third-party code
in the request path is why Jira cannot be made fast), **permission schemes**, **workflow per issue
type**, **a native mobile app**, and **voting**.

These are not gaps. Each one is a thing Jira has that made Jira worse, and the discipline not to build
them is part of the product.

---

## The honest summary

Freehold is at parity with Jira for the work a team does day to day: items, boards, backlog, sprints,
search, reports, notifications, and now releases. It is **ahead** on nesting depth, on reports that stay
honest after an edit, on notification preferences belonging to the person, on export without lock-in,
and on being self-hostable at all.

It is **behind** on three things that decide adoptions, and no amount of being ahead elsewhere
compensates:

1. **SSO** — blocked on a provider to test against
2. **Custom fields** — unblocked, large
3. **Automation and git integration** — needs webhooks first, which is a day or two

The fastest route to "a team could actually switch to this" runs through webhooks, then custom fields,
then SSO as soon as there is an identity provider to point at.
