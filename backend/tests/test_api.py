"""API tests through FastAPI's TestClient, with routing served by the mock OSRM server."""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from .conftest import SOURCE_KML
from .test_routing import MockOsrm, make_service


@pytest.fixture(scope="module")
def client(data_dir, tmp_path_factory, monkeypatch_module):
    exports = tmp_path_factory.mktemp("exports")
    monkeypatch_module.setenv("DATA_DIR", str(data_dir))
    monkeypatch_module.setenv("DATABASE_PATH", str(data_dir / "api_test.db"))
    monkeypatch_module.setenv("EXPORTS_DIR", str(exports))
    monkeypatch_module.setenv("GOOGLE_MAPS_API_KEY", "")
    monkeypatch_module.setenv("ORS_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        app.state.routing = make_service(app.state.settings, MockOsrm())
        yield c
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_health(client):
    r = client.get("/api/health").json()
    assert r["dataset_ready"] and r["hubs"] == 361 and r["clusters"] == 26
    assert r["routing"]["active"] == "osrm"
    google = next(p for p in r["routing"]["providers"] if p["name"] == "google")
    assert google["configured"] is False
    assert r["deployment"] == {"platform": "local", "read_only_dataset": False, "persistent_storage": True,
                               "max_upload_mb": 60.0}


def test_stateless_exports_from_posted_result(client):
    """Exports built from a posted result need no server-side memory (serverless-safe)."""
    res = client.post("/api/nearest-hub", json={"latitude": 17.4849, "longitude": 78.4138, "save_history": False}).json()
    client.app.state.results.clear()  # simulate a different serverless instance
    assert client.get("/api/export/kml", params={"type": "route", "result_id": res["result_id"]}).status_code == 404

    kml = client.post("/api/export/kml", params={"type": "route"}, json=res)
    assert kml.status_code == 200 and b"<LineString>" in kml.content
    assert "nearest_hub_route.kml" in kml.headers["content-disposition"]
    demo = client.post("/api/export/kml", params={"type": "company_demo"}, json=res)
    assert demo.status_code == 200 and b"Nearest hub search" in demo.content
    csv = client.post("/api/export/csv", json=res)
    assert csv.status_code == 200 and "road_distance_km" in csv.text
    gj = client.post("/api/export/geojson", json=res).json()
    assert len(gj["features"][0]["geometry"]["coordinates"]) == res["route"]["point_count"]

    # Alternative hub: the client swaps in that hub's ranking row and route
    alt_row = res["ranking"][2]
    alt = client.post("/api/route", json={"origin_latitude": 17.4849, "origin_longitude": 78.4138,
                                          "hub_id": alt_row["hub_id"]}).json()
    alt_kml = client.post("/api/export/kml", params={"type": "route"},
                          json={**res, "nearest": alt_row, "route": alt["route"]})
    assert f"Nearest hub: {alt_row['display_name']}".encode() in alt_kml.content

    assert client.post("/api/export/kml", params={"type": "route"}, json={"bogus": 1}).status_code == 422


def test_responses_are_gzip_compressed(client):
    r = client.get("/api/export/kml", params={"type": "all_hubs"}, headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_hubs_and_search(client):
    r = client.get("/api/hubs", params={"limit": 5000}).json()
    assert r["total"] == 361
    r = client.get("/api/hubs", params={"q": "lanco"}).json()
    assert [h["name"] for h in r["hubs"]] == ["lanco_hills"]
    r = client.get("/api/hubs", params={"cluster_id": "kondapur"}).json()
    assert r["total"] == 28
    r = client.get("/api/hubs", params={"active": False}).json()
    assert r["total"] == 13


def test_clusters_endpoints(client):
    r = client.get("/api/clusters").json()
    assert r["count"] == 26 and r["clusters"][0]["boundary"]["type"] in ("Polygon", "MultiPolygon")
    r = client.get("/api/clusters/kondapur").json()
    assert r["cluster"]["hub_count"] == 28 and len(r["hubs"]) == 28
    r = client.get("/api/clusters/kondapur/hubs").json()
    assert r["total"] == 28
    assert client.get("/api/clusters/nope").status_code == 404


def test_analytics_overview(client):
    r = client.get("/api/analytics/overview").json()
    t = r["totals"]
    assert (t["hubs"], t["clusters"], t["valid_locations"], t["unassigned_hubs"]) == (361, 26, 361, 0)
    assert sum(c["hub_count"] for c in r["hubs_per_cluster"]) == 361
    assert any(m["field"] == "hub_type" and m["missing"] == 361 for m in r["missing_data"])


@pytest.mark.parametrize("body,field", [
    ({"latitude": 95, "longitude": 78.4}, "latitude"),
    ({"latitude": 17.4, "longitude": -181}, "longitude"),
    ({"latitude": "abc", "longitude": 78.4}, "latitude"),
    ({"longitude": 78.4}, "latitude"),
])
def test_nearest_hub_validation(client, body, field):
    r = client.post("/api/nearest-hub", json=body)
    assert r.status_code == 422
    assert any(e["field"] == field for e in r.json()["errors"])


def test_nearest_hub_history_and_exports(client):
    client.delete("/api/history")
    r = client.post("/api/nearest-hub", json={"latitude": 17.4849, "longitude": 78.4138, "source": "manual"})
    assert r.status_code == 200
    res = r.json()
    assert res["status"] == "ok" and res["nearest"]["cluster_id"] == "kukatpally"
    assert res["history_id"] is not None

    gps = client.post("/api/nearest-hub", json={"latitude": 17.4849, "longitude": 78.4138, "source": "gps"}).json()
    assert gps.get("history_id") is None, "GPS searches must not be stored without consent"

    hist = client.get("/api/history").json()
    assert hist["total"] == 1 and hist["records"][0]["source"] == "manual"

    rid = res["result_id"]
    kml = client.get("/api/export/kml", params={"type": "route", "result_id": rid})
    assert kml.status_code == 200 and kml.headers["content-type"].startswith("application/vnd.google-earth.kml+xml")
    root = etree.fromstring(kml.content)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    coords = root.find(".//k:LineString/k:coordinates", ns).text.split()
    assert len(coords) == res["route"]["point_count"] > 2

    alt = res["ranking"][2]["hub_id"]
    rr = client.post("/api/route", json={"origin_latitude": 17.4849, "origin_longitude": 78.4138, "hub_id": alt,
                                        "result_id": rid})
    assert rr.status_code == 200
    alt_kml = client.get("/api/export/kml", params={"type": "route", "result_id": rid, "hub_id": alt})
    assert alt_kml.status_code == 200
    assert f"Nearest hub: {res['ranking'][2]['display_name']}".encode() in alt_kml.content

    csv = client.get("/api/export/csv", params={"type": "search", "result_id": rid}).text
    assert "road_distance_km" in csv and "straight_line_km is the pre-filter distance only" in csv
    assert client.get("/api/export/geojson", params={"type": "route", "result_id": rid}).json()["features"]

    gen = client.post("/api/export/generate-files", params={"result_id": rid}).json()
    assert all(f["written"] for f in gen["files"]), gen

    rec = client.get(f"/api/history/{hist['records'][0]['id']}").json()
    assert rec["result"]["result_id"] == rid
    assert client.delete("/api/history").json()["deleted"] == 1


@pytest.mark.parametrize("kind", ["all_hubs", "all_clusters", "company_demo", "cleaned"])
def test_static_kml_exports_are_well_formed(client, kind):
    r = client.get("/api/export/kml", params={"type": kind})
    assert r.status_code == 200
    root = etree.fromstring(r.content)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    assert len(root.findall(".//k:Placemark", ns)) >= 361


def test_selected_cluster_requires_valid_id(client):
    assert client.get("/api/export/kml", params={"type": "selected_cluster"}).status_code == 422
    r = client.get("/api/export/kml", params={"type": "selected_cluster", "cluster_id": "kondapur"})
    assert r.status_code == 200 and b"Kondapur" in r.content


def test_route_export_needs_search(client):
    assert client.get("/api/export/kml", params={"type": "route"}).status_code == 422
    assert client.get("/api/export/kml", params={"type": "route", "result_id": "missing"}).status_code == 404


def test_csv_exports(client):
    hubs = client.get("/api/export/csv", params={"type": "hubs"}).text.lstrip("﻿").splitlines()
    assert len(hubs) == 362 and hubs[0].startswith("hub_id,name")
    clusters = client.get("/api/export/csv", params={"type": "clusters"}).text.lstrip("﻿").splitlines()
    assert len(clusters) == 27


def test_settings_roundtrip(client):
    r = client.put("/api/settings", json={"search_radius_km": 9.5, "ranking": "duration"}).json()
    assert r["preferences"]["search_radius_km"] == 9.5 and r["preferences"]["ranking"] == "duration"
    assert client.put("/api/settings", json={"travel_mode": "rocket"}).status_code == 422
    r = client.delete("/api/settings").json()
    assert r["preferences"]["search_radius_km"] == 15.0


def test_import_preview_does_not_replace_dataset(client):
    data = SOURCE_KML.read_bytes()
    r = client.post("/api/import-kml", files={"file": ("Akhil Copy.kml", data, "application/vnd.google-earth.kml+xml")},
                    data={"activate": "false"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["activated"] is False
    assert body["summary"]["hubs"] == 361 and body["summary"]["repairs"] == 361
    assert body["summary"]["coordinates_unchanged"] is True
    assert client.post("/api/import-kml", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 422


def test_backup_is_byte_identical(data_dir):
    backup = data_dir / "source" / "original_backup.kml"
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == hashlib.sha256(SOURCE_KML.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def kml_schema():
    from app.config import PROJECT_ROOT
    from scripts.validate_kml import load_schema

    try:
        return load_schema(PROJECT_ROOT / "data" / "schemas")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"OGC KML schema unavailable: {exc}")


@pytest.mark.parametrize("kind", ["all_hubs", "all_clusters", "selected_cluster", "company_demo", "route"])
def test_exports_validate_against_ogc_kml_schema(client, kml_schema, kind):
    from lxml import etree as ET

    params = {"type": kind, "cluster_id": "kondapur", "include_service_areas": True}
    if kind in ("route", "company_demo"):
        res = client.post("/api/nearest-hub", json={"latitude": 17.46, "longitude": 78.36, "save_history": False}).json()
        params["result_id"] = res["result_id"]
    r = client.get("/api/export/kml", params=params)
    assert r.status_code == 200
    doc = ET.fromstring(r.content).getroottree()
    assert kml_schema.validate(doc), [e.message for e in kml_schema.error_log][:5]
