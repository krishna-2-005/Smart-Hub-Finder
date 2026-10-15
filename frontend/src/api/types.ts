// Types mirroring the FastAPI response schemas (backend/app/models.py).

export type TravelMode = "driving" | "two_wheeler" | "cycling" | "walking";
export type Ranking = "distance" | "duration";
export type ProviderName = "auto" | "google" | "osrm" | "ors";
export type LatLng = [number, number];

export interface Hub {
  hub_id: string | null;
  name: string | null;
  display_name: string | null;
  hub_code: string | null;
  latitude: number | null;
  longitude: number | null;
  location_method: string | null;
  location_inferred: boolean;
  cluster_raw: string | null;
  cluster_id: string | null;
  cluster_name: string | null;
  cluster_source: string | null;
  region: string | null;
  status: string | null;
  is_active: boolean | null;
  hub_type: string | null;
  cluster_mapping: string | null;
  priority: string | null;
  demand_level: string | null;
  original_folder: string | null;
  source_line: number | null;
  placemark_index: number | null;
  service_area_km2: number | null;
  has_service_area: boolean;
  metadata?: Record<string, string> | null;
  issues: string[];
  valid: boolean;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates: unknown;
}

export interface Cluster {
  cluster_id: string;
  name: string;
  display_name: string;
  source: string;
  inferred: boolean;
  name_variants: string[];
  boundary?: GeoJsonGeometry | null;
  boundary_name: string | null;
  hub_ids: string[];
  hub_count: number;
  active_hub_count: number;
  status_counts: Record<string, number>;
  region_counts: Record<string, number>;
  cluster_mapping_counts: Record<string, number>;
  center_lat: number | null;
  center_lng: number | null;
  center_method: string | null;
  boundary_area_km2: number | null;
  service_area_union_km2: number | null;
  bbox: [number, number, number, number] | null;
  max_hub_distance_km: number | null;
  mean_nearest_neighbor_km: number | null;
  hubs_outside_boundary: string[];
  color: string;
}

export interface ProviderStatus {
  name: string;
  label: string;
  configured: boolean;
  reason: string | null;
  modes: TravelMode[];
  requires_key: boolean;
}

export interface RoutingStatus {
  preferred: string;
  active: string | null;
  error: string | null;
  providers: ProviderStatus[];
}

export interface Health {
  status: string;
  version: string;
  dataset_ready: boolean;
  dataset_error: string | null;
  hubs: number;
  clusters: number;
  dataset_loaded_at: string | null;
  routing: RoutingStatus;
}

export interface RouteStep {
  instruction: string;
  distance_m: number;
  duration_s: number;
  maneuver: string | null;
  road_name: string | null;
  location: LatLng | null;
}

export interface AltRoute {
  provider: string;
  provider_label: string;
  travel_mode: string;
  distance_m: number;
  duration_s: number;
  distance_km: number;
  duration_min: number;
  point_count: number;
  geometry: LatLng[];
  summary: string | null;
}

export interface Route extends AltRoute {
  steps: RouteStep[];
  origin_snapped: LatLng | null;
  destination_snapped: LatLng | null;
  origin_snap_m: number | null;
  destination_snap_m: number | null;
  alternatives: AltRoute[];
  traffic_aware: boolean;
  bbox: [number, number, number, number] | null;
  hub_id: string | null;
}

export interface RankedHub {
  rank: number | null;
  hub_id: string | null;
  name: string | null;
  display_name: string | null;
  cluster_id: string | null;
  cluster_name: string | null;
  status: string | null;
  latitude: number;
  longitude: number;
  location_method: string | null;
  straight_line_km: number;
  road_distance_m: number | null;
  road_distance_km: number | null;
  duration_s: number | null;
  duration_min: number | null;
  snap_distance_m: number | null;
  reason?: string | null;
}

export interface LocationInfo {
  cluster_id: string | null;
  cluster_name: string | null;
  detection: "inside_cluster_boundary" | "inside_hub_service_area" | "outside_coverage";
  detection_label: string;
  containing_clusters: { cluster_id: string; name: string }[];
  inside_service_area_of: { hub_id: string; name: string; display_name: string; cluster_id: string } | null;
  within_coverage: boolean;
  nearest_cluster: { cluster_id: string; name: string; display_name: string; straight_line_km: number } | null;
}

export type SearchStatus = "ok" | "no_eligible_hubs" | "no_hubs_in_radius" | "routing_unavailable" | "no_reachable_hubs";

export interface NearestHubResult {
  result_id: string;
  created_at: string;
  status: SearchStatus;
  message: string;
  query: {
    latitude: number;
    longitude: number;
    cluster_selection: string;
    travel_mode: TravelMode;
    ranking: Ranking;
    max_radius_km: number;
    max_candidates: number;
    live_only: boolean;
    top_n: number;
    source: string;
  };
  location: LocationInfo;
  scope: { selection: string; cluster_ids: string[] | null; description: string; fallback: boolean };
  provider: { name: string; label: string } | null;
  evaluation: {
    candidates_in_scope: number;
    excluded_inactive: number;
    eligible: number;
    candidates_within_radius: number;
    candidates_evaluated: number;
    matrix_requests: number;
    strategy: string | null;
    guaranteed: boolean;
    explanation: string;
    radius_note: string;
    origin_snap_m?: number | null;
    outside_radius_ruled_out?: boolean | null;
  };
  nearest: RankedHub | null;
  ranking: RankedHub[];
  unreachable: RankedHub[];
  route: Route | null;
  route_status: string;
  route_error: { code: string; message: string; provider: string | null } | null;
  candidates_preview: { label: string; hubs: RankedHub[] } | null;
  warnings: string[];
  links: Record<string, string>;
  timing_ms: number | null;
  history_id?: number | null;
}

export interface RouteResponse {
  hub: Partial<Hub> | null;
  origin: { latitude: number; longitude: number };
  destination: { latitude: number; longitude: number };
  route: Route;
  provider: { name: string; label: string };
  links: Record<string, string>;
}

export interface NearestHubRequest {
  latitude: number;
  longitude: number;
  cluster_id?: string;
  travel_mode?: TravelMode;
  ranking?: Ranking;
  max_radius_km?: number;
  max_candidates?: number;
  top_n?: number;
  live_only?: boolean;
  provider?: ProviderName;
  alternatives?: boolean;
  source?: "manual" | "gps" | "tracking" | "history";
  save_history?: boolean;
}

export interface Preferences {
  routing_provider: ProviderName;
  travel_mode: TravelMode;
  ranking: Ranking;
  search_radius_km: number;
  max_candidates: number;
  exhaustive_threshold: number;
  top_n: number;
  live_only: boolean;
  max_snap_distance_m: number;
  save_manual_searches: boolean;
  save_gps_searches: boolean;
  tracking_min_move_m: number;
}

export interface SettingsResponse {
  preferences: Preferences;
  routing: RoutingStatus;
  travel_modes: TravelMode[];
}

export interface ClusterStat {
  cluster_id: string;
  name: string;
  display_name: string;
  hub_count: number;
  active: number;
  inactive: number;
  color: string;
  boundary_area_km2: number | null;
  service_area_union_km2: number | null;
  max_hub_distance_km: number | null;
  mean_nearest_neighbor_km: number | null;
  center_lat: number | null;
  center_lng: number | null;
  hub_density_per_km2: number | null;
  region_counts: Record<string, number>;
  hubs_outside_boundary: number;
}

export interface AnalyticsOverview {
  dataset: {
    file_name: string;
    processed_at: string;
    loaded_at: string | null;
    sha256: string;
    placemarks: number;
    repairs: number;
    cluster_method: string;
  };
  totals: {
    hubs: number;
    clusters: number;
    valid_locations: number;
    invalid_locations: number;
    unassigned_hubs: number;
    active_hubs: number;
    inactive_hubs: number;
    status_unknown: number;
    duplicate_ids: number;
    duplicate_names: number;
    duplicate_locations: number;
    isolated_hubs: number;
    boundary_mismatches: number;
    overlapping_service_areas: number;
    hubs_with_issues: number;
    unclassified_placemarks: number;
    location_inferred: number;
  };
  hubs_per_cluster: ClusterStat[];
  status_counts: Record<string, number>;
  region_counts: Record<string, number>;
  cluster_mapping_counts: Record<string, number>;
  priority_counts: Record<string, number>;
  demand_level_counts: Record<string, number>;
  location_method_counts: Record<string, number>;
  coverage: { total_boundary_area_km2: number; total_service_area_km2: number };
  categories: CategoryInfo[];
  missing_data: { field: string; label: string; missing: number; total: number }[];
  layers: Record<string, number>;
}

export interface CategoryInfo {
  category: string;
  label: string;
  count: number;
  inferred: boolean;
  pii: boolean;
  rule: string;
}

export interface DataQuality {
  repair: {
    encoding: string;
    had_bom: boolean;
    valid_before: boolean;
    parse_error_before: string | null;
    valid_after: boolean;
    parse_error_after: string | null;
    coordinates_unchanged: boolean;
    coordinate_blocks: number;
    total_changes: number;
    changes_by_kind: Record<string, number>;
    first_change: { line: number; column: number; kind: string; context: string } | null;
    distinct_contexts: { context: string; occurrences: number }[];
  };
  quality: {
    duplicate_hub_ids: Record<string, number>;
    duplicate_hub_names: Record<string, number>;
    duplicate_locations: { hub_a: string; hub_b: string; distance_m: number }[];
    duplicate_location_threshold_m: number;
    missing_hub_ids: string[];
    missing_hub_names: string[];
    invalid_locations: { hub_id: string; name: string; issues: string[] }[];
    unassigned_hubs: { hub_id: string; name: string }[];
    isolated_hubs: { hub_id: string; name: string; cluster: string; reason: string; nearest_any_km: number | null }[];
    isolation_threshold_km: number;
    cluster_boundary_mismatches: {
      hub_id: string;
      name: string;
      assigned_cluster: string;
      location_inside_cluster_boundaries: string[];
      distance_outside_assigned_boundary_km: number;
    }[];
    overlapping_service_areas: { hub_a: string; name_a: string; hub_b: string; name_b: string; overlap_km2: number; overlap_pct_of_smaller: number }[];
    hubs_with_issues: { hub_id: string; name: string; source_line: number; issues: string[] }[];
    inactive_hubs: { hub_id: string; name: string; status: string; cluster: string }[];
    cluster_name_variants: Record<string, string[]>;
  };
  coordinate_issues: { placemark_index: number; source_line: number; name: string; folder: string; category: string; issues: string[] }[];
  unclassified: { placemark_index: number; source_line: number; name: string; folder: string; geometry: string }[];
  encoding_anomalies: { source_line: number; field: string; category?: string }[];
  assumptions: { topic: string; text: string; inferred: string }[];
  folders: {
    name: string;
    path: string;
    source_line: number;
    placemark_count: number;
    geometry_counts: Record<string, number>;
    categories: Record<string, number>;
    attribute_fields: string[];
  }[];
  categories: CategoryInfo[];
  regions: {
    id: string;
    name: string;
    label: string | null;
    hub_line: string | null;
    hubs_inside_polygon: number;
    hubs_with_line_attribute: number;
    line_hubs_inside_polygon: number;
  }[];
}

export interface HistoryRecord {
  id: number;
  result_id: string;
  created_at: string;
  source: string;
  latitude: number;
  longitude: number;
  cluster_id: string | null;
  cluster_name: string | null;
  travel_mode: string | null;
  ranking: string | null;
  status: string | null;
  nearest_hub_id: string | null;
  nearest_hub_name: string | null;
  road_distance_m: number | null;
  duration_s: number | null;
  provider: string | null;
  candidates_evaluated: number | null;
}

export interface ImportResult {
  activated: boolean;
  file_name: string;
  summary: {
    placemarks: number;
    hubs: number;
    clusters: number;
    cluster_method: string;
    repairs: number;
    valid_before_repair: boolean;
    parse_error_before: string | null;
    coordinates_unchanged: boolean;
    categories: Record<string, number>;
    status_counts: Record<string, number>;
    duplicate_hub_ids: number;
    unassigned_hubs: number;
    coordinate_issues: number;
  };
  report_markdown: string | null;
}

export interface FeatureCollection {
  type: "FeatureCollection";
  features: { type: "Feature"; id?: string; geometry: GeoJsonGeometry; properties: Record<string, unknown> }[];
}
