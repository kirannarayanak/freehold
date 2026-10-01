# Glossary

Freehold terms, and the Jira words they replace.

| Freehold | Jira | Notes |
|---|---|---|
| **Space** | Project | A team's or product's work. Owns its own workflow, members and sprints |
| **Work item** | Issue | "Issue" implies a problem; most work is not a problem |
| **Key** | Issue key | `WEB-12`. Never reused |
| **Status category** | Status category | To do / In progress / Done. Drives every report |
| **OQL** | JQL | Same shape, smaller surface, same grammar in browser and server |
| **Saved filter** | Filter | Personal or shared with a space |
| **Space role** | Permission scheme | Three roles instead of a scheme matrix |
| **Site admin** | Jira administrator | Manages accounts, not content |
| **Worklog** | Work log | Hours against an item, with a note |
| **History** | Issue history | Freehold rebuilds reports from it |
| **Digest** | Batched notification | Per person, not per project |

## Things Jira has that Freehold does not

So you are not hunting for them:

| Jira | Status in Freehold |
|---|---|
| Resolution (separate from status) | Not built. Status category carries it |
| Components | Not built. Use labels |
| Versions / fix version | Not built. A real gap for versioned software |
| Custom fields | Not built. The largest parity gap |
| Screens and screen schemes | Deliberately not built |
| Permission schemes | Deliberately replaced by three roles |
| Workflow per issue type | Deliberately not built |
| Marketplace apps | Deliberately not built |
| Voting | Deliberately not built |

See the [feature matrix](../product/feature-matrix.md) for the full picture.
