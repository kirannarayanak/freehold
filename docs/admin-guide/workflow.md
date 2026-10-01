# Workflow

Each space has its own workflow: an ordered list of statuses, each in a category, each with an optional
WIP limit. Edit it under space **Settings → Workflow**. There is one screen and no schemes.

## Statuses

Order is left to right on the board. Add, rename, reorder and remove statuses freely.

Renaming a status moves every item on it; nothing is orphaned.

## Categories matter more than names

Every status belongs to one of three categories:

| Category | Means |
|---|---|
| **To do** | Not started |
| **In progress** | Started |
| **Done** | Finished |

Call your statuses whatever your team says out loud. The **category** is what reports use, so:

- Burndown counts work as complete when it reaches a **Done** status
- Cycle time measures from first **In progress** to first **Done**
- Cumulative flow bands by category
- `is:open` and `is:done` in [OQL](../reference/oql.md) read the category

A status in the wrong category produces charts that look plausible and are wrong, so this is the one
setting worth double-checking after an import.

## WIP limits

Set a limit per status, or `0` for none. When a column exceeds its limit the count turns red on the
board. It is a signal, not a block: Freehold warns rather than refusing, because the work is usually
already happening and hiding it helps nobody.

## Templates

Creating a space offers two starting points:

- **Scrum** — To do, In progress, In review, Done, with sprints and a backlog
- **Kanban** — continuous flow with WIP limits

Both are just starting workflows. Either can be edited into the other.

## What is not here yet

Transition rules, conditions, validators, post-functions and approvals are all planned and none are
built. Any status can currently move to any other status.

This is a real gap for regulated teams. It is also the single largest source of configuration sprawl in
Jira, so when it arrives it will be deliberately smaller than Jira's version. See the
[feature matrix](../product/feature-matrix.md).
