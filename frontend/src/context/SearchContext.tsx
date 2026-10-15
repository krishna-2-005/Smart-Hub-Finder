import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { NearestHubRequest, NearestHubResult, Route, TravelMode } from "../api/types";
import { useAppData } from "./AppData";

export type SearchSource = "manual" | "gps" | "tracking" | "history";

export interface SearchOptionsState {
  clusterId: string; // "auto" | "all" | cluster id
  travelMode: TravelMode;
  ranking: "distance" | "duration";
  radiusKm: number;
  maxCandidates: number;
  liveOnly: boolean;
}

interface SearchState {
  origin: { lat: number; lng: number; source: SearchSource } | null;
  result: NearestHubResult | null;
  loading: boolean;
  error: string | null;
  /** Hub whose route is displayed (nearest by default, or an alternative the user picked). */
  selectedHubId: string | null;
  selectedRoute: Route | null;
  routeLoading: boolean;
  routeError: string | null;
  runSearch: (lat: number, lng: number, source: SearchSource, opts: SearchOptionsState, saveHistory: boolean) => Promise<NearestHubResult | null>;
  selectHub: (hubId: string) => Promise<void>;
  loadResult: (r: NearestHubResult) => void;
  clear: () => void;
}

const Ctx = createContext<SearchState | null>(null);

// Only the opaque result id is kept (per tab), so a page reload can re-open the latest search
// from the backend's short-lived in-memory cache. Coordinates are never written to browser storage.
const LAST_RESULT_KEY = "shf.lastResultId";
const storage = {
  get: () => {
    try {
      return sessionStorage.getItem(LAST_RESULT_KEY);
    } catch {
      return null;
    }
  },
  set: (v: string | null) => {
    try {
      if (v) sessionStorage.setItem(LAST_RESULT_KEY, v);
      else sessionStorage.removeItem(LAST_RESULT_KEY);
    } catch {
      /* storage unavailable: nothing to persist */
    }
  },
};

export function SearchProvider({ children }: { children: ReactNode }) {
  const { setSelectedClusterId } = useAppData();
  const [origin, setOrigin] = useState<SearchState["origin"]>(null);
  const [result, setResult] = useState<NearestHubResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedHubId, setSelectedHubId] = useState<string | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<Route | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const seq = useRef(0);

  const loadResult = useCallback(
    (r: NearestHubResult) => {
      setResult(r);
      setOrigin({ lat: r.query.latitude, lng: r.query.longitude, source: (r.query.source as SearchSource) ?? "manual" });
      setSelectedHubId(r.nearest?.hub_id ?? null);
      setSelectedRoute(r.route);
      setRouteError(r.route_status === "unavailable" ? r.route_error?.message ?? "Route unavailable" : null);
      setError(null);
      const cid = r.nearest?.cluster_id ?? r.location.cluster_id;
      if (cid) setSelectedClusterId(cid);
      storage.set(r.result_id);
    },
    [setSelectedClusterId],
  );

  useEffect(() => {
    const id = storage.get();
    if (!id) return;
    api
      .result(id)
      .then((r) => {
        if (seq.current === 0) loadResult(r); // don't override a search started meanwhile
      })
      .catch(() => storage.set(null));
  }, [loadResult]);

  const runSearch = useCallback<SearchState["runSearch"]>(
    async (lat, lng, source, opts, saveHistory) => {
      const my = ++seq.current;
      setLoading(true);
      setError(null);
      setOrigin({ lat, lng, source });
      const req: NearestHubRequest = {
        latitude: lat,
        longitude: lng,
        cluster_id: opts.clusterId,
        travel_mode: opts.travelMode,
        ranking: opts.ranking,
        max_radius_km: opts.radiusKm,
        max_candidates: opts.maxCandidates,
        live_only: opts.liveOnly,
        source,
        save_history: saveHistory,
      };
      try {
        const r = await api.nearestHub(req);
        if (my !== seq.current) return null; // a newer search superseded this one
        loadResult(r);
        return r;
      } catch (e) {
        if (my === seq.current) {
          setError((e as Error).message);
          setResult(null);
          setSelectedRoute(null);
          setSelectedHubId(null);
        }
        return null;
      } finally {
        if (my === seq.current) setLoading(false);
      }
    },
    [loadResult],
  );

  const selectHub = useCallback(
    async (hubId: string) => {
      if (!result || !origin) return;
      setSelectedHubId(hubId);
      setRouteError(null);
      if (hubId === result.nearest?.hub_id && result.route) {
        setSelectedRoute(result.route);
        return;
      }
      setRouteLoading(true);
      setSelectedRoute(null);
      try {
        const r = await api.route({
          origin_latitude: origin.lat,
          origin_longitude: origin.lng,
          hub_id: hubId,
          travel_mode: result.query.travel_mode,
          result_id: result.result_id,
        });
        setSelectedRoute(r.route);
      } catch (e) {
        setRouteError((e as Error).message);
      } finally {
        setRouteLoading(false);
      }
    },
    [result, origin],
  );

  const clear = useCallback(() => {
    seq.current++;
    storage.set(null);
    setOrigin(null);
    setResult(null);
    setError(null);
    setSelectedHubId(null);
    setSelectedRoute(null);
    setRouteError(null);
    setLoading(false);
  }, []);

  const value = useMemo<SearchState>(
    () => ({
      origin,
      result,
      loading,
      error,
      selectedHubId,
      selectedRoute,
      routeLoading,
      routeError,
      runSearch,
      selectHub,
      loadResult,
      clear,
    }),
    [origin, result, loading, error, selectedHubId, selectedRoute, routeLoading, routeError, runSearch, selectHub, loadResult, clear],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSearch(): SearchState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSearch must be used inside SearchProvider");
  return v;
}
