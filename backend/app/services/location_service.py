"""Locate a coordinate within the hub network (which cluster / service area it falls in)."""

from __future__ import annotations

from typing import Any

from shapely.geometry import Point

from .data_store import DataStore
from .geo_utils import haversine_km, to_local_km


def detect_location(store: DataStore, lat: float, lng: float) -> dict[str, Any]:
    """Determine the cluster for a location.

    Order: inside a cluster boundary polygon -> inside a hub service-area polygon
    (use that hub's cluster) -> outside coverage (report nearest boundary).
    """
    p = Point(lng, lat)
    result: dict[str, Any] = {
        "cluster_id": None,
        "cluster_name": None,
        "detection": "outside_coverage",
        "detection_label": "Outside all cluster boundaries",
        "containing_clusters": [],
        "inside_service_area_of": None,
        "within_coverage": False,
        "nearest_cluster": None,
    }

    if store.service_area_tree is not None:
        idx = store.service_area_tree.query(p, predicate="within")
        if len(idx):
            hid = store.service_area_shapes[int(idx[0])][0]
            h = store.hubs_by_id.get(hid)
            if h:
                result["inside_service_area_of"] = {
                    "hub_id": hid, "name": h.get("name"), "display_name": h.get("display_name"),
                    "cluster_id": h.get("cluster_id"),
                }

    containing: list[str] = []
    if store.cluster_tree is not None:
        containing = [store.cluster_shapes[int(i)][0] for i in store.cluster_tree.query(p, predicate="within")]
    result["containing_clusters"] = [
        {"cluster_id": cid, "name": store.clusters_by_id[cid]["name"]} for cid in containing
    ]

    if containing:
        cid = containing[0]
        if len(containing) > 1:
            # Overlapping boundaries: prefer the one whose hub service area we are in, else the closest hub.
            sa = result["inside_service_area_of"]
            if sa and sa.get("cluster_id") in containing:
                cid = sa["cluster_id"]
            else:
                def nearest_hub_km(c_id: str) -> float:
                    hs = [h for h in store.hubs if h.get("cluster_id") == c_id and h.get("latitude") is not None]
                    return min((haversine_km(lat, lng, h["latitude"], h["longitude"]) for h in hs), default=1e9)
                cid = min(containing, key=nearest_hub_km)
        c = store.clusters_by_id[cid]
        result.update(cluster_id=cid, cluster_name=c["name"], detection="inside_cluster_boundary",
                      detection_label=f"Inside the {c['display_name']} cluster boundary", within_coverage=True)
        return result

    sa = result["inside_service_area_of"]
    if sa and sa.get("cluster_id"):
        c = store.clusters_by_id.get(sa["cluster_id"])
        if c:
            result.update(cluster_id=c["cluster_id"], cluster_name=c["name"], detection="inside_hub_service_area",
                          detection_label=f"Inside the service area of hub {sa['display_name']}",
                          within_coverage=True)
            return result

    # Outside coverage: report the nearest cluster boundary (straight-line, for information only).
    best = None
    for cid, geom in store.cluster_shapes:
        d = to_local_km(geom, lat, lng).distance(to_local_km(p, lat, lng))
        if best is None or d < best[1]:
            best = (cid, d)
    if best:
        c = store.clusters_by_id[best[0]]
        result["nearest_cluster"] = {
            "cluster_id": c["cluster_id"], "name": c["name"], "display_name": c["display_name"],
            "straight_line_km": round(best[1], 3),
        }
    return result
