"""Routing + nearest-hub tests.

Offline tests drive the real algorithm against a mock OSRM server (httpx
MockTransport) with deterministic road distances. Tests marked ``live`` call
the real routing provider.
"""

from __future__ import annotations

import asyncio
import json
import math

import httpx
import pytest

from app.services.geo_utils import encode_polyline, haversine_km
from app.services.nearest_hub_service import SearchOptions, find_nearest_hub, route_to_hub
from app.services.routing_service import RoutingService, osrm_instruction

ROAD_FACTOR = 1.35  # mock road network: road distance = 1.35 x great-circle


def run(coro):
    return asyncio.run(coro)


def run_live(settings, fn):
    """Create, use and close a real RoutingService inside one event loop."""

    async def go():
        svc = RoutingService(settings)
        try:
            return await fn(svc)
        finally:
            await svc.aclose()

    return asyncio.run(go())


class MockOsrm:
    """Minimal OSRM HTTP API: /table and /route with configurable failures."""

    def __init__(self, unreachable: set[tuple[float, float]] | None = None, far_snap: set[tuple[float, float]] | None = None,
                 fail_table: bool = False, fail_route: bool = False):
        self.unreachable = unreachable or set()
        self.far_snap = far_snap or set()
        self.fail_table = fail_table
        self.fail_route = fail_route
        self.table_calls = 0
        self.route_calls = 0
        self.destinations_evaluated = 0

    @staticmethod
    def _coords(path: str) -> list[tuple[float, float]]:
        part = path.split("/driving/")[1]
        return [(float(lat), float(lng)) for lng, lat in (c.split(",") for c in part.split(";"))]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        coords = self._coords(path)
        if "/table/" in path:
            self.table_calls += 1
            if self.fail_table:
                return httpx.Response(503, text="overloaded")
            dests = [int(i) for i in request.url.params["destinations"].split(";")]
            o = coords[0]
            dist, dur, meta = [], [], []
            for j in dests:
                d = coords[j]
                key = (round(d[0], 6), round(d[1], 6))
                self.destinations_evaluated += 1
                if key in self.unreachable:
                    dist.append(None)
                    dur.append(None)
                else:
                    m = haversine_km(*o, *d) * 1000 * ROAD_FACTOR
                    dist.append(m)
                    dur.append(m / 8.0)
                meta.append({"location": [d[1], d[0]], "distance": 1500.0 if key in self.far_snap else 12.0})
            return httpx.Response(200, json={
                "code": "Ok", "distances": [dist], "durations": [dur],
                "sources": [{"location": [o[1], o[0]], "distance": 5.0}], "destinations": meta,
            })
        if "/route/" in path:
            self.route_calls += 1
            if self.fail_route:
                return httpx.Response(500, text="boom")
            a, b = coords
            pts = [(a[0] + (b[0] - a[0]) * t / 20, a[1] + (b[1] - a[1]) * t / 20 + 0.0004 * math.sin(t)) for t in range(21)]
            m = haversine_km(*a, *b) * 1000 * ROAD_FACTOR
            route = {
                "distance": m, "duration": m / 8.0, "geometry": encode_polyline(pts, 6),
                "legs": [{"summary": "Mock Road", "steps": [
                    {"maneuver": {"type": "depart", "bearing_after": 90, "location": [a[1], a[0]]}, "name": "Mock Road",
                     "distance": m, "duration": m / 8},
                    {"maneuver": {"type": "arrive", "modifier": "left", "location": [b[1], b[0]]}, "name": "",
                     "distance": 0, "duration": 0},
                ]}],
            }
            return httpx.Response(200, json={
                "code": "Ok", "routes": [route, {**route, "distance": m * 1.2, "duration": m / 7}],
                "waypoints": [{"location": [a[1], a[0]], "distance": 5.0}, {"location": [b[1], b[0]], "distance": 12.0}],
            })
        return httpx.Response(404)



def make_service(settings, mock: MockOsrm) -> RoutingService:
    client = httpx.AsyncClient(transport=httpx.MockTransport(mock.handler))
    return RoutingService(settings, client=client)


def expected_order(store, lat, lng, hubs):
    return sorted(hubs, key=lambda h: haversine_km(lat, lng, h["latitude"], h["longitude"]))


# ---------------------------------------------------------------------------
# Offline: algorithm behaviour
# ---------------------------------------------------------------------------

def test_exhaustive_search_ranks_by_road_distance(store, settings):
    mock = MockOsrm()
    svc = make_service(settings, mock)
    r = run(find_nearest_hub(SearchOptions(latitude=17.412498, longitude=78.411452), store, svc))
    assert r["status"] == "ok"
    assert r["location"]["cluster_id"] == "shaikpet"
    ev = r["evaluation"]
    shaikpet_live = [h for h in store.hubs if h["cluster_id"] == "shaikpet" and h["is_active"]]
    assert ev["strategy"] == "exhaustive" and ev["guaranteed"]
    assert ev["candidates_evaluated"] == len(shaikpet_live) == mock.destinations_evaluated
    dists = [h["road_distance_m"] for h in r["ranking"]]
    assert dists == sorted(dists) and len(r["ranking"]) == 5
    assert all(h["cluster_id"] == "shaikpet" for h in r["ranking"])
    # road distances come from the routing engine, never from haversine directly
    for h in r["ranking"]:
        # straight_line_km is rounded to the metre, so allow ~1 m of rounding
        assert h["road_distance_m"] == pytest.approx(h["straight_line_km"] * 1000 * ROAD_FACTOR, abs=1.5)


def test_route_geometry_has_intermediate_points_and_steps(store, settings):
    svc = make_service(settings, MockOsrm())
    r = run(find_nearest_hub(SearchOptions(latitude=17.412498, longitude=78.411452), store, svc))
    route = r["route"]
    assert r["route_status"] == "available"
    assert route["point_count"] == 21 > 2
    assert route["steps"][0]["instruction"].startswith("Head east")
    assert len(route["alternatives"]) == 1
    assert r["links"]["google_maps"].startswith("https://www.google.com/maps/dir/?api=1")


def test_unreachable_and_far_snapped_hubs_are_excluded(store, settings):
    lat, lng = 17.412498, 78.411452
    shaikpet = [h for h in store.hubs if h["cluster_id"] == "shaikpet" and h["is_active"]]
    order = expected_order(store, lat, lng, shaikpet)
    blocked = (round(order[0]["latitude"], 6), round(order[0]["longitude"], 6))
    far = (round(order[1]["latitude"], 6), round(order[1]["longitude"], 6))
    svc = make_service(settings, MockOsrm(unreachable={blocked}, far_snap={far}))
    r = run(find_nearest_hub(SearchOptions(latitude=lat, longitude=lng), store, svc))
    ids = [h["hub_id"] for h in r["ranking"]]
    assert order[0]["hub_id"] not in ids and order[1]["hub_id"] not in ids
    reasons = {u["hub_id"]: u["reason"] for u in r["unreachable"]}
    assert "No road route" in reasons[order[0]["hub_id"]]
    assert "nearest routable road" in reasons[order[1]["hub_id"]]
    assert r["nearest"]["hub_id"] == order[2]["hub_id"]


def test_provider_failure_is_reported_honestly(store, settings):
    svc = make_service(settings, MockOsrm(fail_table=True))
    r = run(find_nearest_hub(SearchOptions(latitude=17.412498, longitude=78.411452), store, svc))
    assert r["status"] == "routing_unavailable"
    assert r["nearest"] is None and r["route"] is None and r["ranking"] == []
    assert r["route_error"]["code"] == "provider_error"
    assert "NOT road distance" in r["candidates_preview"]["label"]


def test_route_failure_keeps_ranking_but_no_fake_route(store, settings):
    svc = make_service(settings, MockOsrm(fail_route=True))
    r = run(find_nearest_hub(SearchOptions(latitude=17.412498, longitude=78.411452), store, svc))
    assert r["status"] == "ok" and r["nearest"] is not None
    assert r["route"] is None and r["route_status"] == "unavailable"


def test_progressive_bounded_search_matches_exhaustive(store, settings):
    lat, lng = 17.44, 78.38
    exhaustive_mock = MockOsrm()
    full = run(find_nearest_hub(SearchOptions(latitude=lat, longitude=lng, cluster_id="all", exhaustive_threshold=1000,
                                              max_candidates=1000), store, make_service(settings, exhaustive_mock)))
    prog_mock = MockOsrm()
    prog = run(find_nearest_hub(SearchOptions(latitude=lat, longitude=lng, cluster_id="all", exhaustive_threshold=10,
                                              max_candidates=300), store, make_service(settings, prog_mock)))
    assert full["evaluation"]["strategy"] == "exhaustive"
    assert prog["evaluation"]["strategy"] == "progressive (bounded)"
    assert prog["evaluation"]["guaranteed"] is True
    assert prog_mock.destinations_evaluated < exhaustive_mock.destinations_evaluated
    assert [h["hub_id"] for h in prog["ranking"]] == [h["hub_id"] for h in full["ranking"]]


def test_capped_search_is_flagged_not_guaranteed(store, settings):
    r = run(find_nearest_hub(SearchOptions(latitude=17.2403, longitude=78.4294, cluster_id="all", max_radius_km=40,
                                           exhaustive_threshold=10, max_candidates=12), store,
                             make_service(settings, MockOsrm())))
    assert r["evaluation"]["strategy"] == "progressive (capped)"
    assert r["evaluation"]["guaranteed"] is False
    assert "cannot be ruled out" in r["evaluation"]["explanation"]


def test_outside_coverage_falls_back_to_all_clusters(store, settings):
    r = run(find_nearest_hub(SearchOptions(latitude=17.2403, longitude=78.4294), store, make_service(settings, MockOsrm())))
    assert r["scope"]["fallback"] is True and r["scope"]["cluster_ids"] is None
    assert r["location"]["detection"] == "outside_coverage"


def test_live_only_excludes_inactive_hubs(store, settings):
    inactive = next(h for h in store.hubs if h["is_active"] is False)
    lat, lng = inactive["latitude"], inactive["longitude"]
    svc = make_service(settings, MockOsrm())
    with_inactive = run(find_nearest_hub(SearchOptions(latitude=lat, longitude=lng, live_only=False), store, svc))
    live_only = run(find_nearest_hub(SearchOptions(latitude=lat, longitude=lng, live_only=True), store, svc))
    assert with_inactive["nearest"]["hub_id"] == inactive["hub_id"]
    assert inactive["hub_id"] not in [h["hub_id"] for h in live_only["ranking"]]
    assert live_only["evaluation"]["excluded_inactive"] >= 1


def test_no_hubs_in_radius(store, settings):
    r = run(find_nearest_hub(SearchOptions(latitude=16.5, longitude=80.6, max_radius_km=10), store,
                             make_service(settings, MockOsrm())))
    assert r["status"] == "no_hubs_in_radius"
    assert "straight line" in r["message"]


def test_unsupported_mode_and_missing_key(store, settings):
    svc = make_service(settings, MockOsrm())
    r = run(find_nearest_hub(SearchOptions(latitude=17.41, longitude=78.41, travel_mode="two_wheeler"), store, svc))
    assert r["status"] == "routing_unavailable" and r["route_error"]["code"] == "unsupported_mode"
    r = run(find_nearest_hub(SearchOptions(latitude=17.41, longitude=78.41, provider="google"), store, svc))
    assert r["status"] == "routing_unavailable" and r["route_error"]["code"] == "not_configured"


def test_route_to_alternative_hub(store, settings):
    hub = store.hubs[5]
    out = run(route_to_hub(store, make_service(settings, MockOsrm()), (17.41, 78.41), hub["hub_id"], None, "driving",
                           None, True))
    assert out["hub"]["hub_id"] == hub["hub_id"]
    assert out["route"]["point_count"] > 2


def test_osrm_instruction_text():
    assert osrm_instruction({"maneuver": {"type": "turn", "modifier": "left"}, "name": "MG Road"}) == "Turn left onto MG Road"
    assert osrm_instruction({"maneuver": {"type": "roundabout", "exit": 2}, "name": ""}) == "Enter the roundabout and take the 2nd exit"
    assert osrm_instruction({"maneuver": {"type": "arrive", "modifier": "right"}}) == "Arrive at the destination on the right"


def test_google_provider_parsing(settings):
    from app.services.routing_service import GoogleRoutesProvider

    settings.google_maps_api_key = "test-key"
    pts = [(17.41, 78.41), (17.415, 78.412), (17.42, 78.415)]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["X-Goog-Api-Key"] == "test-key"
        body = json.loads(req.content)
        if "computeRouteMatrix" in str(req.url):
            return httpx.Response(200, json=[
                {"originIndex": 0, "destinationIndex": 0, "distanceMeters": 1200, "duration": "180s", "condition": "ROUTE_EXISTS"},
                {"originIndex": 0, "destinationIndex": 1, "condition": "ROUTE_NOT_FOUND"},
            ])
        assert body["travelMode"] == "TWO_WHEELER"
        return httpx.Response(200, json={"routes": [{
            "distanceMeters": 1500, "duration": "240s", "polyline": {"encodedPolyline": encode_polyline(pts)},
            "legs": [{"steps": [{"distanceMeters": 1500, "staticDuration": "240s",
                                 "navigationInstruction": {"maneuver": "TURN_LEFT", "instructions": "Turn left onto Road 1"},
                                 "startLocation": {"latLng": {"latitude": 17.41, "longitude": 78.41}}}]}],
        }]})

    p = GoogleRoutesProvider(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    m = run(p.matrix((17.4, 78.4), [(17.41, 78.41), (17.5, 78.5)], "two_wheeler"))
    assert m.cells[0].distance_m == 1200 and m.cells[0].duration_s == 180
    assert m.cells[1].status == "no_route"
    r = run(p.route((17.41, 78.41), (17.42, 78.415), "two_wheeler"))
    assert r.distance_m == 1500 and len(r.geometry) == 3 and r.steps[0].instruction == "Turn left onto Road 1"


# ---------------------------------------------------------------------------
# Live: real road network
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_live_osrm_nearest_hub_known_location(store, settings, require_live):
    r = run_live(settings, lambda svc: find_nearest_hub(SearchOptions(latitude=17.412498, longitude=78.411452), store, svc))
    assert r["status"] == "ok", r["message"]
    assert r["provider"]["name"] == "osrm"
    assert r["evaluation"]["guaranteed"]
    assert r["route"]["point_count"] > 2
    # A road route is at least as long as the straight line between its snapped end points
    for h in r["ranking"]:
        assert h["road_distance_m"] >= h["straight_line_km"] * 1000 - 100
    dists = [h["road_distance_m"] for h in r["ranking"]]
    assert dists == sorted(dists)


@pytest.mark.live
@pytest.mark.parametrize("idx", [0, 100, 200])
def test_live_search_from_a_hub_finds_that_hub(store, settings, require_live, idx):
    hubs = [h for h in store.hubs if h["is_active"]]
    h = hubs[idx]
    r = run_live(settings, lambda svc: find_nearest_hub(
        SearchOptions(latitude=h["latitude"], longitude=h["longitude"]), store, svc))
    assert r["status"] == "ok"
    assert r["nearest"]["hub_id"] == h["hub_id"], (h["name"], r["nearest"]["name"])
    assert r["nearest"]["road_distance_m"] < 300


@pytest.mark.live
def test_live_route_polyline_follows_roads(settings, require_live):
    route = run_live(settings, lambda svc: svc.resolve("osrm").route((17.4474, 78.3762), (17.4401, 78.3489), "driving"))
    assert len(route.geometry) > 50, "a 3+ km urban road route must contain many intermediate points"
    straight = haversine_km(17.4474, 78.3762, 17.4401, 78.3489) * 1000
    assert route.distance_m > straight
    assert route.steps and route.steps[-1].instruction.startswith("Arrive")


@pytest.mark.live
def test_live_matrix_handles_unroutable_destination(settings, require_live):
    # Second destination is in the Bay of Bengal: OSRM snaps it very far away.
    m = run_live(settings, lambda svc: svc.resolve("osrm").matrix(
        (17.4474, 78.3762), [(17.4401, 78.3489), (15.0, 85.0)], "driving"))
    assert m.cells[0].status == "ok"
    assert m.cells[1].status != "ok" or (m.cells[1].snap_distance_m or 0) > 10_000
