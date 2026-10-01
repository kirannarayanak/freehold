# Reports

Six reports, under **Reports** (`6`) in any space.

**Every one is rebuilt from the history table**, not from current state. If someone edits an item today,
last quarter's chart does not move. This is a deliberate difference from Jira, where reports read current
state and historical charts shift under you after an edit.

All of them read status **categories**, not status names, so the categories in your
[workflow](../admin-guide/workflow.md) need to be right or the charts will be plausible and wrong.

## Burndown

Remaining story points across the active sprint, against an ideal line.

Days before any sprint work existed are left as gaps rather than drawn as zero, so a sprint that started
before its items were created shows an honest break rather than a cliff.

## Velocity

Committed versus completed points for the last eight **closed** sprints, with an average. A sprint has to
be completed properly to appear.

## Cumulative flow

How many items sat in each category per day over 30 days. Widening bands mean work arriving faster than
it leaves.

## Created vs resolved

Two lines over 30 days. If created stays above resolved, the backlog is growing.

## Cycle time

How long finished items took, from first **In progress** to first **Done**, with a median. Points above
the line are the ones worth asking about.

## Open points by assignee

Unfinished points per person. For spotting imbalance, not for performance.

## Tiles

Above the charts: open items, open bugs, overdue, blocked, and hours logged against estimated.

## What is not built

Custom dashboards, gadgets, and cross-space reporting. See the
[feature matrix](../product/feature-matrix.md).
