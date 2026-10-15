import type {
  AnalyticsOverview,
  Cluster,
  DataQuality,
  FeatureCollection,
  Health,
  HistoryRecord,
  Hub,
  ImportResult,
  NearestHubRequest,
  NearestHubResult,
  Preferences,
  RouteResponse,
  SettingsResponse,
  TravelMode,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function messageFrom(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) return String((d as { message: unknown }).message);
    return JSON.stringify(d);
  }
  if (status === 502 || status === 504) return "The backend API is not reachable. Is the FastAPI server running on port 8000?";
  return `Request failed (HTTP ${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the backend API. Check that the FastAPI server is running.");
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) throw new ApiError(res.status, messageFrom(body, res.status));
  return body as T;
}

const json = (method: string, data?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: data === undefined ? undefined : JSON.stringify(data),
});

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request<Health>("/api/health"),
  clusters: () => request<{ count: number; method: string | null; clusters: Cluster[] }>("/api/clusters"),
  hubs: () => request<{ total: number; hubs: Hub[] }>("/api/hubs?limit=5000&include_metadata=true"),
  analytics: () => request<AnalyticsOverview>("/api/analytics/overview"),
  dataQuality: () => request<DataQuality>("/api/data-quality"),
  report: () => request<string>("/api/report"),
  layer: (name: string) => request<FeatureCollection>(`/api/layers/${name}`),

  nearestHub: (req: NearestHubRequest) => request<NearestHubResult>("/api/nearest-hub", json("POST", req)),
  route: (body: {
    origin_latitude: number;
    origin_longitude: number;
    hub_id: string;
    travel_mode?: TravelMode;
    result_id?: string;
    alternatives?: boolean;
  }) => request<RouteResponse>("/api/route", json("POST", body)),
  result: (id: string) => request<NearestHubResult>(`/api/results/${id}`),

  settings: () => request<SettingsResponse>("/api/settings"),
  updateSettings: (p: Partial<Preferences>) => request<SettingsResponse>("/api/settings", json("PUT", p)),
  resetSettings: () => request<SettingsResponse>("/api/settings", { method: "DELETE" }),
  routingTest: (provider?: string, mode?: string) =>
    request<Record<string, unknown>>(`/api/routing/test${qs({ provider, mode })}`, { method: "POST" }),

  history: (limit = 200) => request<{ total: number; records: HistoryRecord[] }>(`/api/history?limit=${limit}`),
  historyRecord: (id: number) => request<HistoryRecord & { result: NearestHubResult }>(`/api/history/${id}`),
  deleteHistory: (id: number) => request<{ deleted: number }>(`/api/history/${id}`, { method: "DELETE" }),
  clearHistory: () => request<{ deleted: number }>("/api/history", { method: "DELETE" }),

  importKml: (file: File, activate: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("activate", String(activate));
    return request<ImportResult>("/api/import-kml", { method: "POST", body: fd });
  },
  generateExportFiles: (resultId?: string, clusterId?: string) =>
    request<{ directory: string; result_id: string | null; files: { file: string; written: boolean; bytes?: number; reason?: string }[] }>(
      `/api/export/generate-files${qs({ result_id: resultId, cluster_id: clusterId })}`,
      { method: "POST" },
    ),
};

export const exportUrl = {
  kml: (type: string, opts: { cluster_id?: string; result_id?: string; hub_id?: string; include_service_areas?: boolean } = {}) =>
    `${BASE}/api/export/kml${qs({ type, ...opts })}`,
  csv: (type: "hubs" | "clusters" | "search", opts: { result_id?: string; cluster_id?: string } = {}) =>
    `${BASE}/api/export/csv${qs({ type, ...opts })}`,
  geojson: (type: "hubs" | "clusters" | "service_areas" | "route", opts: { result_id?: string } = {}) =>
    `${BASE}/api/export/geojson${qs({ type, ...opts })}`,
};
