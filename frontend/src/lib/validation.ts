export interface CoordinateErrors {
  latitude?: string;
  longitude?: string;
}

export type CoordinateParse =
  | { ok: true; latitude: number; longitude: number }
  | { ok: false; errors: CoordinateErrors };

const NUMBER_RE = /^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$/;

function parseOne(raw: string, label: string, min: number, max: number): number | string {
  const v = raw.trim();
  if (!v) return `${label} is required.`;
  if (!NUMBER_RE.test(v)) return `${label} must be a number (decimal degrees, e.g. ${label === "Latitude" ? "17.4485" : "78.3908"}).`;
  const n = Number(v);
  if (!Number.isFinite(n)) return `${label} must be a finite number.`;
  if (n < min || n > max) return `${label} must be between ${min} and ${max}.`;
  return n;
}

/** Validate latitude/longitude text inputs (decimal degrees, negatives allowed). */
export function validateCoordinates(lat: string, lng: string): CoordinateParse {
  const la = parseOne(lat, "Latitude", -90, 90);
  const lo = parseOne(lng, "Longitude", -180, 180);
  const errors: CoordinateErrors = {};
  if (typeof la === "string") errors.latitude = la;
  if (typeof lo === "string") errors.longitude = lo;
  if (errors.latitude || errors.longitude) return { ok: false, errors };
  return { ok: true, latitude: la as number, longitude: lo as number };
}

/**
 * Accept a pasted "lat, lng" pair (as copied from Google Maps) and split it.
 * Returns null when the text is not a pair.
 */
export function splitPastedPair(text: string): { lat: string; lng: string } | null {
  const m = text.trim().match(/^\(?\s*([+-]?\d+(?:\.\d+)?)\s*[,;\s]\s*([+-]?\d+(?:\.\d+)?)\s*\)?$/);
  if (!m) return null;
  return { lat: m[1], lng: m[2] };
}
