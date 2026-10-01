# Email

Freehold sends two kinds of mail: instant notifications and digests. Both are driven by each person's own
preferences, not by an admin-configured scheme.

## Without SMTP

If `SMTP_HOST` is unset, Freehold writes every email it would have sent to the application log:

```bash
docker compose logs -f app
```

This is intentional. You can verify that the right people would be notified before you point it at a
real mail server.

## With SMTP

```bash
SMTP_HOST=smtp.yourcompany.com
SMTP_PORT=587
SMTP_USER=freehold@yourcompany.com
SMTP_PASSWORD=<app password>
SMTP_FROM=Freehold <freehold@yourcompany.com>
SMTP_TLS=true
BASE_URL=https://tracker.yourcompany.com
```

`BASE_URL` is not optional once email is on. Every link in every email is built from it, and if it is
wrong the mail still sends with links nobody can follow.

Restart after changing any of these: configuration is read once at startup.

## Digests

Anyone can choose digests instead of instant mail per event type, under **Profile and notifications**.
A background loop checks every five minutes and sends what is due.

**Digests are sent in UTC.** Per-user time zones are not built yet, so someone in Dubai gets their daily
digest on a UTC schedule. It is a known gap.

## Testing it

1. Set the SMTP variables and restart.
2. Have a colleague watch an item, or assign one to yourself from another account.
3. Check `docker compose logs app` for the send, and the inbox for arrival.

Failures are logged with the reason and never crash the request that triggered them; a bad mail server
cannot stop people filing work.
