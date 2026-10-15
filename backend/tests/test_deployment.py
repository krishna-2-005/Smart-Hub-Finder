"""Serverless (Vercel) behaviour: settings defaults, lazy start-up, read-only dataset, loop-safe HTTP client."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import PROJECT_ROOT, Settings
from app.services.routing_service import RoutingService


def test_vercel_settings_defaults():
    s = Settings(vercel=True, _env_file=None)
    tmp = Path(tempfile.gettempdir())
    assert s.platform == "vercel"
    assert s.dataset_read_only is True and s.persistent_storage is False
    assert s.db_path.is_relative_to(tmp) and s.exports_path.is_relative_to(tmp)
    assert s.max_upload_mb < 4.5
    local = Settings(vercel=False, _env_file=None)
    assert local.db_path == local.data_dir / "app.db" and not local.dataset_read_only


def test_http_client_follows_the_event_loop():
    svc = RoutingService(Settings(_env_file=None))

    async def grab():
        return svc.http()

    first = asyncio.run(grab())
    second = asyncio.run(grab())  # new loop: the old pooled client must not be reused
    assert first is not second

    async def same_loop():
        return svc.http() is svc.http()

    assert asyncio.run(same_loop())


SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
from index import app   # the Vercel entry point (api/index.py)

c = TestClient(app)     # NOT used as a context manager: no lifespan events, like serverless
out = {}
h = c.get("/api/health").json()
out["deployment"] = h["deployment"]
out["hubs"] = c.get("/api/hubs", params={"limit": 1}).json()["total"]
out["activate"] = c.post("/api/import-kml", files={"file": ("a.kml", b"<kml/>", "application/xml")},
                         data={"activate": "true"}).status_code
out["generate"] = c.post("/api/export/generate-files").status_code
out["settings"] = c.put("/api/settings", json={"top_n": 7}).status_code
print("RESULT" + json.dumps(out))
"""


def test_vercel_entrypoint_without_lifespan(tmp_path, data_dir):
    work = tmp_path / "work"
    env = {**os.environ, "VERCEL": "1", "DATA_DIR": str(data_dir), "WORK_DIR": str(work),
           "GOOGLE_MAPS_API_KEY": "", "ORS_API_KEY": ""}
    env.pop("DATABASE_PATH", None)
    proc = subprocess.run([sys.executable, "-c", SCRIPT, str(PROJECT_ROOT / "api")], env=env,
                          capture_output=True, text=True, timeout=180, cwd=str(tmp_path))
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line, proc.stderr[-2000:]
    out = json.loads(line[len("RESULT"):])
    assert out["deployment"]["platform"] == "vercel"
    assert out["deployment"]["read_only_dataset"] is True
    assert out["hubs"] == 361
    assert out["activate"] == 403
    assert out["generate"] == 403
    assert out["settings"] == 200
    assert (work / "app.db").exists(), "SQLite must live in the writable work dir"
    assert not (data_dir / "app.db").exists(), "the read-only dataset dir must not be written"
