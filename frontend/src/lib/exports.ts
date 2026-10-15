import type { Hub, NearestHubResult, RankedHub, Route } from "../api/types";
import { haversineMeters } from "./geo";

/**
 * The search result to export for the hub whose route is on screen: the result itself for the
 * nearest hub, or a copy whose `nearest`/`route` point at the alternative the user selected.
 */
export function resultForSelectedHub(
  result: NearestHubResult,
  hubId: string | null,
  route: Route | null,
  hub?: Hub,
): NearestHubResult {
  if (!hubId || hubId === result.nearest?.hub_id || !route) return result;
  let row: RankedHub | undefined = result.ranking.find((r) => r.hub_id === hubId);
  if (!row && hub && hub.latitude !== null && hub.longitude !== null) {
    row = {
      rank: null,
      hub_id: hub.hub_id,
      name: hub.name,
      display_name: hub.display_name,
      cluster_id: hub.cluster_id,
      cluster_name: hub.cluster_name,
      status: hub.status,
      latitude: hub.latitude,
      longitude: hub.longitude,
      location_method: hub.location_method,
      straight_line_km: Math.round(haversineMeters(result.query.latitude, result.query.longitude, hub.latitude, hub.longitude)) / 1000,
      road_distance_m: route.distance_m,
      road_distance_km: route.distance_km,
      duration_s: route.duration_s,
      duration_min: route.duration_min,
      snap_distance_m: route.destination_snap_m,
    };
  }
  return row ? { ...result, nearest: row, route } : result;
}
