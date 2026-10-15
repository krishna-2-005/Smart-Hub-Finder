"""Run a real nearest-hub search and write the five Google Earth KML deliverables.

Writes ``all_hubs.kml``, ``all_clusters.kml``, ``selected_cluster.kml``,
``nearest_hub_route.kml`` and ``company_demo.kml`` to the exports directory.
The route comes from the configured routing provider; if routing fails the
route files are skipped (never replaced by a straight line).

Usage (from ``backend``)::

    .venv/Scripts/python -m scripts.generate_exports --lat 17.4849 --lng 78.4138
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services import export_service as ex  # noqa: E402
from app.services.data_store import DataStore  # noqa: E402
from app.services.nearest_hub_service import SearchOptions, find_nearest_hub  # noqa: E402
from app.services.routing_service import RoutingService  # noqa: E402


async def search(store: DataStore, lat: float, lng: float, mode: str) -> dict:
    routing = RoutingService(get_settings())
    try:
        return await find_nearest_hub(SearchOptions(latitude=lat, longitude=lng, travel_mode=mode), store, routing)
    finally:
        await routing.aclose()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lat", type=float, default=17.4849)
    ap.add_argument("--lng", type=float, default=78.4138)
    ap.add_argument("--mode", default="driving")
    ap.add_argument("--cluster", default=None, help="cluster_id for selected_cluster.kml (default: the result's cluster)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    settings = get_settings()
    out = args.out or settings.exports_path
    out.mkdir(parents=True, exist_ok=True)
    store = DataStore(settings.processed_dir)
    store.load()
    store.require()

    result = asyncio.run(search(store, args.lat, args.lng, args.mode))
    print(f"Search status: {result['status']} - {result['message']}")
    regions = [{**f["properties"], "geometry": f["geometry"]} for f in store.layers["regions"]["features"]]

    files: dict[str, bytes] = {
        "all_hubs.kml": ex.build_hubs_kml(store.hubs, store.clusters, store.service_areas),
        "all_clusters.kml": ex.build_clusters_kml(store.hubs, store.clusters),
    }
    cid = args.cluster or (result.get("nearest") or {}).get("cluster_id") or result["location"].get("cluster_id")
    if cid and cid in store.clusters_by_id:
        files["selected_cluster.kml"] = ex.build_selected_cluster_kml(store.clusters_by_id[cid], store.hubs, store.service_areas)
    if result.get("route"):
        files["nearest_hub_route.kml"] = ex.build_route_kml(result, store.hubs_by_id)
    else:
        print("No road route available - nearest_hub_route.kml not written:", result.get("route_error"))
    files["company_demo.kml"] = ex.build_company_demo_kml(
        store.hubs, store.clusters, regions=regions, result=result if result.get("route") else None,
        service_areas=store.service_areas,
    )
    for name, data in files.items():
        (out / name).write_bytes(data)
        print(f"wrote {out / name} ({len(data) / 1024:.0f} KB)")
    (out / "nearest_hub_search_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    n = result.get("nearest")
    if n:
        print(f"Nearest hub: {n['display_name']} ({n['hub_id']}) - {n['road_distance_km']} km, "
              f"{n['duration_min']} min by road via {result['provider']['label']}; "
              f"route geometry {result['route']['point_count'] if result.get('route') else 0} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
