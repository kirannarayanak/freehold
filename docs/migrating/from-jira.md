# Migrating from Jira

Freehold imports a Jira CSV export directly. One project at a time, into a space you create first.

## Why people are doing this now

Atlassian is ending self-managed Jira:

| Date | What happens |
|---|---|
| **30 March 2026** | New customers can no longer buy Data Center subscriptions. **This has passed.** |
| **30 March 2028** | Existing customers can no longer buy expansions or new subscriptions |
| **28 March 2029** | Data Center subscriptions expire and products become **read-only** |

If you are already on Data Center you have time, but it is a countdown with a fixed end. If you are not,
self-hosted Jira is no longer purchasable at any price.

## Export from Jira

In Jira, open your project's issue list, then **Export → Export Excel CSV (all fields)**.

Use *all fields*, not current fields. The all-fields export is what carries comments, sprints, story
points and worklogs, and it repeats columns like `Labels` and `Comment` once per value, which the
importer expects.

## Import into Freehold

1. Create a space with the key you want. Use the **same key as the Jira project** (`WEB` for `WEB-123`)
   and the original keys are preserved, so every existing link and bookmark still reads correctly.
2. Add your team as members first, under space **Settings → Members**. The importer matches people by
   display name; anyone it cannot match leaves their work unassigned and is listed in the warnings.
3. Go to **Settings → Import**, choose the CSV, and import.

The result reports how many items and sprints were created, and warns about anything it could not match.

## What transfers

| | Notes |
|---|---|
| Keys | `WEB-123` stays `WEB-123` if the space key matches |
| Summary, description, type, priority, status | Statuses are created in your workflow if missing, and mapped to a category |
| Assignee, reporter | Matched by display name against existing members |
| Labels | Multiple `Labels` columns are merged |
| Story points | From any of Jira's several story point field names |
| Original estimate, time spent | Converted from seconds to hours |
| Comments | Author and date preserved from Jira's `date;account;text` format |
| Sprints | Created and linked. Closed unless the work is unfinished |
| Parent / epic link | Rebuilt as hierarchy |
| Created, updated, resolved dates | **Backdated**, so reports reflect when work really happened |

That last row matters more than it looks. Freehold rebuilds every report from history, so a correctly
backdated import means your burndown and cycle-time charts are accurate from day one rather than showing
every item as created on migration day.

## What does not transfer yet

Named honestly, and tracked in the [feature matrix](../product/feature-matrix.md):

- **Attachments.** Files stay in Jira. Download anything you need to keep.
- **Issue links** (blocks, relates to, duplicates). Re-create the ones that matter.
- **Custom fields.** Freehold has no custom fields yet, so there is nowhere to put them.
- **Workflow rules**, conditions, validators and post-functions.
- **Permission and notification schemes.** Freehold's model is three roles; set them up fresh.

Export your Jira data before your instance goes read-only, even if you are not migrating yet. A CSV
costs nothing to keep.

## After importing

1. **Check the workflow.** Settings → Workflow. The importer creates any status it met and guesses the
   category. Confirm each one is in the right column, because categories drive every report.
2. **Check the sprints.** Settings and the backlog. Mark the current one active.
3. **Re-assign the unmatched.** The warnings list every name it could not resolve.
4. **Spot-check a migrated item.** Open one with comments and history and confirm the dates look right.

## Importing more than one project

Repeat per project, one space each. Spaces are independent, which is the point: there is no global
scheme to coordinate.

## Going back out

Every space exports to complete JSON from **Settings → Export**, and that file re-imports. You are not
locked in here either, and we would rather say so.
