# Running a pilot

Freehold is at the point where the useful next step is one real team running one real sprint on it.
Everything in it passes tests and has been clicked through, but no team has yet done a week's work in
it, and that is a different kind of evidence.

This page is for the person running that pilot.

## Pick the right team

| Good pilot | Bad pilot |
|---|---|
| 3 to 8 people | A whole department |
| One project, one board | Cross-project dependencies |
| A sprint that is not on fire | Anything with a hard external deadline |
| Someone who will say what annoyed them | Volunteers who are too polite to complain |

**Run it alongside Jira for the first sprint, not instead of it.** Double entry for two weeks is
cheap. Discovering a gap halfway through a sprint you cannot abandon is not.

## Before day one

```bash
docker compose up -d --build
python scripts/validate.py  http://your-host:8080                 # does the product work
python scripts/preflight.py http://your-host:8080 --compose freehold   # is this deployment safe
```

The two ask different questions. `validate.py` runs a whole lifecycle against a **fresh, empty**
instance and tells you the product works. `preflight.py` runs against the instance you intend to
use and tells you whether it is fit for other people: default passwords, mail that silently goes
nowhere, notification links pointing at localhost, no working backup. The second is the one that
sinks pilots.

`validate.py` runs a whole lifecycle against a **fresh, empty** instance: setup, Jira import, custom
fields, planning, permissions, working a sprint, filtering, completing, reporting, releasing, and
exporting. Fifty assertions. If it does not come back clean, stop and fix that first.

Then set, at minimum:

| | |
|---|---|
| `POSTGRES_PASSWORD` | the default is published in this repository |
| `SECRET_KEY` | so sessions survive a restart |
| `BASE_URL` | the address people actually type, or notification links point nowhere |
| `SMTP_HOST` | or email goes to the log and people will say "I never got told" |

And take a backup before you start, so you can compare later: see
[backup and restore](../admin-guide/backup-and-restore.md).

## Putting it on a hostname that lasts

A Cloudflare *quick* tunnel (`cloudflared tunnel --url http://localhost:8080`) is the fastest way to
show somebody, and the wrong way to run a pilot: it gets a random hostname that changes every time it
restarts, so bookmarks break and links already sent by email point nowhere.

A **named** tunnel keeps one hostname across restarts and reboots. It is free, and needs a domain in
Cloudflare.

```bash
cloudflared tunnel login                              # once, in a browser; pick your domain
sh scripts/named-tunnel.sh tracker.yourdomain.com     # everything else
```

That creates the tunnel, points DNS at it, writes the config, installs it as a service so it survives
a reboot, sets `BASE_URL`, and recreates the app so notification links are right.

No domain? Two honest options: register one (about $10 a year, and you will want one anyway), or put
Freehold on a small VPS and skip tunnelling altogether. Tailscale also gives a stable hostname without
a domain, but every person in the pilot has to join your tailnet first, which is friction a pilot does
not need.

## Day one

1. **Import the real project**, not a toy one. [Migrating from Jira](../migrating/from-jira.md).
   Attachments, links and custom fields do not come across yet, so note what the team loses.
2. **Check the workflow categories.** Settings → Workflow. Names can be anything; the *category* on
   each status drives every report. This is the single most common way to get plausible-but-wrong
   charts.
3. **Add everyone, with real roles.** Stakeholders as viewers — viewers cost nothing, so there is no
   reason to leave anyone out.
4. **Walk through it together for twenty minutes.** Create, assign, move, comment, complete. Watch
   where people hesitate; hesitation is the data.

## What to watch for

The things most likely to bite, in roughly that order:

| Watch | Why |
|---|---|
| **Anything that needs a custom field you cannot build** | Eight types exist. If the team needs something else, that is a real gap |
| **People falling back to a spreadsheet** | The single strongest signal that something is missing. Find out what |
| **Reports that look wrong** | Usually a status in the wrong category. Occasionally a real bug, and we want to know which |
| **"Why did I get this email?"** | Notification preferences are per person, under Profile. If people cannot find that, the UI is at fault |
| **Searches people give up on** | OQL has no visual builder yet, so watch for anyone who stops trying to filter |
| **Anything slow** | One space loads in a single request. That is why it feels instant, and it has a ceiling we have not paged yet. A very large import is where you would meet it |

## What it cannot do yet

Say this to the team up front. Discovering it mid-sprint is what sours a pilot.

- **No SSO.** Accounts are created by a site admin with a temporary password.
- **No password reset by email.** An admin resets it.
- **No Jira attachments, links or custom fields on import.** Export anything you need from Jira
  separately, and do it before the instance is switched off.
- **No automation rules, no dashboards, no git integration.**
- **No mobile app.** The web app works on a phone; it is not a native app.
- **English only.**

The full picture is in the [feature matrix](../product/feature-matrix.md) and
[what we cannot build yet](../product/not-yet.md).

## Collecting what you learn

Use Freehold for it. Make a space called `PILOT`, and have the team file what they hit there: it is
the fastest way to find out whether the tool is pleasant to use, because they will be using it to
complain about itself.

Ask for three things at the end of the sprint:

1. **What did you have to work around?**
2. **What did you go back to Jira or a spreadsheet for?**
3. **What would stop you using this for the next sprint?**

The third question is the one that matters. Everything else is a feature request.

## Deciding

After one sprint you should be able to answer: did the team do their work in it, or did they maintain
it alongside their real tool? If it was the second, the gap they named is the roadmap, and it is worth
more than anything on the current priority list.
