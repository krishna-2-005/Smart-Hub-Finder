"""Nearest-hub search, routing and location endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Database
from ..models import LocateResponse, NearestHubRequest, NearestHubResponse, RouteRequest, RouteResponse
from ..services.data_store import DataStore
from ..services.location_service import detect_location
from ..services.nearest_hub_service import (
    ResultCache,
    SearchInputError,
    SearchOptions,
    find_nearest_hub,
    route_to_hub,
)
from ..services.routing_service import RoutingError, RoutingService
from .deps import get_cache, get_db, get_routing, get_store

router = APIRouter(prefix="/api", tags=["search"])
log = logging.getLogger(__name__)


@router.post("/nearest-hub", response_model=NearestHubResponse)
async def nearest_hub(
    req: NearestHubRequest,
    store: DataStore = Depends(get_store),
    routing: RoutingService = Depends(get_routing),
    db: Database = Depends(get_db),
    cache: ResultCache = Depends(get_cache),
):
    prefs = db.get_preferences()
    opts = SearchOptions(
        latitude=req.latitude,
        longitude=req.longitude,
        cluster_id=req.cluster_id or "auto",
        travel_mode=req.travel_mode or prefs["travel_mode"],
        ranking=req.ranking or prefs["ranking"],
        max_radius_km=req.max_radius_km or prefs["search_radius_km"],
        max_candidates=req.max_candidates or prefs["max_candidates"],
        exhaustive_threshold=prefs["exhaustive_threshold"],
        top_n=req.top_n or prefs["top_n"],
        live_only=prefs["live_only"] if req.live_only is None else req.live_only,
        max_snap_distance_m=prefs["max_snap_distance_m"],
        provider=req.provider or prefs["routing_provider"],
        alternatives=req.alternatives,
        source=req.source,
    )
    try:
        result = await find_nearest_hub(opts, store, routing)
    except SearchInputError as exc:
        raise HTTPException(422, str(exc)) from exc

    cache.put(result)
    save = req.save_history
    if save is None:
        save = prefs["save_gps_searches"] if req.source in ("gps", "tracking") else prefs["save_manual_searches"]
    if save:
        result["history_id"] = db.add_history(result)
    log.info("nearest-hub status=%s source=%s evaluated=%s provider=%s %sms", result["status"], req.source,
             result["evaluation"]["candidates_evaluated"], (result.get("provider") or {}).get("name"),
             result["timing_ms"])
    return result


@router.post("/route", response_model=RouteResponse)
async def route(
    req: RouteRequest,
    store: DataStore = Depends(get_store),
    routing: RoutingService = Depends(get_routing),
    db: Database = Depends(get_db),
    cache: ResultCache = Depends(get_cache),
):
    prefs = db.get_preferences()
    dest = None
    if req.destination_latitude is not None and req.destination_longitude is not None:
        dest = (req.destination_latitude, req.destination_longitude)
    try:
        out = await route_to_hub(
            store, routing, (req.origin_latitude, req.origin_longitude), req.hub_id, dest,
            req.travel_mode or prefs["travel_mode"], req.provider or prefs["routing_provider"], req.alternatives,
        )
    except SearchInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(502, detail=exc.to_dict()) from exc

    if req.result_id and req.hub_id:
        cached = cache.get(req.result_id)
        if cached is not None:
            cached.setdefault("selected_routes", {})[req.hub_id] = out["route"]
    return out


@router.get("/locate", response_model=LocateResponse)
def locate(
    lat: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
    lng: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
    store: DataStore = Depends(get_store),
):
    return {"latitude": lat, "longitude": lng, "location": detect_location(store, lat, lng)}


@router.get("/results/{result_id}", response_model=NearestHubResponse)
def get_result(result_id: str, cache: ResultCache = Depends(get_cache), db: Database = Depends(get_db)):
    r = cache.get(result_id) or db.get_history_by_result(result_id)
    if r is None:
        raise HTTPException(404, "Result not found (results are kept in memory only unless saved to history)")
    return r
