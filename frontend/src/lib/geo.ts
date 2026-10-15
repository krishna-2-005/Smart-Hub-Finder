import type { LatLngBoundsExpression } from "leaflet";

const R = 6371008.8;

/** Great-circle distance in metres. Used only to decide when live tracking has moved enough to re-search. */
export function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function boundsOfPoints(points: [number, number][]): LatLngBoundsExpression | null {
  if (!points.length) return null;
  let minLat = Infinity,
    minLng = Infinity,
    maxLat = -Infinity,
    maxLng = -Infinity;
  for (const [la, lo] of points) {
    minLat = Math.min(minLat, la);
    maxLat = Math.max(maxLat, la);
    minLng = Math.min(minLng, lo);
    maxLng = Math.max(maxLng, lo);
  }
  return [
    [minLat, minLng],
    [maxLat, maxLng],
  ];
}
