# Install from source

For development and contributing. For running Freehold properly, use [Docker](install-docker.md).

## Requirements

- Python 3.12
- Node 18+ (only to run the UI test suite)

## Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080
```

This runs on SQLite in `backend/data/`, which needs no setup. Open <http://localhost:8080>.

There is no build step for the frontend. It is plain JavaScript loaded as classic scripts, with no
bundler and no CDN, so it runs on networks with no internet access. Edit a file and reload the page.

## Running against PostgreSQL

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/freehold uvicorn app.main:app --port 8080
```

## Tests

Run both before every commit.

```bash
cd backend && pytest -q                 # API tests, SQLite
sh frontend/tests/run.sh                # UI click-through in jsdom, needs Node 18+
```

To run the API tests against PostgreSQL the way CI does:

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/freehold_test pytest -q
```

The UI test starts a throwaway server on port 8099, seeds demo data, and drives the real app in jsdom.
If it fails with "address already in use", a previous run left a server behind; kill it and retry.

## API documentation

With the server running, interactive OpenAPI docs are at <http://localhost:8080/docs>.
