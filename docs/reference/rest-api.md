# REST API

Freehold is API-first: the web app is a client of this API and uses nothing private. Anything the UI does,
you can do.

Interactive OpenAPI documentation is served by your own instance at **`/docs`**, and the schema at
**`/openapi.json`**. That is the authoritative reference; this page is the orientation.

## Authentication

Sign in, get a bearer token, send it on every request.

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}' | jq -r .token)

curl -s http://localhost:8080/api/spaces -H "Authorization: Bearer $TOKEN"
```

Tokens last `TOKEN_HOURS` (default 168, one week).

File downloads and exports also accept `?token=<token>` in the query string, because a browser following
a download link cannot set a header. Treat such URLs as secrets.

## Shape

Everything lives under `/api`. Keys are strings like `WEB-12`; ids are integers.

| | |
|---|---|
| Errors | HTTP status plus `{"detail": "A sentence saying how to fix it"}` |
| Validation | `422` with the same shape |
| Permissions | `403`, or `404` where revealing existence would leak |
| Timestamps | Naive UTC ISO 8601 |
| Dates | `YYYY-MM-DD` |

## The one call that matters

The web app loads a whole space in one request and filters in memory. That is why it feels instant, and
it is usually what you want too:

```bash
curl -s "http://localhost:8080/api/spaces/WEB" -H "Authorization: Bearer $TOKEN"
```

Returns the space, its statuses, members, sprints, saved filters and every work item.

For very large spaces this is a known scaling limit; paging is not built yet.

## Endpoints

### Auth and people

| Method | Path | |
|---|---|---|
| `GET` | `/api/auth/status` | Whether setup is needed and whether signup is open |
| `POST` | `/api/auth/register` | First account, or any account when `ALLOW_SIGNUP=true` |
| `POST` | `/api/auth/login` | Returns a token |
| `GET` `PATCH` | `/api/me` | Your profile and notification preferences |
| `GET` `POST` | `/api/users` | Site admin: list and create |
| `PATCH` | `/api/users/{id}` | Site admin: rename, promote, deactivate, reset password |

### Spaces

| Method | Path | |
|---|---|---|
| `GET` `POST` | `/api/spaces` | |
| `GET` `PATCH` `DELETE` | `/api/spaces/{key}` | `GET` returns the full bundle |
| `GET` `POST` | `/api/spaces/{key}/members` | |
| `PATCH` `DELETE` | `/api/spaces/{key}/members/{user_id}` | Change role, remove |
| `GET` | `/api/spaces/{key}/activity` | |
| `GET` | `/api/spaces/{key}/changes` | Poll for changes since a timestamp |
| `GET` `POST` | `/api/spaces/{key}/filters` | Saved filters |
| `DELETE` | `/api/filters/{id}` | |

### Work items

| Method | Path | |
|---|---|---|
| `POST` | `/api/spaces/{key}/items` | Create |
| `GET` `PATCH` `DELETE` | `/api/items/{key}` | `GET` includes comments, history, links, worklogs |
| `POST` | `/api/items/bulk` | Change many at once |
| `POST` | `/api/items/{key}/clone` | |
| `POST` | `/api/items/{key}/comments` | |
| `PATCH` `DELETE` | `/api/comments/{id}` | |
| `POST` | `/api/items/{key}/links` | |
| `DELETE` | `/api/links/{id}` | |
| `POST` | `/api/items/{key}/worklogs` | |
| `DELETE` | `/api/worklogs/{id}` | |
| `POST` | `/api/items/{key}/attachments` | multipart |
| `GET` `DELETE` | `/api/attachments/{id}` | |
| `POST` | `/api/items/{key}/watch` · `/mute` | |
| `GET` | `/api/search?q=` | Across spaces you can see |

Every write goes through one validation and history path, so the API cannot produce a state the UI
could not, and every change is recorded.

### Sprints

| Method | Path | |
|---|---|---|
| `POST` | `/api/spaces/{key}/sprints` | |
| `PATCH` `DELETE` | `/api/sprints/{id}` | Includes starting one, by setting state |
| `POST` | `/api/sprints/{id}/complete` | Records committed and completed points |

### Reports

`GET /api/spaces/{key}/reports/{name}` where name is one of:

`burndown` · `velocity` · `cfd` · `created-vs-resolved` · `cycle-time`

`burndown` takes `?sprint_id=`, and defaults to the active sprint. The 30-day reports take `?days=`,
clamped to 7–180.

### Notifications

| Method | Path | |
|---|---|---|
| `GET` | `/api/notifications` | |
| `POST` | `/api/notifications/read` | Mark read |

### Import and export

| Method | Path | |
|---|---|---|
| `GET` | `/api/spaces/{key}/export` | Complete JSON |
| `GET` | `/api/spaces/{key}/export.csv` | |
| `POST` | `/api/spaces/{key}/import/jira` | Jira CSV, multipart |
| `POST` | `/api/spaces/{key}/import/freehold` | Freehold JSON, multipart. Also accepts files exported before the rename |

### Versions and releases

| Method | Path | |
|---|---|---|
| `GET` `POST` | `/api/spaces/{key}/versions` | |
| `PATCH` `DELETE` | `/api/versions/{id}` | Rename, set a date, release, archive. Releasing is refused while work in it is unfinished |
| `GET` | `/api/versions/{id}/notes` | Generated release notes as markdown |

### Webhooks

| Method | Path | |
|---|---|---|
| `GET` `POST` | `/api/spaces/{key}/webhooks` | Space admin only. The signing secret is returned once, on creation |
| `PATCH` `DELETE` | `/api/webhooks/{id}` | |
| `POST` | `/api/webhooks/{id}/test` | Send a ping to confirm the receiver works |

Events: `item.created` `item.updated` `item.deleted` `comment.created` `sprint.started` `sprint.completed`
`version.released`. Subscribe to a subset, or leave the list empty for all.

Each request carries `X-Freehold-Signature: sha256=<hmac>` over the raw body. Verify it:

```python
import hmac, hashlib
expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(expected, request.headers["X-Freehold-Signature"])
```

Delivery is best effort and never blocks the write that triggered it. A receiver that is down does not
stop anyone filing work; the failure is recorded on the hook and shown in Settings.

### API tokens

| Method | Path | |
|---|---|---|
| `GET` `POST` | `/api/me/tokens` | `POST` returns the token once. Only its hash is stored |
| `DELETE` | `/api/me/tokens/{id}` | Revoked immediately |

A token starts `fh_` and goes on the same `Authorization: Bearer` header as a session token, so every
client works unchanged. It acts as the person who created it. Optional expiry via `expires_days`.

```bash
curl -s http://localhost:8080/api/spaces/WEB -H "Authorization: Bearer fh_..."
```

### Health

`GET /api/health` needs no authentication and checks the database. Use it for your load balancer.

## Example: create and move an item

```bash
curl -s -X POST http://localhost:8080/api/spaces/WEB/items \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Fix login timeout","type":"Bug","priority":"High","points":3,"labels":["auth"]}'

curl -s -X PATCH http://localhost:8080/api/items/WEB-42 \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status":"In progress"}'
```

## Notes

- Webhooks are outgoing only. There is no incoming receiver yet, so a Git host cannot push to Freehold
- The UI still polls `/api/spaces/{key}/changes` every 15 seconds; there are no server-sent events
- Login is rate limited in memory, per app process. Put a limiter at the proxy on a public network
