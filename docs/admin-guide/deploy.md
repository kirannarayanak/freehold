# Deploying for real

Running Freehold on a laptop behind a tunnel is fine for showing someone. It is not fine for a team:
the hostname changes when the tunnel restarts, and nothing is listening while the laptop sleeps. For
anyone depending on it, put it on a server.

This is the whole thing, and it costs about five pounds a month.

## What you need

- A small server. 1 vCPU and 1 GB of memory is enough. Hetzner, DigitalOcean, Vultr, anything.
- A domain, with an **A record pointing at the server's address**. Certificates are issued by
  checking that the name resolves to you, so DNS has to be right before you start.
- Docker with Compose v2 (2.24 or newer, for the port override in the production file).

## Install

```bash
git clone https://github.com/kirannarayanak/freehold.git
cd freehold
cp .env.example .env
```

Edit `.env`. The five that matter:

```bash
POSTGRES_PASSWORD=<long random string>
SECRET_KEY=<long random string>
BASE_URL=https://tracker.example.com
FREEHOLD_BIND=127.0.0.1          # the app must not be reachable except through the proxy
ALLOW_SIGNUP=false
```

Generate the secrets rather than inventing them:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then set the hostname and start it:

```bash
echo "FREEHOLD_HOST=tracker.example.com" >> .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Caddy obtains and renews the certificate on its own. Nothing to configure, nothing to remember in
ninety days.

## Why the production file exists

The default compose publishes the app on every interface, which is right on a laptop and wrong on a
public server: the app would answer on `http://your-server:8080` in clear text, so anyone who knew the
address could skip TLS and read passwords off the wire.

`docker-compose.prod.yml` binds the app to localhost and puts Caddy in front on 80 and 443. The proxy
becomes the only way in.

## Check it before anyone arrives

```bash
curl -s https://tracker.example.com/api/health
python scripts/preflight.py https://tracker.example.com --compose freehold
```

Preflight checks the things that quietly ruin a deployment: a default database password, no mail
server, notification links pointing somewhere nobody can reach, no working backup, and the app being
reachable around the proxy.

**Claim the admin account immediately after the first start.** Until somebody does, the instance
answers `needs_setup` and the first person to find it becomes the site admin.

## Firewall

Only 80, 443 and your SSH port need to be open. Postgres and the app are on the internal Docker
network and should not be reachable from outside at all.

```bash
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
```

## Email

Without `SMTP_HOST` every notification is written to the log instead of sent, and people will be
assigned work and told nothing. Set it before the team arrives; see [email](email.md).

## Backups

Both of these, on a schedule, off the machine:

```bash
docker compose exec -T db pg_dump -U freehold freehold > freehold-$(date +%F).sql
docker run --rm -v freehold_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/freehold-data-$(date +%F).tar.gz -C /data .
```

The database holds everything except attachments. The volume holds attachments and the signing key.
A backup of one without the other is not a backup. See
[backup and restore](backup-and-restore.md).

## Upgrading

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Migrations run at startup. Take a backup first anyway.
