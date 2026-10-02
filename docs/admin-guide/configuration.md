# Configuration

Freehold is configured entirely by environment variables, read once at startup. There is no settings
file to edit and no configuration stored in the database, so a deployment is reproducible from its
compose file.

With Docker, put these in `.env` next to `docker-compose.yml`. Start from `.env.example`.

## Core

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | SQLite in the data directory | SQLAlchemy URL. PostgreSQL in production: `postgresql+psycopg://user:pass@host:5432/freehold` |
| `FREEHOLD_DATA` | `./data` | Where attachments and the generated secret key live. `OPENTRACK_DATA` is still read if this is unset, for installs predating the rename |
| `SECRET_KEY` | generated | Signs session tokens. Leave empty and one is written to `<data>/secret.key`. **Changing it signs everyone out.** Set it explicitly if you run more than one app container, or they will reject each other's sessions |
| `BASE_URL` | `http://localhost:8080` | The address people actually use. Links in notification emails are built from it |
| `TOKEN_HOURS` | `168` | How long a session lasts. Default is one week |
| `SOURCE_URL` | the upstream repository | Where this instance's source can be obtained. **If you have modified Freehold, point this at your own repository**: AGPL section 13 requires a modified network-served version to offer its source to users. It is shown in the sidebar |

## Access

| Variable | Default | What it does |
|---|---|---|
| `ALLOW_SIGNUP` | `false` | `false`: only a site admin creates accounts. `true`: anyone who can reach the page can register. The **first** account is always allowed either way, so you can bootstrap |
| `MAX_UPLOAD_MB` | `25` | Largest attachment |

## Email

Without `SMTP_HOST`, Freehold writes emails to the application log instead of sending them. That is
deliberate: it means notifications are testable before you own a mail server.

| Variable | Default |
|---|---|
| `SMTP_HOST` | empty, logs instead of sending |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | empty |
| `SMTP_PASSWORD` | empty |
| `SMTP_FROM` | `Freehold <freehold@localhost>` |
| `SMTP_TLS` | `true` |

See [email](email.md).

## Docker only

| Variable | Default | What it does |
|---|---|---|
| `FREEHOLD_PORT` | `8080` | Host port |
| `FREEHOLD_BIND` | `0.0.0.0` | Which interface to publish on. Set to `127.0.0.1` on a public server so the only way in is a TLS-terminating proxy |
| `FREEHOLD_HOST` | unset | Hostname for the Caddy proxy, used only by `docker-compose.prod.yml` |
| `POSTGRES_PASSWORD` | `freehold` | **Change this before the instance is reachable by anyone else** |

## Development only

| Variable | Default | What it does |
|---|---|---|
| `FRONTEND_DIR` | `../frontend` | Where the static files are served from |

## Minimum safe production set

```bash
POSTGRES_PASSWORD=<long random string>
SECRET_KEY=<long random string>
BASE_URL=https://tracker.yourcompany.com
ALLOW_SIGNUP=false
SMTP_HOST=smtp.yourcompany.com
```

Generate the secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
