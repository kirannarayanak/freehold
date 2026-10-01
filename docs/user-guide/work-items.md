# Work items

A work item is one piece of work. Every item has a key like `WEB-12`: the space key, then a number that
is never reused.

## Types

| Type | For |
|---|---|
| **Epic** | A large body of work that contains other items |
| **Story** | Something a user gets |
| **Task** | Something that needs doing |
| **Bug** | Something broken |
| **Subtask** | A piece of another item |

Types are presentational. They change the icon and how things group, not what is allowed.

## Fields

| Field | Notes |
|---|---|
| **Summary** | The one-line title |
| **Description** | Markdown. See below |
| **Status** | From your space's [workflow](../admin-guide/workflow.md) |
| **Assignees** | **More than one is allowed**, unlike Jira. Real work often has two people on it |
| **Reporter** | Who raised it |
| **Priority** | Highest, High, Medium, Low |
| **Labels** | Free text, comma separated |
| **Story points** | For estimation and burndown |
| **Estimate / time logged** | Hours. Log time with a note under the Time tab |
| **Start and due dates** | Drive the timeline, calendar and overdue flags |
| **Epic / parent** | Puts the item inside a larger one |
| **Sprint** | Which sprint it belongs to, or the backlog |
| **Checklist** | Small steps that do not deserve their own items |
| **Watchers** | Who gets notified. Watch or mute from the item header |

## Markdown

Descriptions and comments take markdown: headings, **bold**, lists, `code`, fenced blocks, quotes, links
and task lists.

```markdown
Some **markdown** with a task list:

- [x] done thing
- [ ] open thing

cc @bob.stone see WEB-1
```

Two things resolve automatically:

- `@handle` mentions a person and notifies them. Your own handle is on your profile
- A key like `WEB-1` becomes a link

All user text is escaped before rendering, so a description can never inject HTML.

## Custom fields

A space admin can add extra fields under **Settings → Custom fields**: text, number, date, single
select, multi select, checkbox, URL, or a person. They appear on every work item in that space,
alongside the built-in fields.

Each field has a **key**, shown next to it in settings, and that key is how you filter on it:
`severity = High`. See [OQL](../reference/oql.md).

Two things worth knowing:

- **A field's type cannot change once it exists.** The key is what values are stored under, so changing
  the type would reinterpret everything already saved. Archive the field and add a new one instead.
- **Archiving hides a field without losing data.** Values stay on the items and stay readable. Deleting
  the definition leaves the values orphaned, which is why archiving is offered first.

## Links

Relate items from the Links section:

| Link | Inverse shown on the other item |
|---|---|
| blocks | is blocked by |
| relates to | relates to |
| duplicates | is duplicated by |

Each link is stored once and the inverse is computed, so the two items can never disagree.

An item blocked by something unfinished shows a **Blocked** flag and matches `is:blocked`.

## Attachments

Drag files onto the item or use the attachment box. Images preview inline. The maximum size is set by
`MAX_UPLOAD_MB`, default 25 MB.

## Comments and history

Comments take markdown and mentions. The **History** tab records every field change with who and when.

That history is not just an audit trail: every [report](reports.md) is rebuilt from it, which is why
charts of past quarters stay correct after someone edits an item today.

## Creating quickly

Press `C` anywhere, or type into the quick-create box on a board column or the backlog. The box parses
shorthand:

```
Fix login timeout @kiran !high #auth ~3
```

`@name` assignee · `!high` priority · `#label` label · `~3` points

## Bulk changes

In the [List view](boards-and-sprints.md), tick several rows and a bulk bar appears for status, priority,
assignee and sprint in one action.
