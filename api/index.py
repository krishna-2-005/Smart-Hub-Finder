"""Vercel serverless entry point.

Vercel deploys every ``api/*.py`` file as a Python function and serves the
ASGI ``app`` it exports. ``vercel.json`` rewrites ``/api/*`` here; FastAPI still
sees the original path (e.g. ``/api/health``), so the routes are unchanged.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
