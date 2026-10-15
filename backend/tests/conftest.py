"""Shared fixtures.

Data tests run against the real source KML (processed once per session into a
temporary directory). Routing tests that need the network are marked
``live`` and are skipped automatically when the routing servers are
unreachable; set ``SKIP_LIVE=1`` to skip them explicitly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.config import PROJECT_ROOT, Settings  # noqa: E402
from app.services.pipeline import process_kml  # noqa: E402

SOURCE_KML = PROJECT_ROOT / "Akhil Copy.kml"
CONFIG = BACKEND / "config" / "classification.json"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: needs network access to a real routing provider")


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory) -> Path:
    """A throw-away data directory with the real KML processed into ``processed/``."""
    if not SOURCE_KML.exists():
        pytest.skip("Source KML 'Akhil Copy.kml' not present")
    root = tmp_path_factory.mktemp("data")
    process_kml(SOURCE_KML, root / "processed", CONFIG, backup_path=root / "source" / "original_backup.kml")
    return root


@pytest.fixture(scope="session")
def processed_dir(data_dir) -> Path:
    return data_dir / "processed"


@pytest.fixture(scope="session")
def analysis(processed_dir) -> dict:
    import json

    return json.loads((processed_dir / "analysis.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def hubs(processed_dir) -> list[dict]:
    import json

    return json.loads((processed_dir / "hubs.json").read_text(encoding="utf-8"))["hubs"]


@pytest.fixture(scope="session")
def clusters(processed_dir) -> list[dict]:
    import json

    return json.loads((processed_dir / "clusters.json").read_text(encoding="utf-8"))["clusters"]


@pytest.fixture(scope="session")
def store(processed_dir):
    from app.services.data_store import DataStore

    s = DataStore(processed_dir)
    s.load()
    assert s.ready
    return s


def _osrm_reachable() -> bool:
    if os.environ.get("SKIP_LIVE"):
        return False
    try:
        r = httpx.get(
            "https://router.project-osrm.org/route/v1/driving/78.3762,17.447;78.3489,17.4401?overview=false",
            timeout=15, headers={"User-Agent": "SmartHubFinder-tests"},
        )
        return r.status_code == 200 and r.json().get("code") == "Ok"
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="session")
def live_routing_available() -> bool:
    return _osrm_reachable()


@pytest.fixture
def require_live(live_routing_available):
    if not live_routing_available:
        pytest.skip("Routing provider not reachable (offline or SKIP_LIVE set)")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(database_path=tmp_path / "test.db", google_maps_api_key=None, ors_api_key=None, routing_provider="auto")
