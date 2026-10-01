# Notifications

Notifications belong to **you**, not to a project. Set them once under **Profile and notifications** and
they apply in every space.

This is a deliberate difference from Jira, where each project carries its own notification scheme, the
schemes drift apart over time, and nobody can reliably say what the system will send them.

## Events

| Event | Fires when |
|---|---|
| Assigned | Someone assigns you an item |
| Mentioned | Someone writes `@your.handle` |
| Comments | A comment on something you are involved in |
| Status changes | Work you are involved in moves |
| Other edits | Any other field change |

"Involved in" means you are an assignee, the reporter, or a watcher.

## Channels

Each event is independently **in app**, **by email**, both, or neither.

The bell in the header shows unread in-app notifications. Click through to the item.

## Instant or digest

Per event type, choose instant mail or a digest. Digests batch everything into one message.

**Digests are sent on a UTC schedule.** Per-user time zones are not built yet.

## Watching

Every item has **Watching** and **Mute** in its header.

- Creating or commenting on an item watches it automatically
- **Mute** silences one noisy item without changing your preferences anywhere else

Muting is per item and permanent until you unmute, which is the quickest fix for one thread that will
not stop.

## If email is not arriving

Ask your admin to check [email configuration](../admin-guide/email.md). With no SMTP server configured,
Freehold writes mail to the application log instead of sending it, so the notification worked and the
delivery did not.
