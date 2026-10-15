import { Filter, PanelLeftClose, PanelLeftOpen, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { InteractiveMap, type FitTarget } from "../components/map/InteractiveMap";
import { ClusterDot, cx } from "../components/ui";
import { useAppData } from "../context/AppData";
import { useSearch } from "../context/SearchContext";

export function LiveMapPage() {
  const { clusters, hubs, clustersById, selectedClusterId, setSelectedClusterId } = useAppData();
  const search = useSearch();
  const [visible, setVisible] = useState<Set<string> | null>(null); // null = all clusters
  const [panelOpen, setPanelOpen] = useState(true);
  const [filter, setFilter] = useState("");
  const [hubQuery, setHubQuery] = useState("");
  const [fitTarget, setFitTarget] = useState<FitTarget | null>(null);

  const sorted = useMemo(() => [...clusters].sort((a, b) => a.display_name.localeCompare(b.display_name)), [clusters]);
  const shown = sorted.filter((c) => c.display_name.toLowerCase().includes(filter.toLowerCase()));
  const isOn = (id: string) => !visible || visible.has(id);

  const toggle = (id: string) => {
    const next = new Set(visible ?? clusters.map((c) => c.cluster_id));
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setVisible(next.size === clusters.length ? null : next);
  };

  const focus = (id: string) => {
    setSelectedClusterId(id);
    const bb = clustersById[id]?.bbox;
    if (bb) setFitTarget({ key: `c-${id}-${Date.now()}`, bounds: [[bb[0], bb[1]], [bb[2], bb[3]]] });
    if (visible && !visible.has(id)) setVisible(new Set([...visible, id]));
  };

  const hubMatches = useMemo(() => {
    const q = hubQuery.trim().toLowerCase();
    if (q.length < 2) return [];
    return hubs
      .filter((h) => [h.display_name, h.name, h.hub_id, h.cluster_name].some((v) => (v ?? "").toLowerCase().includes(q)))
      .slice(0, 8);
  }, [hubQuery, hubs]);

  const visibleHubCount = hubs.filter((h) => !visible || (h.cluster_id && visible.has(h.cluster_id))).length;

  return (
    <div className="relative flex h-full">
      <aside
        className={cx(
          "absolute inset-y-0 left-0 z-[1001] flex w-72 flex-col border-r border-slate-200 bg-white shadow-pop transition-transform lg:static lg:shadow-none",
          panelOpen ? "translate-x-0" : "-translate-x-full lg:hidden",
        )}
        aria-label="Map filters"
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Filter className="h-4 w-4 text-slate-400" /> Cluster filters
          </p>
          <button className="rounded p-1 text-slate-400 hover:bg-slate-100" onClick={() => setPanelOpen(false)} aria-label="Hide filters">
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3 border-b border-slate-100 p-4">
          <div className="relative">
            <label htmlFor="hub-find" className="label mb-1">
              Find a hub (name, ID or cluster)
            </label>
            <Search className="pointer-events-none absolute left-2.5 top-[30px] h-4 w-4 text-slate-400" />
            <input id="hub-find" className="input pl-8" placeholder="e.g. lanco hills" value={hubQuery} onChange={(e) => setHubQuery(e.target.value)} />
            {hubMatches.length > 0 && (
              <ul className="absolute left-0 right-0 top-full z-10 mt-1 max-h-64 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-pop">
                {hubMatches.map((h) => (
                  <li key={h.hub_id}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
                      onClick={() => {
                        if (h.latitude === null || h.longitude === null) return;
                        const d = 0.004;
                        setFitTarget({ key: `h-${h.hub_id}-${Date.now()}`, bounds: [[h.latitude - d, h.longitude - d], [h.latitude + d, h.longitude + d]], maxZoom: 16 });
                        if (h.cluster_id) setSelectedClusterId(h.cluster_id);
                        setHubQuery("");
                      }}
                    >
                      <ClusterDot color={clustersById[h.cluster_id ?? ""]?.color ?? "#64748b"} />
                      <span className="min-w-0 flex-1 truncate">{h.display_name}</span>
                      <span className="text-[11px] text-slate-400">{h.cluster_name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <input className="input" placeholder="Filter cluster list…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter cluster list" />
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">
              {visible ? visible.size : clusters.length} of {clusters.length} clusters · {visibleHubCount} hubs
            </span>
            <span className="flex gap-2">
              <button className="font-semibold text-brand-700 hover:underline" onClick={() => setVisible(null)}>
                All
              </button>
              <button className="font-semibold text-brand-700 hover:underline" onClick={() => setVisible(new Set())}>
                None
              </button>
            </span>
          </div>
        </div>
        <ul className="flex-1 overflow-y-auto py-1">
          {shown.map((c) => (
            <li key={c.cluster_id} className={cx("flex items-center gap-2 px-4 py-1.5", selectedClusterId === c.cluster_id && "bg-brand-50")}>
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
                checked={isOn(c.cluster_id)}
                onChange={() => toggle(c.cluster_id)}
                aria-label={`Show ${c.display_name}`}
              />
              <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm hover:text-brand-700" onClick={() => focus(c.cluster_id)} title="Zoom to cluster">
                <ClusterDot color={c.color} />
                <span className="truncate">{c.display_name}</span>
              </button>
              <span className="tabular text-xs text-slate-500">{c.hub_count}</span>
            </li>
          ))}
        </ul>
        {selectedClusterId && (
          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2.5 text-xs">
            <span>
              Focused: <b>{clustersById[selectedClusterId]?.display_name}</b>
            </span>
            <button className="flex items-center gap-1 text-slate-500 hover:text-ink" onClick={() => setSelectedClusterId(null)}>
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          </div>
        )}
      </aside>

      <div className="relative min-w-0 flex-1">
        {!panelOpen && (
          <button
            className="absolute left-3 top-3 z-[1000] flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold shadow-pop"
            onClick={() => setPanelOpen(true)}
          >
            <PanelLeftOpen className="h-4 w-4" /> Filters
          </button>
        )}
        <InteractiveMap
          className="h-full"
          clusters={clusters}
          hubs={hubs}
          visibleClusterIds={visible}
          highlightClusterId={selectedClusterId}
          fitTarget={fitTarget}
          onClusterClick={focus}
          search={search.result ? { origin: search.origin, result: search.result, selectedHubId: search.selectedHubId, route: search.selectedRoute } : null}
          initialLayers={{ centers: true }}
        />
      </div>
    </div>
  );
}
