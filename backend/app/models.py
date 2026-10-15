"""Pydantic request / response schemas."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TravelMode = Literal["driving", "two_wheeler", "cycling", "walking"]
Ranking = Literal["distance", "duration"]
ProviderName = Literal["auto", "google", "osrm", "ors"]
LatLngPair = tuple[float, float]


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class NearestHubRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False, description="WGS84 longitude")
    cluster_id: str = Field("auto", description="'auto' (detect), 'all', or a cluster_id")
    travel_mode: Optional[TravelMode] = None
    ranking: Optional[Ranking] = None
    max_radius_km: Optional[float] = Field(None, gt=0, le=200)
    max_candidates: Optional[int] = Field(None, ge=1, le=500)
    top_n: Optional[int] = Field(None, ge=1, le=20)
    live_only: Optional[bool] = None
    provider: Optional[ProviderName] = None
    alternatives: bool = True
    source: Literal["manual", "gps", "tracking", "history"] = "manual"
    save_history: Optional[bool] = Field(
        None, description="Persist this search in route history. Defaults to the preference for the source."
    )


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    origin_longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False)
    hub_id: Optional[str] = None
    destination_latitude: Optional[float] = Field(None, ge=-90, le=90, allow_inf_nan=False)
    destination_longitude: Optional[float] = Field(None, ge=-180, le=180, allow_inf_nan=False)
    travel_mode: Optional[TravelMode] = None
    provider: Optional[ProviderName] = None
    alternatives: bool = True
    result_id: Optional[str] = Field(None, description="Attach this route to a previous search for KML export")


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routing_provider: Optional[ProviderName] = None
    travel_mode: Optional[TravelMode] = None
    ranking: Optional[Ranking] = None
    search_radius_km: Optional[float] = Field(None, gt=0, le=200)
    max_candidates: Optional[int] = Field(None, ge=1, le=500)
    exhaustive_threshold: Optional[int] = Field(None, ge=1, le=200)
    top_n: Optional[int] = Field(None, ge=1, le=20)
    live_only: Optional[bool] = None
    max_snap_distance_m: Optional[float] = Field(None, ge=10, le=10000)
    save_manual_searches: Optional[bool] = None
    save_gps_searches: Optional[bool] = None
    tracking_min_move_m: Optional[float] = Field(None, ge=10, le=10000)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    dataset_ready: bool
    dataset_error: Optional[str]
    hubs: int
    clusters: int
    dataset_loaded_at: Optional[str]
    routing: dict[str, Any]
    deployment: dict[str, Any]


class HubOut(BaseModel):
    hub_id: Optional[str]
    name: Optional[str]
    display_name: Optional[str]
    hub_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    location_method: Optional[str]
    location_inferred: bool
    cluster_raw: Optional[str]
    cluster_id: Optional[str]
    cluster_name: Optional[str]
    cluster_source: Optional[str]
    region: Optional[str]
    status: Optional[str]
    is_active: Optional[bool]
    hub_type: Optional[str]
    cluster_mapping: Optional[str]
    priority: Optional[str]
    demand_level: Optional[str]
    original_folder: Optional[str]
    source_line: Optional[int]
    placemark_index: Optional[int]
    service_area_km2: Optional[float]
    has_service_area: bool
    metadata: Optional[dict[str, str]] = None
    issues: list[str]
    valid: bool


class HubListResponse(BaseModel):
    total: int
    count: int
    offset: int
    hubs: list[HubOut]


class ClusterOut(BaseModel):
    cluster_id: str
    name: str
    display_name: str
    source: str
    inferred: bool
    name_variants: list[str]
    boundary: Optional[dict[str, Any]] = None
    boundary_name: Optional[str]
    hub_ids: list[str]
    hub_count: int
    active_hub_count: int
    status_counts: dict[str, int]
    region_counts: dict[str, int]
    cluster_mapping_counts: dict[str, int]
    center_lat: Optional[float]
    center_lng: Optional[float]
    center_method: Optional[str]
    boundary_area_km2: Optional[float]
    service_area_union_km2: Optional[float]
    bbox: Optional[list[float]]
    max_hub_distance_km: Optional[float]
    mean_nearest_neighbor_km: Optional[float]
    hubs_outside_boundary: list[str]
    color: str


class ClusterListResponse(BaseModel):
    count: int
    method: Optional[str]
    clusters: list[ClusterOut]


class ClusterDetailResponse(BaseModel):
    cluster: ClusterOut
    hubs: list[HubOut]


class RouteStepOut(BaseModel):
    instruction: str
    distance_m: float
    duration_s: float
    maneuver: Optional[str]
    road_name: Optional[str]
    location: Optional[LatLngPair]


class AltRouteOut(BaseModel):
    provider: str
    provider_label: str
    travel_mode: str
    distance_m: float
    duration_s: float
    distance_km: float
    duration_min: float
    point_count: int
    geometry: list[LatLngPair]
    summary: Optional[str]


class RouteOut(BaseModel):
    provider: str
    provider_label: str
    travel_mode: str
    distance_m: float
    duration_s: float
    distance_km: float
    duration_min: float
    point_count: int
    geometry: list[LatLngPair]
    steps: list[RouteStepOut]
    summary: Optional[str]
    origin_snapped: Optional[LatLngPair]
    destination_snapped: Optional[LatLngPair]
    origin_snap_m: Optional[float]
    destination_snap_m: Optional[float]
    alternatives: list[AltRouteOut]
    traffic_aware: bool
    bbox: Optional[list[float]] = None
    hub_id: Optional[str] = None


class RankedHub(BaseModel):
    rank: Optional[int]
    hub_id: Optional[str]
    name: Optional[str]
    display_name: Optional[str]
    cluster_id: Optional[str]
    cluster_name: Optional[str]
    status: Optional[str]
    latitude: float
    longitude: float
    location_method: Optional[str]
    straight_line_km: float = Field(description="Straight-line pre-filter distance. NOT a road distance.")
    road_distance_m: Optional[float]
    road_distance_km: Optional[float]
    duration_s: Optional[float]
    duration_min: Optional[float]
    snap_distance_m: Optional[float]
    reason: Optional[str] = None


class LocationInfo(BaseModel):
    cluster_id: Optional[str]
    cluster_name: Optional[str]
    detection: str
    detection_label: str
    containing_clusters: list[dict[str, Any]]
    inside_service_area_of: Optional[dict[str, Any]]
    within_coverage: bool
    nearest_cluster: Optional[dict[str, Any]]


class ScopeInfo(BaseModel):
    selection: str
    cluster_ids: Optional[list[str]]
    description: str
    fallback: bool


class EvaluationInfo(BaseModel):
    candidates_in_scope: int
    excluded_inactive: int
    eligible: int
    candidates_within_radius: int
    candidates_evaluated: int
    matrix_requests: int
    strategy: Optional[str]
    guaranteed: bool
    explanation: str
    radius_note: str
    origin_snap_m: Optional[float] = None
    outside_radius_ruled_out: Optional[bool] = None


class CandidatesPreview(BaseModel):
    label: str
    hubs: list[RankedHub]


class NearestHubResponse(BaseModel):
    result_id: str
    created_at: str
    status: Literal["ok", "no_eligible_hubs", "no_hubs_in_radius", "routing_unavailable", "no_reachable_hubs"]
    message: str
    query: dict[str, Any]
    location: LocationInfo
    scope: ScopeInfo
    provider: Optional[dict[str, str]]
    evaluation: EvaluationInfo
    nearest: Optional[RankedHub]
    ranking: list[RankedHub]
    unreachable: list[RankedHub]
    route: Optional[RouteOut]
    route_status: str
    route_error: Optional[dict[str, Any]]
    candidates_preview: Optional[CandidatesPreview]
    warnings: list[str]
    links: dict[str, str]
    timing_ms: Optional[int]
    history_id: Optional[int] = None


class RouteResponse(BaseModel):
    hub: Optional[dict[str, Any]]
    origin: dict[str, float]
    destination: dict[str, float]
    route: RouteOut
    provider: dict[str, str]
    links: dict[str, str]


class LocateResponse(BaseModel):
    latitude: float
    longitude: float
    location: LocationInfo


class HistoryListResponse(BaseModel):
    total: int
    records: list[dict[str, Any]]


class ImportResponse(BaseModel):
    activated: bool
    file_name: str
    summary: dict[str, Any]
    report_markdown: Optional[str] = None
