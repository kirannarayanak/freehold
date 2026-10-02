# Install with Docker

The supported way to run Freehold. One command brings up the app and PostgreSQL.

## Requirements

- Docker with Compose v2
- 1 GB RAM and a little disk. Freehold is not heavy.

## Install

```bash
git clone https://github.com/kirannarayanak/freehold.git
cd freehold
docker compose up -d --build
```

Open <http://localhost:8080>. The first account you create becomes the site admin.

That is the whole installation. There is no licence key, no account to register, and nothing phones home.

## Configure before putting it on a network

Copy the example file and edit it. Every value is optional for a local try-out; two of them matter the
moment anyone else can reach the page.

```bash
cp .env.example .env
```

| Set this | Why |
|---|---|
| `POSTGRES_PASSWORD` | The default is `freehold`. Change it. |
| `SECRET_KEY` | Leave empty and one is generated into the data volume. Set it explicitly if you run more than one app container, or they will not accept each other's sessions. |
| `BASE_URL` | The address people actually use. It is what links in notification emails point at. |

Full list in [configuration](../admin-guide/configuration.md).

## Sign-up is closed by default

`ALLOW_SIGNUP=false` means only a site admin creates accounts, which is usually what you want. The *first*
account is always allowed regardless, so you can bootstrap. Set it to `true` only if anyone who can reach
the page should be able to register themselves.

## Where your data lives

Two named Docker volumes:

- `db` — PostgreSQL
- `data` — attachments, and the generated `secret.key`

Both survive `docker compose down`. `docker compose down -v` **deletes them**. Back them up before
upgrading: see [backup and restore](../admin-guide/backup-and-restore.md).

## Upgrading

```bash
git pull
docker compose up -d --build
```

Freehold currently creates missing tables at startup and does not yet run schema migrations, so
**take a backup before upgrading.** Proper migrations are the top priority before 1.0.

## Running on another port

```bash
FREEHOLD_PORT=9000 docker compose up -d
```

## Behind a reverse proxy

The container already runs with `--proxy-headers --forwarded-allow-ips *`, so it honours
`X-Forwarded-For` and `X-Forwarded-Proto`. Terminate TLS at your proxy, point it at port 8080, and set
`BASE_URL` to the public address.

## Checking it is healthy

```bash
curl -s http://localhost:8080/api/health
```

Returns `{"ok":true,"version":"0.1.0-beta"}`. The container also has a Docker healthcheck, so
`docker compose ps` shows `healthy` once it is serving.
