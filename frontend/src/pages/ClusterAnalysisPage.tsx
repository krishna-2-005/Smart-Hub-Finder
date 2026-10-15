import { BarChart3, Download, Layers3, ListChecks, Map as MapIcon, Maximize2, PieChart, Ruler, Table2 } from "lucide-react";
import { useMemo } from "react";
import { exportUrl } from "../api/client";
import { BarList, ClusterSummaryTable, HubsPerClusterChart, MissingDataIndicators } from "../components/analytics/ClusterAnalytics";
import { InteractiveMap, type FitTarget } from "../components/map/InteractiveMap";
import { ClusterSelector } from "../components/search/ClusterSelector";
import { Card, ClusterDot, KeyValue, LinkButton, PageHeader, Spinner, StatTile, StatusBadge } from "../components/ui";
import { useAppData } from "../context/AppData";
import { fmtCoord, fmtNum } from "../lib/format";

const REGION_LABELS: Record<string, string> = { southern_hyd: "Southern Hyderabad", northern_hyd: "Northern Hyderabad", eastern_hyd: "Eastern Hyderabad" };

export function ClusterAnalysisPage() {
  const { analytics, clusters, hubs, clustersById, selectedClusterId, setSelectedClusterId } = useAppData();
  const selected = selectedClusterId ? clustersById[selectedClusterId] : null;

  const fitTarget = useMemo<FitTarget | null>(() => {
    if (selected?.bbox) {
      const b = selected.bbox;
      return { key: `c-${selected.cluster_id}`, bounds: [[b[0], b[1]], [b[2], b[3]]] };
    }
    const all = clusters.flatMap((c) => (c.bbox ? [c.bbox] : []));
    if (!all.length) return null;
    return {
      key: "all",
      bounds: [
        [Math.min(...all.map((b) => b[0])), Math.min(...all.map((b) => b[1]))],
        [Math.max(...all.map((b) => b[2])), Math.max(...all.map((b) => b[3]))],
      ],
    };
  }, [selected, clusters]);

  const members = useMemo(
    () => (selected ? hubs.filter((h) => h.cluster_id === selected.cluster_id).sort((a, b) => (a.display_name ?? "").localeCompare(b.display_name ?? "")) : []),
    [selected, hubs],
  );

  if (!analytics) return <div className="p-6"><Spinner /></div>;
  const stats = analytics.hubs_per_cluster;
  const largest = [...stats].sort((a, b) => b.hub_count - a.hub_count)[0];
  const smallest = [...stats].sort((a, b) => a.hub_count - b.hub_count)[0];
  const t = analytics.totals;

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Cluster analysis"
        description={`Cluster method: ${analytics.dataset.cluster_method}. Hub counts, geographic coverage and data completeness per cluster.`}
        actions={
          <>
            <LinkButton href={exportUrl.csv("clusters")} download icon={Download} size="sm">
              Cluster summary CSV
            </LinkButton>
            <LinkButton href={exportUrl.kml("all_clusters")} download icon={Download} size="sm">
              All clusters KML
            </LinkButton>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile icon={Layers3} label="Clusters" value={t.clusters} hint={`${t.hubs} hubs · ${t.unassigned_hubs} unassigned`} />
        <StatTile icon={Maximize2} label="Largest cluster" value={largest?.display_name} hint={`${largest?.hub_count} hubs`} accent="text-violet-700 bg-violet-50" />
        <StatTile icon={Ruler} label="Smallest cluster" value={smallest?.display_name} hint={`${smallest?.hub_count} hub${smallest?.hub_count === 1 ? "" : "s"}`} accent="text-amber-700 bg-amber-50" />
        <StatTile
          icon={MapIcon}
          label="Area covered"
          value={`${fmtNum(analytics.coverage.total_boundary_area_km2, 0)} km²`}
          hint={`Cluster boundaries · hub service areas ${fmtNum(analytics.coverage.total_service_area_km2, 0)} km²`}
          accent="text-emerald-700 bg-emerald-50"
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-2" title="Hubs per cluster" subtitle="Click a bar to select the cluster" icon={BarChart3}>
          <HubsPerClusterChart data={stats} selectedClusterId={selectedClusterId} onSelect={setSelectedClusterId} />
        </Card>
        <div className="space-y-5 xl:col-span-3">
          <Card
            title="Geographic cluster distribution"
            subtitle="Selecting a cluster zooms the map to its extent and highlights its hubs"
            icon={MapIcon}
            actions={
              <div className="w-56">
                <ClusterSelector
                  id="analysis-cluster"
                  label=""
                  value={selectedClusterId ?? "all"}
                  onChange={(v) => setSelectedClusterId(v === "all" ? null : v)}
                  clusters={clusters}
                  includeAuto={false}
                />
              </div>
            }
            bodyClassName="p-0"
          >
            <InteractiveMap
              className="h-[420px] rounded-b-xl"
              clusters={clusters}
              hubs={hubs}
              highlightClusterId={selectedClusterId}
              fitTarget={fitTarget}
              onClusterClick={setSelectedClusterId}
              initialLayers={{ labels: true }}
              showLegend={false}
            />
          </Card>
          {selected && (
            <Card
              title={
                <span className="flex items-center gap-2">
                  <ClusterDot color={selected.color} /> {selected.display_name}
                </span>
              }
              subtitle={`${selected.hub_count} hubs · ${selected.active_hub_count} live`}
              actions={
                <>
                  <LinkButton size="sm" icon={Download} href={exportUrl.kml("selected_cluster", { cluster_id: selected.cluster_id, include_service_areas: true })} download>
                    KML
                  </LinkButton>
                  <LinkButton size="sm" icon={Download} href={exportUrl.csv("hubs", { cluster_id: selected.cluster_id })} download>
                    CSV
                  </LinkButton>
                </>
              }
            >
              <div className="grid gap-5 2xl:grid-cols-2">
                <KeyValue
                  className="text-[13px]"
                  items={[
                    ["Center", `${fmtCoord(selected.center_lat, 5)}, ${fmtCoord(selected.center_lng, 5)}`],
                    ["Center method", selected.center_method === "boundary_centroid" ? "Boundary centroid" : "Mean of hub locations"],
                    ["Boundary area", `${fmtNum(selected.boundary_area_km2, 2)} km²`],
                    ["Service-area coverage", `${fmtNum(selected.service_area_union_km2, 2)} km²`],
                    ["Spread from center (straight-line)", `${fmtNum(selected.max_hub_distance_km, 2)} km`],
                    ["Mean hub spacing (straight-line)", `${fmtNum(selected.mean_nearest_neighbor_km, 2)} km`],
                    ["Extent (lat)", selected.bbox ? `${selected.bbox[0].toFixed(4)} – ${selected.bbox[2].toFixed(4)}` : "—"],
                    ["Extent (lng)", selected.bbox ? `${selected.bbox[1].toFixed(4)} – ${selected.bbox[3].toFixed(4)}` : "—"],
                    ["Spellings in source", selected.name_variants.join(", ")],
                    ["Hubs outside boundary", selected.hubs_outside_boundary.length ? selected.hubs_outside_boundary.length : "None"],
                  ]}
                />
                <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-200">
                  <table className="table-base">
                    <thead>
                      <tr>
                        <th>Hub</th>
                        <th>Status</th>
                        <th>Region</th>
                      </tr>
                    </thead>
                    <tbody>
                      {members.map((h) => (
                        <tr key={h.hub_id}>
                          <td className="font-medium">{h.display_name}</td>
                          <td>
                            <StatusBadge status={h.status} active={h.is_active} />
                          </td>
                          <td className="text-xs text-slate-500">{REGION_LABELS[h.region ?? ""] ?? h.region}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      <Card title="Cluster summary table" subtitle="Distances are straight-line geographic measures for coverage analysis, not road distances" icon={Table2} bodyClassName="p-0">
        <ClusterSummaryTable data={stats} selectedClusterId={selectedClusterId} onSelect={setSelectedClusterId} />
      </Card>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Hubs by service line" icon={PieChart}>
          <BarList data={analytics.region_counts} total={t.hubs} labels={REGION_LABELS} />
        </Card>
        <Card title="Hubs by cluster mapping" icon={PieChart}>
          <BarList data={analytics.cluster_mapping_counts} total={t.hubs} labels={{ competitive_cluster: "Competitive cluster", non_competitive_cluster: "Non-competitive cluster" }} />
        </Card>
        <Card title="Hubs by operational status" icon={PieChart}>
          <BarList data={analytics.status_counts} total={t.hubs} />
        </Card>
        <Card title="Missing-data indicators" subtitle="Share of hubs with each field filled" icon={ListChecks}>
          <MissingDataIndicators data={analytics.missing_data} />
        </Card>
      </div>
    </div>
  );
}
