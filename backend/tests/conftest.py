import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="opentrack-test-")
os.environ.setdefault("OPENTRACK_DATA", _tmp)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["ALLOW_SIGNUP"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
