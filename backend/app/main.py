"""Freehold API and web app."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import config, notify
from .db import Base, SessionLocal, engine
from .routers import auth_users, items, reports_io, spaces

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("freehold")
VERSION = "0.1.0-beta"


async def _digest_loop():
    while True:
        await asyncio.sleep(300)
        try:
            with SessionLocal() as db:
                sent = notify.send_due_digests(db)
                if sent:
                    log.info("Sent %s digest emails", sent)
        except Exception:  # noqa: BLE001
            log.exception("Digest run failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    task = asyncio.create_task(_digest_loop())
    yield
    task.cancel()


app = FastAPI(title="Freehold", version=VERSION, lifespan=lifespan,
              description="Open-source work tracking. All endpoints live under /api; sign in to get a bearer token.")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if not request.url.path.startswith(("/api", "/docs", "/redoc", "/openapi.json")):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'self'")
    return response


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"ok": True, "version": VERSION}


for r in (auth_users.router, spaces.router, items.router, reports_io.router):
    app.include_router(r)

if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="web")
