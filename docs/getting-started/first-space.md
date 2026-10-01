# Your first space

Fifteen minutes from an empty install to a team running a sprint.

## 1. Create the admin account

Open <http://localhost:8080>. The first account you create becomes the **site admin**, which is the only
account that can create other accounts.

Use a real email address: it is how you are mentioned and notified.

## 2. Create a space

A **space** is one team's or one product's work. It owns its own workflow, members, sprints and saved
filters. Nothing is shared between spaces, which is why there is no global configuration to coordinate.

| | |
|---|---|
| **Name** | What people call it. "Website relaunch" |
| **Key** | The prefix on every item. `WEB` gives you `WEB-1`, `WEB-2`. **Pick carefully: it is permanent** |
| **Template** | Scrum (sprints and a backlog) or Kanban (continuous flow with WIP limits) |

If you are migrating from Jira, use the **same key as the Jira project** so existing keys survive the
import. See [migrating from Jira](../migrating/from-jira.md).

## 3. Add your team

Two steps, because accounts and access are separate concerns:

1. **People (site admin)** in the sidebar → create each account with a temporary password, shared privately
2. Space **Settings → Members** → add them with a role

| Role | Can |
|---|---|
| Viewer | See everything, change nothing |
| Member | Create, edit, comment, move work |
| Admin | All of that, plus settings and members |

See [users and roles](../admin-guide/users-and-roles.md).

## 4. Check the workflow

Space **Settings → Workflow**. The template gives you To do, In progress, In review, Done.

Rename them to whatever your team actually says. What matters is the **category** on each one, because
every report reads categories rather than names. Getting a category wrong produces charts that look
right and are wrong.

See [workflow](../admin-guide/workflow.md).

## 5. Add some work

Press `C`, or type into the quick-create box on the board. The box takes shorthand:

```
Fix login timeout @kiran !high #auth ~3
```

That creates a High priority item, assigned to Kiran, labelled `auth`, estimated at 3 points.

Make an **Epic** first if you have a larger body of work, then set it as the parent on the items inside it.

## 6. Plan a sprint

Scrum spaces only.

1. **Backlog** (`2`)
2. Drag items from the backlog into Sprint 1
3. Set a goal, one sentence on what the sprint is for
4. **Start sprint**

The board (`1`) now shows that sprint.

## 7. Work

- Drag cards between columns to change status
- Click any card to open it: description, comments, checklist, links, attachments, time
- `@mention` someone to pull them in
- The filter box takes [OQL](../reference/oql.md): `assignee = me AND status != Done`

## 8. Complete the sprint

**Complete sprint** on the board. Unfinished work returns to the backlog and Freehold records what was
committed against what was completed.

Do this properly rather than deleting sprints: that committed/completed pair is what makes the velocity
report meaningful, and it cannot be reconstructed later.

## Next

| | |
|---|---|
| [Work items](../user-guide/work-items.md) | Every field, links, markdown, time |
| [OQL](../reference/oql.md) | The filter language |
| [Reports](../user-guide/reports.md) | What each chart means |
| [Keyboard shortcuts](../reference/keyboard-shortcuts.md) | |
