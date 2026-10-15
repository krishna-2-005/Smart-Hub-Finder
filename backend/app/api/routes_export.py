"""KML / CSV / GeoJSON export endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from ..database import Database
from ..services import export_service as ex
from ..services.data_store import DataStore
from ..services.nearest_hub_service import ResultCache
from .deps import get_cache, get_db, get_store

router = APIRouter(prefix="/api/export", tags=["export"])

KML_MEDIA = "application/vnd.google-earth.kml+xml"
KmlType = Literal["all_hubs", "all_clusters", "selected_cluster", "route", "company_demo", "cleaned"]


def _download(content: bytes | str, filename: str, media: str) -> Response:
    body = content.encode("utf-8") if isinstance(content, str) else content
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _result(result_id: Optional[str], cache: ResultCache, db: Database, required: bool) -> Optional[dict[str, Any]]:
    if not result_id:
        if required:
            raise HTTPException(422, "result_id is required for this export (run a nearest-hub search first)")
        return None
    r = cache.get(result_id) or db.get_history_by_result(result_id)
    if r is None:
        raise HTTPException(404, "Search result not found; it may have expired. Run the search again.")
    return r


def _with_selected_route(result: dict[str, Any], hub_id: Optional[str]) -> dict[str, Any]:
    """Return a copy of ``result`` whose primary route/nearest point at ``hub_id`` (an alternative hub)."""
    if not hub_id or (result.get("nearest") or {}).get("hub_id") == hub_id:
        return result
    route = (result.get("selected_routes") or {}).get(hub_id)
    hub_row = next((r for r in result.get("ranking") or [] if r["hub_id"] == hub_id), None)
    if route is None or hub_row is None:
        raise HTTPException(404, "No route has been calculated for that hub in this search")
    return {**result, "nearest": hub_row, "route": route}


def build_kml(kind: str, store: DataStore, result: Optional[dict[str, Any]], cluster_id: Optional[str],
              include_service_areas: bool) -> tuple[bytes, str]:
    sa = store.service_areas if include_service_areas else None
    if kind == "all_hubs":
        return ex.build_hubs_kml(store.hubs, store.clusters, sa), "all_hubs.kml"
    if kind == "all_clusters":
        return ex.build_clusters_kml(store.hubs, store.clusters), "all_clusters.kml"
    if kind == "selected_cluster":
        cid = cluster_id or (((result or {}).get("nearest") or {}).get("cluster_id"))
        if not cid or cid not in store.clusters_by_id:
            raise HTTPException(422, "A valid cluster_id is required for selected_cluster export")
        return ex.build_selected_cluster_kml(store.clusters_by_id[cid], store.hubs, sa), f"selected_cluster_{cid}.kml"
    if kind == "route":
        if result is None or not result.get("route"):
            raise HTTPException(422, "This search has no road route to export")
        return ex.build_route_kml(result, store.hubs_by_id), "nearest_hub_route.kml"
    if kind == "company_demo":
        return ex.build_company_demo_kml(store.hubs, store.clusters, regions=_regions(store), result=result,
                                         service_areas=sa), "company_demo.kml"
    if kind == "cleaned":
        return (store.processed_dir / "cleaned_hubs.kml").read_bytes(), "cleaned_hubs.kml"
    raise HTTPException(422, f"Unknown export type {kind}")


def _regions(store: DataStore) -> list[dict[str, Any]]:
    return [
        {**f["properties"], "geometry": f["geometry"]}
        for f in store.layers.get("regions", {}).get("features", [])
    ]


@router.get("/kml")
def export_kml(
    type: KmlType = Query("all_hubs"),
    cluster_id: Optional[str] = None,
    result_id: Optional[str] = None,
    hub_id: Optional[str] = Query(None, description="For route exports: an alternative hub routed in that search"),
    include_service_areas: bool = False,
    store: DataStore = Depends(get_store),
    cache: ResultCache = Depends(get_cache),
    db: Database = Depends(get_db),
):
    result = _result(result_id, cache, db, required=type == "route")
    if result is not None:
        result = _with_selected_route(result, hub_id)
    data, name = build_kml(type, store, result, cluster_id, include_service_areas)
    return _download(data, name, KML_MEDIA)


@router.get("/csv")
def export_csv(
    type: Literal["hubs", "clusters", "search"] = "hubs",
    cluster_id: Optional[str] = None,
    result_id: Optional[str] = None,
    store: DataStore = Depends(get_store),
    cache: ResultCache = Depends(get_cache),
    db: Database = Depends(get_db),
):
    stamp = datetime.now().strftime("%Y%m%d")
    if type == "hubs":
        hubs = [h for h in store.hubs if not cluster_id or h.get("cluster_id") == cluster_id]
        return _download(ex.hubs_csv(hubs), f"hub_directory_{stamp}.csv", "text/csv; charset=utf-8")
    if type == "clusters":
        return _download(ex.clusters_csv(store.clusters), f"cluster_summary_{stamp}.csv", "text/csv; charset=utf-8")
    result = _result(result_id, cache, db, required=True)
    return _download(ex.search_csv(result), f"nearest_hub_results_{result['result_id']}.csv", "text/csv; charset=utf-8")


@router.get("/geojson")
def export_geojson(
    type: Literal["hubs", "clusters", "service_areas", "route"] = "hubs",
    result_id: Optional[str] = None,
    store: DataStore = Depends(get_store),
    cache: ResultCache = Depends(get_cache),
    db: Database = Depends(get_db),
):
    if type == "hubs":
        data, name = ex.hubs_geojson(store.hubs), "hubs.geojson"
    elif type == "clusters":
        data, name = ex.clusters_geojson(store.clusters), "clusters.geojson"
    elif type == "service_areas":
        data, name = store.layers["hub_service_areas"], "hub_service_areas.geojson"
    else:
        r = _result(result_id, cache, db, required=True)
        if not r.get("route"):
            raise HTTPException(422, "This search has no road route to export")
        data = {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[p[1], p[0]] for p in r["route"]["geometry"]]},
            "properties": {k: r["route"][k] for k in ("provider", "travel_mode", "distance_m", "duration_s")}
                          | {"hub_id": r["nearest"]["hub_id"], "hub_name": r["nearest"]["display_name"]},
        }]}
        name = "nearest_hub_route.geojson"
    return _download(json.dumps(data, ensure_ascii=False), name, "application/geo+json")


@router.post("/generate-files")
def generate_files(
    request: Request,
    result_id: Optional[str] = None,
    cluster_id: Optional[str] = None,
    store: DataStore = Depends(get_store),
    cache: ResultCache = Depends(get_cache),
    db: Database = Depends(get_db),
):
    """Write the five standard Google Earth KML files into the project's ``exports/`` folder."""
    result = _result(result_id, cache, db, required=False) or cache.latest()
    out_dir = request.app.state.settings.exports_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for kind, fname in (("all_hubs", "all_hubs.kml"), ("all_clusters", "all_clusters.kml"),
                        ("selected_cluster", "selected_cluster.kml"), ("route", "nearest_hub_route.kml"),
                        ("company_demo", "company_demo.kml")):
        try:
            data, _ = build_kml(kind, store, result, cluster_id, include_service_areas=kind != "all_clusters")
        except HTTPException as exc:
            written.append({"file": fname, "written": False, "reason": exc.detail})
            continue
        (out_dir / fname).write_bytes(data)
        written.append({"file": fname, "written": True, "bytes": len(data), "path": str(out_dir / fname)})
    return {"directory": str(out_dir), "result_id": (result or {}).get("result_id"), "files": written}
