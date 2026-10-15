"""Read-only dataset endpoints: hubs, clusters, layers, analytics, data quality."""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from .. import __version__
from ..database import Database
from ..models import (
    ClusterDetailResponse,
    ClusterListResponse,
    HealthResponse,
    HubListResponse,
    HubOut,
)
from ..services.data_store import LAYER_NAMES, DataStore
from ..services.routing_service import RoutingService
from .deps import get_db, get_routing, get_store, get_store_any

router = APIRouter(prefix="/api", tags=["data"])


def _hub_out(h: dict[str, Any], include_metadata: bool) -> dict[str, Any]:
    return h if include_metadata else {k: v for k, v in h.items() if k != "metadata"}


@router.get("/health", response_model=HealthResponse)
def health(request: Request, store: DataStore = Depends(get_store_any), routing: RoutingService = Depends(get_routing),
           db: Database = Depends(get_db)):
    prefs = db.get_preferences()
    return {
        "status": "ok" if store.ready else "degraded",
        "version": __version__,
        "dataset_ready": store.ready,
        "dataset_error": store.error,
        "hubs": len(store.hubs),
        "clusters": len(store.clusters),
        "dataset_loaded_at": store.loaded_at,
        "routing": routing.status(prefs["routing_provider"]),
        "deployment": request.app.state.settings.deployment_info(),
    }


@router.get("/hubs", response_model=HubListResponse)
def list_hubs(
    q: Optional[str] = Query(None, description="Search hub name, display name, ID, code or cluster"),
    cluster_id: Optional[str] = None,
    status: Optional[str] = Query(None, description="Exact hub status, e.g. Live"),
    active: Optional[bool] = None,
    region: Optional[str] = None,
    has_issues: Optional[bool] = None,
    include_metadata: bool = False,
    sort: Literal["name", "cluster", "status", "hub_id"] = "name",
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    store: DataStore = Depends(get_store),
):
    hubs = store.hubs
    if cluster_id:
        ids = set(cluster_id.split(","))
        hubs = [h for h in hubs if h.get("cluster_id") in ids]
    if status:
        hubs = [h for h in hubs if (h.get("status") or "").lower() == status.lower()]
    if active is not None:
        hubs = [h for h in hubs if h.get("is_active") is active]
    if region:
        hubs = [h for h in hubs if h.get("region") == region]
    if has_issues is not None:
        hubs = [h for h in hubs if bool(h.get("issues")) is has_issues]
    if q:
        needle = q.strip().lower()
        hubs = [
            h for h in hubs
            if any(needle in (str(h.get(k) or "")).lower()
                   for k in ("name", "display_name", "hub_id", "hub_code", "cluster_name"))
        ]
    key = {"name": "name", "cluster": "cluster_name", "status": "status", "hub_id": "hub_id"}[sort]
    hubs = sorted(hubs, key=lambda h: (str(h.get(key) or ""), str(h.get("name") or "")))
    page = hubs[offset : offset + limit]
    return {"total": len(hubs), "count": len(page), "offset": offset,
            "hubs": [_hub_out(h, include_metadata) for h in page]}


@router.get("/hubs/{hub_id}", response_model=HubOut)
def get_hub(hub_id: str, store: DataStore = Depends(get_store)):
    h = store.hubs_by_id.get(hub_id)
    if h is None:
        raise HTTPException(404, f"Hub '{hub_id}' not found")
    return h


@router.get("/clusters", response_model=ClusterListResponse)
def list_clusters(include_boundary: bool = True, store: DataStore = Depends(get_store)):
    return {
        "count": len(store.clusters),
        "method": store.analysis.get("clusters", {}).get("method"),
        "clusters": [store.cluster_public(c, include_boundary) for c in store.clusters],
    }


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
def get_cluster(cluster_id: str, include_metadata: bool = False, store: DataStore = Depends(get_store)):
    c = store.clusters_by_id.get(cluster_id)
    if c is None:
        raise HTTPException(404, f"Cluster '{cluster_id}' not found")
    hubs = [_hub_out(h, include_metadata) for h in store.hubs if h.get("cluster_id") == cluster_id]
    return {"cluster": c, "hubs": hubs}


@router.get("/clusters/{cluster_id}/hubs", response_model=HubListResponse)
def get_cluster_hubs(cluster_id: str, include_metadata: bool = False, store: DataStore = Depends(get_store)):
    if cluster_id not in store.clusters_by_id:
        raise HTTPException(404, f"Cluster '{cluster_id}' not found")
    hubs = sorted((h for h in store.hubs if h.get("cluster_id") == cluster_id), key=lambda h: h.get("name") or "")
    return {"total": len(hubs), "count": len(hubs), "offset": 0, "hubs": [_hub_out(h, include_metadata) for h in hubs]}


@router.get("/layers/{name}")
def get_layer(name: str, store: DataStore = Depends(get_store)):
    if name not in LAYER_NAMES:
        raise HTTPException(404, f"Unknown layer '{name}'. Available: {', '.join(LAYER_NAMES)}")
    return store.layers[name]


@router.get("/analytics/overview")
def analytics_overview(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    a = store.analysis
    q = a["quality"]
    hubs = store.hubs

    def counts(key: str) -> dict[str, int]:
        return dict(Counter((h.get(key) or "unknown") for h in hubs).most_common())

    missing_fields = {
        "hub_id": "Hub ID", "name": "Hub name", "cluster_id": "Cluster", "status": "Operational status",
        "region": "Region / Line", "priority": "Priority", "cluster_mapping": "Cluster mapping",
        "demand_level": "Demand level", "hub_type": "Hub type",
    }
    missing = [
        {"field": k, "label": label, "missing": sum(1 for h in hubs if h.get(k) in (None, "")),
         "total": len(hubs)}
        for k, label in missing_fields.items()
    ]
    return {
        "dataset": {
            "file_name": a["source"]["file_name"],
            "processed_at": a["source"]["processed_at"],
            "loaded_at": store.loaded_at,
            "sha256": a["source"]["sha256"],
            "placemarks": a["placemark_count"],
            "repairs": a["repair"]["total_changes"],
            "cluster_method": a["clusters"]["method"],
        },
        "totals": {
            "hubs": len(hubs),
            "clusters": len(store.clusters),
            "valid_locations": sum(1 for h in hubs if h.get("valid")),
            "invalid_locations": sum(1 for h in hubs if not h.get("valid")),
            "unassigned_hubs": len(q["unassigned_hubs"]),
            "active_hubs": sum(1 for h in hubs if h.get("is_active") is True),
            "inactive_hubs": sum(1 for h in hubs if h.get("is_active") is False),
            "status_unknown": sum(1 for h in hubs if h.get("is_active") is None),
            "duplicate_ids": len(q["duplicate_hub_ids"]),
            "duplicate_names": len(q["duplicate_hub_names"]),
            "duplicate_locations": len(q["duplicate_locations"]),
            "isolated_hubs": len(q["isolated_hubs"]),
            "boundary_mismatches": len(q["cluster_boundary_mismatches"]),
            "overlapping_service_areas": len(q["overlapping_service_areas"]),
            "hubs_with_issues": len(q["hubs_with_issues"]),
            "unclassified_placemarks": len(a["unclassified"]),
            "location_inferred": sum(1 for h in hubs if h.get("location_inferred")),
        },
        "hubs_per_cluster": [
            {
                "cluster_id": c["cluster_id"], "name": c["name"], "display_name": c["display_name"],
                "hub_count": c["hub_count"], "active": c["active_hub_count"],
                "inactive": c["hub_count"] - c["active_hub_count"], "color": c["color"],
                "boundary_area_km2": c.get("boundary_area_km2"),
                "service_area_union_km2": c.get("service_area_union_km2"),
                "max_hub_distance_km": c.get("max_hub_distance_km"),
                "mean_nearest_neighbor_km": c.get("mean_nearest_neighbor_km"),
                "center_lat": c.get("center_lat"), "center_lng": c.get("center_lng"),
                "hub_density_per_km2": round(c["hub_count"] / c["boundary_area_km2"], 3)
                if c.get("boundary_area_km2") else None,
                "region_counts": c.get("region_counts"),
                "hubs_outside_boundary": len(c.get("hubs_outside_boundary") or []),
            }
            for c in store.clusters
        ],
        "status_counts": counts("status"),
        "region_counts": counts("region"),
        "cluster_mapping_counts": counts("cluster_mapping"),
        "priority_counts": counts("priority"),
        "demand_level_counts": counts("demand_level"),
        "location_method_counts": counts("location_method"),
        "coverage": {
            "total_boundary_area_km2": round(sum(c.get("boundary_area_km2") or 0 for c in store.clusters), 2),
            "total_service_area_km2": round(sum(h.get("service_area_km2") or 0 for h in hubs), 2),
        },
        "categories": a["categories"],
        "missing_data": missing,
        "layers": a["layers"],
    }


@router.get("/data-quality")
def data_quality(store: DataStore = Depends(get_store)) -> dict[str, Any]:
    a = store.analysis
    return {
        "repair": a["repair"],
        "quality": a["quality"],
        "coordinate_issues": a["coordinate_issues"],
        "unclassified": a["unclassified"],
        "encoding_anomalies": a["encoding_anomalies"],
        "assumptions": a["assumptions"],
        "folders": a["folders"],
        "categories": a["categories"],
        "regions": a["regions"],
    }


@router.get("/report", response_class=PlainTextResponse)
def analysis_report(store: DataStore = Depends(get_store)):
    return (store.processed_dir / "kml_analysis_report.md").read_text(encoding="utf-8")
