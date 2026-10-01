# Backup and restore

Freehold keeps state in two places. A backup needs both.

| | Holds |
|---|---|
| PostgreSQL | Everything except files |
| The data volume | Attachments, and `secret.key` |

Losing `secret.key` signs everyone out but loses no data. Losing the data volume loses attachments
permanently, because they are not in the database.

## Backing up Docker

```bash
# database
docker compose exec -T db pg_dump -U freehold freehold > freehold-$(date +%F).sql

# attachments and secret key
docker run --rm -v freehold_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/freehold-data-$(date +%F).tar.gz -C /data .
```

The volume is named after the compose project, which is the folder name. Confirm yours with
`docker volume ls`.

## Restoring

```bash
docker compose up -d db

docker compose exec -T db psql -U freehold -d freehold < freehold-2026-10-01.sql

docker run --rm -v freehold_data:/data -v "$PWD":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/freehold-data-2026-10-01.tar.gz -C /data"

docker compose up -d
```

## Before upgrading

Freehold creates missing tables at startup and **does not yet run schema migrations**. Back up before
every upgrade until Alembic lands; it is the top item on the roadmap for exactly this reason.

## Per-space export

Separately from infrastructure backup, every space exports to complete JSON from **Settings → Export**,
and that file re-imports into any Freehold. Use it to move a space between instances, to hand a team
their data, or to keep a human-readable copy.

It covers items, comments, history, worklogs, links and sprints. It does **not** include attachment
files, which is why the data volume still needs backing up.

## What to verify

A backup you have not restored is a hypothesis. Restore into a scratch instance occasionally:

```bash
curl -s http://localhost:8080/api/health
```

Then open a space, check an attachment downloads, and open a report.
