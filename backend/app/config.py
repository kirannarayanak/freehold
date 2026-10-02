"""Runtime settings, read once from environment variables."""
import os
import secrets
from pathlib import Path

DATA_DIR = Path(os.getenv("FREEHOLD_DATA") or os.getenv("OPENTRACK_DATA") or "./data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'freehold.db'}")


def _secret_key() -> str:
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    path = DATA_DIR / "secret.key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    return key


SECRET_KEY = _secret_key()
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "168"))
ALLOW_SIGNUP = os.getenv("ALLOW_SIGNUP", "false").lower() == "true"
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
# AGPL section 13: anyone running a MODIFIED version over a network must offer its users the
# corresponding source. If you have changed Freehold, point this at your own repository. Leaving
# it at the upstream URL while running modified code does not satisfy the licence.
SOURCE_URL = os.getenv("SOURCE_URL", "https://github.com/freehold-dev/freehold")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Freehold <freehold@localhost>")
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() == "true"

FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", Path(__file__).resolve().parents[2] / "frontend"))
