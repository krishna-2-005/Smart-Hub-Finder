"""Unit tests: geodesic helpers, polyline codec, DBSCAN fallback, location detection."""

from __future__ import annotations

import math

import pytest

from app.services.cluster_service import cluster_key, dbscan_haversine
from app.services.geo_utils import decode_polyline, encode_polyline, haversine_km, validate_lat_lng
from app.services.location_service import detect_location


def test_haversine_known_distance():
    # Charminar -> Golconda Fort is ~8.3 km great-circle
    d = haversine_km(17.3616, 78.4747, 17.3833, 78.4011)
    assert 8.0 < d < 8.6
    assert haversine_km(17.4, 78.4, 17.4, 78.4) == 0


@pytest.mark.parametrize(
    "lat,lng,ok",
    [(17.4, 78.4, True), (-33.9, 151.2, True), (90, 180, True), (-90, -180, True),
     (91, 0, False), (0, 181, False), ("abc", 0, False), (None, 0, False), ("", 0, False), (math.nan, 0, False)],
)
def test_validate_lat_lng(lat, lng, ok):
    assert (validate_lat_lng(lat, lng) == []) is ok


def test_polyline_roundtrip_precision_5_and_6():
    pts = [(17.412498, 78.411452), (17.41301, 78.41207), (17.413467, 78.412724)]
    for precision in (5, 6):
        decoded = decode_polyline(encode_polyline(pts, precision), precision)
        assert len(decoded) == len(pts)
        for (a, b), (c, d) in zip(pts, decoded):
            assert abs(a - c) < 10 ** -precision and abs(b - d) < 10 ** -precision
    # Google's documented example
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]


def test_cluster_key_normalisation():
    assert cluster_key("Hitech_City") == cluster_key("hitech_city") == cluster_key("Hitech_City_Cluster")
    assert cluster_key("Rajendranagar_cluster") == cluster_key("Rajendra_Nagar")
    assert cluster_key("Bachupally Cluster") == cluster_key("bachupally")
    assert cluster_key("Kondapur") != cluster_key("Kokapet")


def test_dbscan_haversine_separates_groups_and_noise():
    a = [(17.40 + i * 0.002, 78.40) for i in range(5)]      # ~220 m apart
    b = [(17.50 + i * 0.002, 78.50) for i in range(4)]
    noise = [(17.80, 78.90)]
    labels = dbscan_haversine(a + b + noise, eps_km=0.5, min_samples=3)
    assert len(set(labels[:5])) == 1 and labels[0] >= 0
    assert len(set(labels[5:9])) == 1 and labels[5] >= 0 and labels[5] != labels[0]
    assert labels[9] == -1


def test_dbscan_fallback_used_when_no_cluster_data():
    from app.services.cluster_service import build_clusters
    from app.services.hub_classifier import HubRecord

    def hub(i, lat, lng):
        return HubRecord(hub_id=f"h{i}", name=f"h{i}", display_name=None, hub_code=None, latitude=lat, longitude=lng,
                         location_method="point_geometry", cluster_raw=None)

    hubs = [hub(i, 17.40 + i * 0.002, 78.40) for i in range(4)] + [hub(10 + i, 17.6 + i * 0.002, 78.6) for i in range(3)]
    clusters, notes = build_clusters(hubs, [], {"clustering_fallback": {"eps_km": 1.0, "min_samples": 2}})
    assert "DBSCAN" in notes["method"]
    assert sorted(c.hub_count for c in clusters) == [3, 4]
    assert all(c.inferred for c in clusters)
    assert all(h.cluster_source == "dbscan (inferred)" for h in hubs)


def test_detect_location_inside_cluster(store):
    loc = detect_location(store, 17.412498, 78.411452)
    assert loc["detection"] == "inside_cluster_boundary"
    assert loc["cluster_id"] == "shaikpet"
    assert loc["within_coverage"]


def test_detect_location_outside_coverage(store):
    loc = detect_location(store, 17.2403, 78.4294)  # airport, south of the network
    assert loc["detection"] == "outside_coverage"
    assert loc["cluster_id"] is None
    assert loc["nearest_cluster"]["straight_line_km"] > 1


def test_every_hub_point_is_detected_somewhere(store):
    """Hub points lie inside their own service area, so detection must never report 'outside' for them."""
    for h in store.hubs:
        loc = detect_location(store, h["latitude"], h["longitude"])
        assert loc["detection"] != "outside_coverage", h["name"]
