# Users and roles

Freehold has two levels of access and three roles. That is the whole model, and it is deliberate: Jira's
permission schemes are widely reported to become unauditable, and too many of them are a measurable
performance problem. Three roles and a single permission check are easier to reason about and easier to
keep correct.

## Site admins

The **first account created** becomes the site admin. Site admins manage people under
**People (site admin)** in the sidebar:

- Create accounts with a temporary password
- Promote or demote other site admins
- Deactivate someone, which blocks sign-in but keeps their history intact
- Reset a password

There is no self-service password reset by email yet. A site admin resets it.

## Space roles

Everyone else's access is per space. Add people under space **Settings → Members**.

| Role | Can |
|---|---|
| **Viewer** | See everything in the space. Change nothing. For stakeholders |
| **Member** | Create, edit, comment, log time, move cards, manage sprints |
| **Admin** | Everything a member can, plus the workflow, members and space settings |

Someone with no membership in a space cannot see it at all, and it does not appear in their space list.

A person can hold a different role in each space. Site admins are not automatically space admins; they
manage accounts, not content.

## How this is enforced

Every endpoint that touches a space goes through one function, `get_space(db, key, user, need)`. There
is exactly one place in the codebase where space access is decided, which means it can be audited by
reading one function rather than reconstructing a scheme matrix.

Attachment downloads and exports additionally accept a `?token=` parameter so a browser can fetch a
file directly, and that token is checked the same way.

## Adding someone

1. A site admin creates the account under **People** and shares the temporary password privately.
2. A space admin adds them under space **Settings → Members** with a role.
3. They sign in and change their password under **Profile**.

People must have an account before they can be added to a space.

## Deactivating someone who leaves

Deactivate the account rather than deleting it. Their comments, history and worklogs stay attached and
reports stay correct. A deactivated account cannot sign in.
