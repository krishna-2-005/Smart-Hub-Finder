export const fmtKm = (km: number | null | undefined, digits = 2) =>
  km === null || km === undefined ? "—" : `${km.toFixed(km < 10 ? digits : 1)} km`;

export const fmtMeters = (m: number | null | undefined) => {
  if (m === null || m === undefined) return "—";
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(m < 10000 ? 2 : 1)} km`;
};

export const fmtMinutes = (min: number | null | undefined) => {
  if (min === null || min === undefined) return "—";
  if (min < 1) return "< 1 min";
  if (min < 60) return `${Math.round(min)} min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m} min` : `${h} h`;
};

export const fmtSecondsAsMin = (s: number | null | undefined) => (s === null || s === undefined ? "—" : fmtMinutes(s / 60));

export const fmtCoord = (v: number | null | undefined, digits = 6) => (v === null || v === undefined ? "—" : v.toFixed(digits));

export const fmtInt = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n.toLocaleString("en-IN"));

export const fmtNum = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: digits });

export const fmtDateTime = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

export const travelModeLabel: Record<string, string> = {
  driving: "Driving",
  two_wheeler: "Two-wheeler",
  cycling: "Cycling",
  walking: "Walking",
};

export const rankingLabel: Record<string, string> = {
  distance: "Shortest road distance",
  duration: "Shortest travel time",
};

export const locationMethodLabel: Record<string, string> = {
  service_area_centroid: "Service-area centroid (inferred)",
  service_area_interior_point: "Service-area interior point (inferred)",
  point_geometry: "KML point",
};

export const strategyLabel = (s: string | null | undefined) =>
  ({
    exhaustive: "Exhaustive (all candidates)",
    "progressive (bounded)": "Progressive with lower-bound proof",
    "progressive (complete)": "Progressive (all candidates)",
    "progressive (capped)": "Progressive, capped shortlist",
  })[s ?? ""] ?? s ?? "—";

export const pct = (part: number, total: number) => (total ? Math.round((part / total) * 1000) / 10 : 0);
