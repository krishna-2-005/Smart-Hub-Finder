"""Nearest-hub search by real road distance (or road travel time).

Algorithm
---------
1. Detect the user's cluster (or use the one selected / all clusters).
2. Filter eligible hubs (scope, operational status).
3. Haversine pre-filter: drop hubs beyond the search radius and sort the rest
   by straight-line distance. Haversine is never reported as road distance.
4. Road evaluation through the routing provider's matrix endpoint:
   * ``exhaustive``  - every candidate is evaluated when there are few enough
     (default <= 50; every single cluster in the source data qualifies).
   * ``progressive`` - candidates are evaluated in straight-line order in
     batches. Because a road route can never be shorter than the great-circle
     distance between its (road-snapped) end points, a candidate whose lower
     bound ``haversine - origin_snap - max_hub_snap`` already exceeds the
     current k-th best road value cannot enter the top k, so evaluation stops
     with a proof. If the candidate cap is hit first, the result is reported
     as *not guaranteed*.
5. Rank reachable hubs, fetch the full road geometry + turn-by-turn steps for
   the winner, and return the top N.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .data_store import DataStore
from .geo_utils import google_earth_web_url, google_maps_directions_url, haversine_km
from .location_service import detect_location
from .routing_service import MatrixCell, RoutingError, RoutingService

log = logging.getLogger(__name__)

# Upper speed bounds used only to derive a travel-time lower bound for pruning.
VMAX_KMH = {"driving": 130.0, "two_wheeler": 110.0, "cycling": 45.0, "walking": 10.0}
PROGRESSIVE_BATCH = 25


class SearchInputError(ValueError):
    pass


@dataclass
class SearchOptions:
    latitude: float
    longitude: float
    cluster_id: str = "auto"
    travel_mode: str = "driving"
    ranking: str = "distance"  # distance | duration
    max_radius_km: float = 15.0
    max_candidates: int = 60
    exhaustive_threshold: int = 50
    top_n: int = 5
    live_only: bool = True
    max_snap_distance_m: float = 1000.0
    provider: str | None = None
    alternatives: bool = True
    source: str = "manual"


class ResultCache:
    """Short-lived in-memory store of recent results (for exports); never written to disk."""

    def __init__(self, max_items: int = 200):
        self.max = max_items
        self._d: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def put(self, result: dict[str, Any]) -> None:
        self._d[result["result_id"]] = result
        self._d.move_to_end(result["result_id"])
        while len(self._d) > self.max:
            self._d.popitem(last=False)

    def get(self, result_id: str) -> dict[str, Any] | None:
        return self._d.get(result_id)

    def latest(self) -> dict[str, Any] | None:
        return next(reversed(self._d.values()), None) if self._d else None

    def clear(self) -> None:
        self._d.clear()


def _hub_row(h: dict[str, Any], straight_km: float, cell: MatrixCell | None = None, rank: int | None = None) -> dict[str, Any]:
    row = {
        "rank": rank,
        "hub_id": h.get("hub_id"),
        "name": h.get("name"),
        "display_name": h.get("display_name"),
        "cluster_id": h.get("cluster_id"),
        "cluster_name": h.get("cluster_name"),
        "status": h.get("status"),
        "latitude": h["latitude"],
        "longitude": h["longitude"],
        "location_method": h.get("location_method"),
        "straight_line_km": round(straight_km, 3),
        "road_distance_m": None,
        "road_distance_km": None,
        "duration_s": None,
        "duration_min": None,
        "snap_distance_m": None,
    }
    if cell is not None:
        row["snap_distance_m"] = round(cell.snap_distance_m, 1) if cell.snap_distance_m is not None else None
        if cell.distance_m is not None:
            row["road_distance_m"] = round(cell.distance_m, 1)
            row["road_distance_km"] = round(cell.distance_m / 1000, 3)
        if cell.duration_s is not None:
            row["duration_s"] = round(cell.duration_s, 1)
            row["duration_min"] = round(cell.duration_s / 60, 1)
    return row


async def find_nearest_hub(opts: SearchOptions, store: DataStore, routing: RoutingService) -> dict[str, Any]:
    t0 = time.perf_counter()
    store.require()
    lat, lng = float(opts.latitude), float(opts.longitude)
    origin = (lat, lng)
    if opts.ranking not in ("distance", "duration"):
        raise SearchInputError("ranking must be 'distance' or 'duration'")

    location = detect_location(store, lat, lng)
    warnings: list[str] = []

    # --- 1. scope -------------------------------------------------------------------
    sel = (opts.cluster_id or "auto").strip()
    fallback = False
    if sel == "auto":
        if location["cluster_id"]:
            scope_ids: set[str] | None = {location["cluster_id"]}
            scope_desc = f"Auto-detected cluster: {store.clusters_by_id[location['cluster_id']]['display_name']}"
        else:
            scope_ids = None
            fallback = True
            nc = location.get("nearest_cluster")
            scope_desc = (
                "Fallback: the location is outside every cluster boundary, so hubs in ALL clusters within the "
                "search radius are evaluated"
                + (f" (nearest cluster boundary: {nc['display_name']}, {nc['straight_line_km']:.1f} km straight-line)"
                   if nc else "")
            )
    elif sel == "all":
        scope_ids = None
        scope_desc = "All clusters"
    else:
        if sel not in store.clusters_by_id:
            raise SearchInputError(f"Unknown cluster '{sel}'")
        scope_ids = {sel}
        scope_desc = f"Selected cluster: {store.clusters_by_id[sel]['display_name']}"
        if location["cluster_id"] and location["cluster_id"] != sel:
            warnings.append(
                f"The location lies inside the {location['cluster_name']} cluster, but the search is restricted to "
                f"the selected cluster {store.clusters_by_id[sel]['name']}."
            )

    in_scope = [h for h in store.hubs if h.get("latitude") is not None
                and (scope_ids is None or h.get("cluster_id") in scope_ids)]
    eligible = [h for h in in_scope if not (opts.live_only and h.get("is_active") is False)]
    excluded_inactive = len(in_scope) - len(eligible)

    with_dist = sorted(
        ((haversine_km(lat, lng, h["latitude"], h["longitude"]), h) for h in eligible), key=lambda x: x[0]
    )
    within = [(d, h) for d, h in with_dist if d <= opts.max_radius_km]

    result: dict[str, Any] = {
        "result_id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "ok",
        "message": "",
        "query": {
            "latitude": lat, "longitude": lng, "cluster_selection": sel, "travel_mode": opts.travel_mode,
            "ranking": opts.ranking, "max_radius_km": opts.max_radius_km, "max_candidates": opts.max_candidates,
            "live_only": opts.live_only, "top_n": opts.top_n, "source": opts.source,
        },
        "location": location,
        "scope": {
            "selection": sel,
            "cluster_ids": sorted(scope_ids) if scope_ids else None,
            "description": scope_desc,
            "fallback": fallback,
        },
        "provider": None,
        "evaluation": {
            "candidates_in_scope": len(in_scope),
            "excluded_inactive": excluded_inactive,
            "eligible": len(eligible),
            "candidates_within_radius": len(within),
            "candidates_evaluated": 0,
            "matrix_requests": 0,
            "strategy": None,
            "guaranteed": False,
            "explanation": "",
            "radius_note": f"The {opts.max_radius_km:g} km search radius is a straight-line pre-filter only.",
        },
        "nearest": None,
        "ranking": [],
        "unreachable": [],
        "route": None,
        "route_status": "not_available",
        "route_error": None,
        "candidates_preview": None,
        "warnings": warnings,
        "links": {},
        "timing_ms": None,
    }

    def finish(status: str, message: str) -> dict[str, Any]:
        result["status"] = status
        result["message"] = message
        result["timing_ms"] = round((time.perf_counter() - t0) * 1000)
        return result

    if not eligible:
        reason = "no hubs" if not in_scope else f"all {len(in_scope)} hubs are inactive"
        return finish("no_eligible_hubs", f"No eligible hubs in scope ({reason}).")
    if not within:
        d, h = with_dist[0]
        result["candidates_preview"] = {
            "label": "Straight-line pre-filter only — NOT road distance",
            "hubs": [_hub_row(h2, d2) for d2, h2 in with_dist[:5]],
        }
        return finish(
            "no_hubs_in_radius",
            f"No eligible hub lies within {opts.max_radius_km:g} km (straight-line). The closest eligible hub "
            f"({h.get('display_name')}) is {d:.1f} km away in a straight line; increase the search radius.",
        )

    # --- 2. road evaluation ------------------------------------------------------------
    try:
        provider = routing.resolve(opts.provider)
        provider.check_mode(opts.travel_mode)
    except RoutingError as exc:
        result["route_error"] = exc.to_dict()
        result["candidates_preview"] = {
            "label": "Straight-line pre-filter only — NOT road distance",
            "hubs": [_hub_row(h, d) for d, h in within[:5]],
        }
        return finish("routing_unavailable", exc.message)
    result["provider"] = {"name": provider.name, "label": provider.label}

    total = len(within)
    exhaustive = total <= opts.exhaustive_threshold
    cap = total if exhaustive else min(total, max(opts.max_candidates, opts.top_n))
    batch = total if exhaustive else PROGRESSIVE_BATCH
    metric_key = "distance_m" if opts.ranking == "distance" else "duration_s"
    vmax_ms = VMAX_KMH.get(opts.travel_mode, 130.0) / 3.6
    max_snap = float(opts.max_snap_distance_m)

    evaluated: list[tuple[float, dict[str, Any], MatrixCell]] = []
    origin_snap_m: float | None = None
    requests = 0
    idx = 0
    proof: str | None = None
    try:
        while idx < cap:
            chunk = within[idx : min(idx + batch, cap)]
            m = await routing.matrix(provider, origin, [(h["latitude"], h["longitude"]) for _, h in chunk],
                                     opts.travel_mode)
            requests += m.requests
            if origin_snap_m is None:
                origin_snap_m = m.origin_snap_m
            evaluated.extend((d, h, c) for (d, h), c in zip(chunk, m.cells))
            idx += len(chunk)
            if exhaustive or idx >= total:
                continue
            vals = sorted(getattr(c, metric_key) for _, _, c in evaluated
                          if c.status == "ok" and (c.snap_distance_m or 0) <= max_snap)
            if len(vals) >= opts.top_n:
                kth = vals[opts.top_n - 1]
                o_snap = origin_snap_m if origin_snap_m is not None else max_snap
                lb_m = max(0.0, within[idx][0] * 1000 - o_snap - max_snap)
                lb = lb_m if metric_key == "distance_m" else lb_m / vmax_ms
                if lb >= kth:
                    proof = (
                        f"Stopped after {idx} of {total} candidates: the next candidate's straight-line lower bound "
                        f"({lb_m / 1000:.2f} km) already exceeds the #{opts.top_n} road "
                        f"{'distance' if metric_key == 'distance_m' else 'time'}, so no unevaluated hub can rank higher."
                    )
                    break
    except RoutingError as exc:
        result["route_error"] = exc.to_dict()
        result["candidates_preview"] = {
            "label": "Straight-line pre-filter only — NOT road distance",
            "hubs": [_hub_row(h, d) for d, h in within[:5]],
        }
        result["evaluation"].update(candidates_evaluated=len(evaluated), matrix_requests=requests)
        return finish("routing_unavailable", f"Road routing failed: {exc.message}")

    ev = result["evaluation"]
    ev["candidates_evaluated"] = len(evaluated)
    ev["matrix_requests"] = requests
    ev["origin_snap_m"] = round(origin_snap_m, 1) if origin_snap_m is not None else None
    if exhaustive:
        ev["strategy"] = "exhaustive"
        ev["guaranteed"] = True
        ev["explanation"] = f"All {total} eligible hubs within the radius were evaluated by road."
    elif proof:
        ev["strategy"] = "progressive (bounded)"
        ev["guaranteed"] = True
        ev["explanation"] = proof
    elif idx >= total:
        ev["strategy"] = "progressive (complete)"
        ev["guaranteed"] = True
        ev["explanation"] = f"All {total} eligible hubs within the radius were evaluated by road."
    else:
        ev["strategy"] = "progressive (capped)"
        ev["guaranteed"] = False
        ev["explanation"] = (
            f"Only the {idx} straight-line-closest of {total} candidates were evaluated (candidate cap "
            f"{opts.max_candidates}). A closer hub by road among the remaining {total - idx} cannot be ruled out; "
            f"raise 'Maximum candidates' for a guaranteed answer."
        )

    if origin_snap_m is not None and origin_snap_m > max_snap:
        warnings.append(
            f"The location is {origin_snap_m:.0f} m from the nearest routable road; road distances are measured "
            f"from that road point."
        )

    reachable: list[tuple[float, dict[str, Any], MatrixCell]] = []
    for d, h, c in evaluated:
        if c.status != "ok":
            result["unreachable"].append({**_hub_row(h, d, c), "reason": f"No road route found by {provider.label}"})
        elif c.snap_distance_m is not None and c.snap_distance_m > max_snap:
            result["unreachable"].append({
                **_hub_row(h, d, c),
                "reason": f"Hub point is {c.snap_distance_m:.0f} m from the nearest routable road "
                          f"(limit {max_snap:.0f} m)",
            })
        else:
            reachable.append((d, h, c))

    other_key = "duration_s" if metric_key == "distance_m" else "distance_m"
    reachable.sort(key=lambda x: (getattr(x[2], metric_key), getattr(x[2], other_key) or 0))
    result["ranking"] = [_hub_row(h, d, c, rank=i + 1) for i, (d, h, c) in enumerate(reachable[: opts.top_n])]

    if not reachable:
        return finish("no_reachable_hubs",
                      f"None of the {len(evaluated)} evaluated hubs is reachable by road with {provider.label}.")

    nearest = result["ranking"][0]
    result["nearest"] = nearest
    best_road_m = reachable[0][2].distance_m or 0
    radius_lb_m = opts.max_radius_km * 1000 - (origin_snap_m if origin_snap_m is not None else max_snap) - max_snap
    ev["outside_radius_ruled_out"] = metric_key == "distance_m" and best_road_m <= radius_lb_m
    if ev["guaranteed"] and metric_key == "distance_m" and not ev["outside_radius_ruled_out"]:
        ev["explanation"] += (" Hubs beyond the radius were not evaluated; the nearest road distance exceeds what the "
                              "radius can rule out, so consider a larger radius.")

    result["links"] = {
        "google_maps": google_maps_directions_url(lat, lng, nearest["latitude"], nearest["longitude"], opts.travel_mode),
        "google_earth_destination": google_earth_web_url(nearest["latitude"], nearest["longitude"], 3000),
    }

    # --- 3. full road geometry for the winner --------------------------------------------
    try:
        route = await routing.route(provider, origin, (nearest["latitude"], nearest["longitude"]),
                                    opts.travel_mode, alternatives=opts.alternatives)
        result["route"] = route.to_dict()
        result["route"]["hub_id"] = nearest["hub_id"]
        result["route_status"] = "available"
        if nearest["road_distance_m"] and abs(route.distance_m - nearest["road_distance_m"]) > max(
                50.0, 0.02 * nearest["road_distance_m"]):
            warnings.append(
                f"The matrix road distance ({nearest['road_distance_km']:.2f} km) and the detailed route "
                f"({route.distance_m / 1000:.2f} km) differ slightly; both come from {provider.label}."
            )
    except RoutingError as exc:
        result["route_status"] = "unavailable"
        result["route_error"] = exc.to_dict()
        warnings.append(f"Route geometry unavailable: {exc.message}")

    return finish("ok", f"Nearest {'live ' if opts.live_only else ''}hub by road "
                        f"{'distance' if opts.ranking == 'distance' else 'travel time'}: "
                        f"{nearest['display_name']} ({nearest['road_distance_km']:.2f} km"
                        + (f", {nearest['duration_min']:.0f} min)." if nearest["duration_min"] is not None else ")."))


async def route_to_hub(
    store: DataStore, routing: RoutingService, origin: tuple[float, float], hub_id: str | None,
    destination: tuple[float, float] | None, travel_mode: str, provider_name: str | None, alternatives: bool,
) -> dict[str, Any]:
    store.require()
    hub = None
    if hub_id:
        hub = store.hubs_by_id.get(hub_id)
        if hub is None:
            raise SearchInputError(f"Unknown hub '{hub_id}'")
        destination = (hub["latitude"], hub["longitude"])
    if destination is None:
        raise SearchInputError("Provide hub_id or destination coordinates")
    provider = routing.resolve(provider_name)
    route = await routing.route(provider, origin, destination, travel_mode, alternatives=alternatives)
    out = route.to_dict()
    out["hub_id"] = hub_id
    return {
        "hub": {k: v for k, v in hub.items() if k != "metadata"} if hub else None,
        "origin": {"latitude": origin[0], "longitude": origin[1]},
        "destination": {"latitude": destination[0], "longitude": destination[1]},
        "route": out,
        "provider": {"name": provider.name, "label": provider.label},
        "links": {
            "google_maps": google_maps_directions_url(origin[0], origin[1], destination[0], destination[1], travel_mode),
        },
    }
