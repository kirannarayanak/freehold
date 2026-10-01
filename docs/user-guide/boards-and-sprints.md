# Boards and sprints

Every space has the same views, reachable from the sidebar or with number keys `1`–`8`.
Settings is `8`.

## Board (`1`)

Your workflow as columns, left to right. Drag cards between columns to change status.

- **Group by** splits the board into swimlanes by assignee, epic, priority or type
- A column over its WIP limit turns its count red
- The quick-create box at the bottom of the first column adds work without leaving the board
- Scrum spaces show the active sprint. Kanban spaces show everything

## Backlog (`2`)

Plan here. Sprints at the top, the backlog below, epics on the right.

- Drag items between the backlog and a sprint, or use bulk edit in the List view
- Each sprint shows its item and point totals as you fill it
- **Start sprint** makes it active and the board switches to it
- **Complete sprint** closes it; unfinished work returns to the backlog
- Click an epic to filter to its children

Only one sprint is active at a time. Parallel sprints are not built yet.

## List (`3`)

Everything as a sortable table. Click a column to sort, tick rows for bulk edits, **Export CSV** for the
current filter.

This is the view to use with a [filter](../reference/oql.md): the filter box narrows every view, but the
list is where you see the result as data.

## Timeline (`4`)

Items with start and due dates as bars over a calendar, grouped by epic. Today is marked. Items without
dates do not appear.

## Calendar (`5`)

A month grid of due dates and sprint boundaries. Click any item to open it.

## Reports (`6`)

See [reports](reports.md).

## Activity (`7`)

Everything that happened in the space, newest first.

## Sprints

A sprint has a name, a goal, dates, and a state: **future**, **active** or **closed**.

When you complete a sprint, Freehold records what was committed and what was completed. That pair is what
makes the velocity report meaningful, so complete sprints properly rather than deleting them.

## Filtering

The filter box at the top narrows every view at once. It takes [OQL](../reference/oql.md):

```
assignee = me AND status != Done
```

**Save filter** keeps it in the sidebar. Saved filters can be personal or shared with the space.
