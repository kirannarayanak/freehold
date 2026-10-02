# OQL: the Freehold Query Language

OQL filters work items. It is JQL-shaped, so anyone who knows JQL can read it, but it is deliberately
smaller and it fails fast: the browser runs the same grammar as the server, so a mistake is underlined as
you type instead of after a round trip.

Type a query in the filter box at the top of any space. Save it with **Save filter**.

```
assignee = me AND status != Done
type in (Bug, Task) AND priority:high AND due < 7d
label:payments OR is:blocked ORDER BY priority DESC, due
"checkout flow" -is:done
```

## Fields

| Field | Matches | Example |
|---|---|---|
| `assignee` | Anyone assigned | `assignee = me` |
| `reporter` | Who raised it | `reporter = kiran` |
| `watcher` | Anyone watching | `watcher = me` |
| `status` | Workflow status name | `status = "In review"` |
| `category` | Status category | `category = done` |
| `type` | Epic, Story, Task, Bug, Subtask | `type in (Bug, Task)` |
| `priority` | Highest, High, Medium, Low | `priority = High` |
| `label` | Any label | `label:payments` |
| `sprint` | Sprint name | `sprint = "Sprint 4"` |
| `parent` | Parent or epic key | `parent = WEB-1` |
| `key` | Work item key | `key = WEB-12` |
| `title` | Summary text | `title ~ checkout` |
| `description` | Body text | `description ~ webhook` |
| `text` | Key, summary, description and labels at once | `text ~ checkout` |
| `space` | Space key | `space = WEB` |
| `due` `start` `created` `updated` `resolved` | Dates | `due < today` |
| `points` `estimate` `logged` | Numbers | `points >= 5` |

### Aliases

Jira names work where they differ, so pasted JQL often just runs:

`summary` → `title` · `issuetype` → `type` · `labels` → `label` · `epic` → `parent` ·
`duedate` → `due` · `startdate` → `start` · `storypoints` → `points` ·
`statuscategory` → `category` · `project` → `space` · `watchers` → `watcher` · `assignees` → `assignee`

## Operators

| Operator | Meaning |
|---|---|
| `=` | Equals |
| `!=` | Does not equal |
| `:` | Equals, shorthand. `priority:high` |
| `~` | Contains. `title ~ checkout` |
| `<` `>` `<=` `>=` | Compare dates and numbers |
| `in (a, b)` | Any of |
| `is empty` | No value set |

`priority` `type` `category` `space` and `key` match exactly, so `priority:high` finds High and never
Highest. Everything else matches loosely.

## People

`me` and `currentuser()` both mean you, so a saved filter shared with the team shows each person their
own work.

`=` matches a person **exactly**, against their display name, handle or email. `:` and `~` match part of
one. So `assignee = sam.okafor` finds Sam, `assignee = sam` finds nobody, and `assignee ~ sam` finds Sam
and anyone else whose details contain "sam". Exactness is the point: a partial `=` would quietly match
Samantha too. The same rule applies to custom fields of type person.

```
assignee = me AND status != Done
```

## Dates

| Form | Means |
|---|---|
| `2026-10-01` | That date |
| `today`, `now` | Today |
| `7d` `2w` `3m` | 7 days, 2 weeks, 3 months from now |
| `-7d` `-2w` | Ago |
| `startofweek()` `endofweek()` | This week's Monday / Sunday |
| `startofmonth()` | The 1st |

```
due < today AND status != Done        overdue
created > -7d                         raised this week
resolved > startofmonth()             closed this month
```

## Shortcuts

| Shortcut | Means |
|---|---|
| `is:open` | Not in a done status |
| `is:done` | In a done status. `is:closed` and `is:resolved` are the same thing |
| `is:blocked` | Blocked by an unfinished item |
| `is:overdue` | Past its due date and not done |
| `is:mine` | Assigned to you |
| `is:assigned` | Has any assignee |
| `is:unassigned` | Has none |
| `is:watching` | You are watching it |
| `is:backlog` | Not in a sprint |
| `is:epic` | Is an epic |

## Combining

`AND` `OR` `NOT`, with parentheses.

```
(is:mine OR watcher = me) AND is:open
type = Bug AND NOT label:wontfix
```

A `-` prefix negates a single term, which is quicker than `NOT`:

```
-is:done            not done
-label:chore        not labelled chore
```

## Free text

Any bare word searches summaries and descriptions. Quote a phrase to keep it together.

```
checkout                      the word
"checkout flow"               the phrase
"checkout flow" AND is:open
```

## Sorting

```
ORDER BY priority DESC, due
```

Sorts by any field. `DESC` reverses. Priority sorts by rank, not alphabetically, so Highest comes first.

## Errors

OQL reports the problem rather than returning nothing: a missing closing parenthesis, an unknown field, a
date it cannot read. The message names the fix, for example
`'nextweek' is not a date. Try 2026-10-01, today, -7d or 2w.`

## Known limits

Named honestly. These are real gaps against JQL, tracked in the [feature matrix](../product/feature-matrix.md):

- No regular expressions
- No subqueries
- No visual query builder yet
- Filters apply within one space; cross-space search is the command palette only

## Custom fields

Every custom field in a space is filterable by its key, which is shown next to the field in
**Settings → Custom fields**. A field called Severity is `severity`:

```
severity = High
severity in (High, Critical) AND is:open
cost > 1000
target_date < 2027-01-01
teams = web                       a multiselect matches if any value matches
regression = true                 a checkbox
owner = me                        a user field, matching like assignee does
customer ~ acme                   contains
severity is empty
```

Numbers, dates and checkboxes compare by type rather than as text, so `cost > 900` does what it looks
like. A user field matches by partial name, handle or `me`, exactly as `assignee` does.

A custom field key can never shadow a built-in one: keys like `status` or `due` are refused when the
field is created, so adding a field cannot quietly change what an existing filter means.
