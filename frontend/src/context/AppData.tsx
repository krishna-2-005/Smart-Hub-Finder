import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { AnalyticsOverview, Cluster, Health, Hub, Preferences, SettingsResponse } from "../api/types";

interface AppData {
  loading: boolean;
  error: string | null;
  health: Health | null;
  clusters: Cluster[];
  clustersById: Record<string, Cluster>;
  hubs: Hub[];
  hubsById: Record<string, Hub>;
  analytics: AnalyticsOverview | null;
  settings: SettingsResponse | null;
  preferences: Preferences | null;
  selectedClusterId: string | null;
  setSelectedClusterId: (id: string | null) => void;
  reload: () => Promise<void>;
  reloadSettings: () => Promise<void>;
  setSettings: (s: SettingsResponse) => void;
}

const Ctx = createContext<AppData | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [hubs, setHubs] = useState<Hub[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);

  const reloadSettings = useCallback(async () => {
    setSettings(await api.settings());
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const h = await api.health();
      setHealth(h);
      const s = await api.settings();
      setSettings(s);
      if (!h.dataset_ready) {
        setError(h.dataset_error ?? "The hub dataset is not loaded on the server.");
        return;
      }
      const [c, hb, an] = await Promise.all([api.clusters(), api.hubs(), api.analytics()]);
      setClusters(c.clusters);
      setHubs(hb.hubs);
      setAnalytics(an);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo<AppData>(() => {
    const clustersById = Object.fromEntries(clusters.map((c) => [c.cluster_id, c]));
    const hubsById = Object.fromEntries(hubs.filter((h) => h.hub_id).map((h) => [h.hub_id as string, h]));
    return {
      loading,
      error,
      health,
      clusters,
      clustersById,
      hubs,
      hubsById,
      analytics,
      settings,
      preferences: settings?.preferences ?? null,
      selectedClusterId,
      setSelectedClusterId,
      reload,
      reloadSettings,
      setSettings,
    };
  }, [loading, error, health, clusters, hubs, analytics, settings, selectedClusterId, reload, reloadSettings]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppData(): AppData {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAppData must be used inside AppDataProvider");
  return v;
}
