#!/usr/bin/env python3
"""Check whether an instance is fit for other people to rely on.

validate.py asks "does the product work". This asks "is this deployment safe to put a team on",
which is a different question and the one that sinks pilots: default passwords, mail that silently
goes nowhere, links in emails pointing at localhost, no backup.

    python scripts/preflight.py https://tracker.example.com
    python scripts/preflight.py http://localhost:8080 --compose fh-pilot

Checks that need the container are skipped, not failed, when --compose is not given.
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

OK, WARN, FAIL = "ok", "warn", "fail"
results = []


def note(level, title, detail=""):
    results.append((level, title, detail))


def get(url, path):
    with urllib.request.urlopen(url.rstrip("/") + path, timeout=15) as r:
        return json.loads(r.read())


def compose_env(project, var):
    """Read an environment variable as the running app container actually sees it."""
    try:
        cid = subprocess.run(["docker", "compose", "-p", project, "ps", "-q", "app"],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        if not cid:
            return None
        out = subprocess.run(["docker", "exec", cid, "printenv", var],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?", default="http://localhost:8080")
    ap.add_argument("--compose", help="docker compose project name, for checks inside the container")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    # --- reachable and healthy -------------------------------------------------
    try:
        h = get(url, "/api/health")
        note(OK, f"reachable and healthy, version {h.get('version')}")
    except Exception as e:  # noqa: BLE001
        note(FAIL, "not reachable", f"{url}: {e}")
        report()
        return

    # --- transport -------------------------------------------------------------
    if url.startswith("https://"):
        note(OK, "served over HTTPS")
    elif "localhost" in url or "127.0.0.1" in url:
        note(WARN, "running on localhost",
             "only you can reach this. A pilot team needs a hostname they can open")
    else:
        note(FAIL, "served over plain HTTP",
             "passwords and session tokens cross the network in clear text. Terminate TLS at a proxy")

    # --- who can get in --------------------------------------------------------
    try:
        st = get(url, "/api/auth/status")
        if st.get("needs_setup"):
            note(WARN, "no accounts yet", "the first person to find this page becomes the site admin")
        else:
            note(OK, "site admin account exists")
        if st.get("allow_signup"):
            note(WARN, "sign-up is open",
                 "anyone who can reach the page can create an account. Fine on a private network, "
                 "not on a public one")
        else:
            note(OK, "sign-up is closed, admins create accounts")
        if st.get("source_url"):
            note(OK, "source is offered to users (AGPL section 13)", st["source_url"])
    except Exception as e:  # noqa: BLE001
        note(WARN, "could not read auth status", str(e))

    # --- things only visible inside the container ------------------------------
    if not args.compose:
        note(WARN, "container checks skipped",
             "pass --compose <project> to check secrets, mail and backups")
    else:
        p = args.compose
        pw = compose_env(p, "POSTGRES_PASSWORD")
        db = compose_env(p, "DATABASE_URL") or ""
        if pw is None and not db:
            note(WARN, "could not reach the container", f"is `docker compose -p {p}` running?")
        else:
            if ":freehold@" in db or ":opentrack@" in db:
                note(FAIL, "database is using the published default password",
                     "set POSTGRES_PASSWORD in .env and recreate. It is in the public repo")
            else:
                note(OK, "database password is not the default")

            secret = compose_env(p, "SECRET_KEY")
            if not secret:
                note(WARN, "SECRET_KEY is not set explicitly",
                     "one is generated into the data volume. Fine for a single container; set it "
                     "before you run more than one, or they reject each other's sessions")
            else:
                note(OK, "SECRET_KEY is set explicitly")

            smtp = compose_env(p, "SMTP_HOST")
            if not smtp:
                note(FAIL, "no SMTP server configured",
                     "every notification is written to the log instead of sent. People will say "
                     "they were never told, and they will be right")
            else:
                note(OK, f"email is configured via {smtp}")

            base = compose_env(p, "BASE_URL") or ""
            if base and base.rstrip("/") != url:
                note(FAIL, "BASE_URL does not match the address people use",
                     f"emails will link to {base}, not {url}")
            elif base:
                note(OK, "BASE_URL matches the address in use")

    # --- is the app reachable around the proxy? -------------------------------
    if args.compose and url.startswith("https://"):
        try:
            out = subprocess.run(["docker", "compose", "-p", args.compose, "ps", "--format",
                                  "{{.Publishers}}"], capture_output=True, text=True, timeout=20).stdout
            # A published port on 0.0.0.0 means the app answers on plain HTTP as well as through
            # the proxy, so anyone who knows the address can skip TLS entirely.
            if "0.0.0.0" in out:
                note(FAIL, "the app is published on every interface",
                     "TLS can be bypassed by going straight to the port. Set FREEHOLD_BIND=127.0.0.1 "
                     "and use docker-compose.prod.yml so only the proxy is exposed")
            else:
                note(OK, "only the proxy is exposed")
        except Exception:  # noqa: BLE001
            pass

    # --- can you get the data back out? ---------------------------------------
    if args.compose:
        try:
            cid = subprocess.run(["docker", "compose", "-p", args.compose, "ps", "-q", "db"],
                                 capture_output=True, text=True, timeout=20).stdout.strip()
            if cid:
                r = subprocess.run(["docker", "exec", cid, "pg_dump", "-U", "freehold",
                                    "--schema-only", "freehold"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode == 0 and "CREATE TABLE" in r.stdout:
                    note(OK, "a database backup can be taken")
                else:
                    note(WARN, "pg_dump did not succeed", (r.stderr or "")[:140])
        except Exception as e:  # noqa: BLE001
            note(WARN, "could not test a backup", str(e))

    report()


def report():
    width = 74
    print()
    for level, title, detail in results:
        tag = {OK: "ok  ", WARN: "warn", FAIL: "FAIL"}[level]
        print(f"  {tag}  {title}")
        if detail:
            for line in [detail[i:i + width] for i in range(0, len(detail), width)]:
                print(f"        {line}")
    fails = sum(1 for l, _, _ in results if l == FAIL)
    warns = sum(1 for l, _, _ in results if l == WARN)
    print("\n" + "=" * 62)
    if fails:
        print(f"  {fails} blocking, {warns} to look at. Not ready for other people yet.")
    elif warns:
        print(f"  No blockers, {warns} to look at.")
    else:
        print("  Ready.")
    print("=" * 62)
    sys.exit(1 if fails else 0)


main()
