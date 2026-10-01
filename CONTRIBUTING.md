# Contributing to Freehold

Thanks for helping. A few things keep Freehold easy to run and easy to hack on.

## Set up

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080 and create the first account. The web app has no build step: edit files in `frontend/` and reload.

## Before you open a pull request

- Run `pytest` in `backend/`, and `sh frontend/tests/run.sh` if you touched the web app.
- Add or update a test for any behaviour you change.
- If you change the query language, change both `backend/app/query.py` and `frontend/js/oql.js`, and keep their tests in step.
- Keep the frontend dependency-free and CDN-free. Many teams run Freehold on networks that cannot reach the internet.
- Never render user text as HTML without escaping it first (`MD.esc` or `MD.render`). The content security policy blocks inline scripts, so wire events with `data-act` and `data-change` attributes, not `onclick`.
- Write interface text in plain, sentence-case English that says what happens ("Save workflow", not "Submit").

## Good first issues

Look for the `good first issue` label, or pick something from the roadmap in the README and open an issue to talk it through first.
