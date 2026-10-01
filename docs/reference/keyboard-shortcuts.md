# Keyboard shortcuts

Shortcuts are off while you are typing in a field, so they never swallow a keystroke.

## Anywhere

| Key | Does |
|---|---|
| `Ctrl` / `Cmd` + `K` | Command palette: run a command, jump to a key like `WEB-12`, or search titles |
| `C` | Create a work item |
| `/` | Jump to the filter box |
| `Esc` | Close the dialog, palette or panel |

## Switching view

Number keys jump straight to a view in the current space.

| Key | View |
|---|---|
| `1` | Board |
| `2` | Backlog |
| `3` | List |
| `4` | Timeline |
| `5` | Calendar |
| `6` | Reports |
| `7` | Activity |
| `8` | Settings |

## In the command palette

| Key | Does |
|---|---|
| `↑` `↓` | Move |
| `Enter` | Run |
| `Esc` | Close |

## On a board

| Key | Does |
|---|---|
| `Tab` | Move between cards |
| `Enter` | Open the focused card |

## In a form

| Key | Does |
|---|---|
| `Ctrl` / `Cmd` + `Enter` | Save and close |
| `Enter` | In a quick-create box, create and stay |

## Quick create syntax

The quick-create boxes on the board and backlog parse shorthand, so one line makes a complete item:

```
Fix login timeout @kiran !high #auth ~3
```

| Token | Sets |
|---|---|
| `@name` | Assignee |
| `!high` | Priority |
| `#label` | Label |
| `~3` | Story points |
