import { ArrowRight, BarChart3, Map as MapIcon, Navigation, ShieldAlert } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ClusterSummaryTable, HubsPerClusterChart } from "../components/analytics/ClusterAnalytics";
import { InteractiveMap, type FitTarget } from "../components/map/InteractiveMap";
import { AlternativeHubs } from "../components/results/AlternativeHubs";
import { NearestHubResult } from "../components/results/NearestHubResult";
import { CoordinateSearch } from "../components/search/CoordinateSearch";
import { CurrentLocationButton } from "../components/search/CurrentLocationButton";
import { SummaryCards } from "../components/SummaryCards";
import { Alert, Card, PageHeader, Spinner } from "../components/ui";
import { useAppData } from "../context/AppData";
import { useSearchForm } from "../hooks/useSearchForm";
import { boundsOfPoints } from "../lib/geo";

export function DashboardPage() {
  const { analytics, clusters, hubs, selectedClusterId, setSelectedClusterId, clustersById } = useAppData();
  const f = useSearchForm();
  const { result, loading, error, selectedHubId, selectedRoute, origin } = f.search;

  const fitTarget = useMemo<FitTarget | null>(() => {
    if (selectedRoute && origin) {
      const b = boundsOfPoints([...selectedRoute.geometry, [origin.lat, origin.lng]]);
      return b ? { key: `r-${result?.result_id}-${selectedHubId}`, bounds: b } : null;
    }
    if (selectedClusterId && clustersById[selectedClusterId]?.bbox) {
      const bb = clustersById[selectedClusterId].bbox!;
      return { key: `c-${selectedClusterId}`, bounds: [[bb[0], bb[1]], [bb[2], bb[3]]] };
    }
    return null;
  }, [selectedRoute, origin, result, selectedHubId, selectedClusterId, clustersById]);

  if (!analytics) return <div className="p-6"><Spinner /></div>;
  const q = analytics.totals;
  const issues = q.boundary_mismatches + q.isolated_hubs + q.duplicate_ids + q.invalid_locations;

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Hub network overview"
        description={`${analytics.dataset.file_name} · ${q.hubs} hubs in ${q.clusters} clusters across Hyderabad. Nearest-hub search uses real road distance.`}
      />
      <SummaryCards />

      <div className="grid gap-5 xl:grid-cols-3">
        <Card
          className="xl:col-span-2"
          title="Hub network map"
          subtitle="Cluster boundaries and hubs. Click a cluster to focus it."
          icon={MapIcon}
          actions={
            <Link to="/map" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline">
              Open live map <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
          bodyClassName="p-0"
        >
          <InteractiveMap
            className="h-[460px] rounded-b-xl sm:h-[540px]"
            clusters={clusters}
            hubs={hubs}
            highlightClusterId={selectedClusterId}
            fitTarget={fitTarget}
            onClusterClick={(id) => setSelectedClusterId(id)}
            search={{ origin, result, selectedHubId, route: selectedRoute, tracking: f.geo.tracking }}
            onHubAction={result ? (h) => h.hub_id && void f.search.selectHub(h.hub_id) : undefined}
            hubActionLabel="Show road route from search location"
          />
        </Card>

        <Card
          title="Nearest hub"
          subtitle="Real road distance from your location or any coordinate"
          icon={Navigation}
          actions={
            <Link to="/find" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline">
              Full view <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
        >
          <div className="space-y-4">
            <CurrentLocationButton
              geo={f.geo}
              onLocate={() => void f.locate()}
              onStartTracking={f.startTracking}
              saveGps={f.saveGps}
              onSaveGpsChange={f.setSaveGps}
            />
            <CoordinateSearch
              lat={f.lat}
              lng={f.lng}
              onLatChange={f.setLat}
              onLngChange={f.setLng}
              errors={f.errors}
              onSubmit={f.submit}
              onClear={result ? f.clear : undefined}
              loading={loading}
            />
            {error && <Alert tone="error" title="Search failed">{error}</Alert>}
            {result && (
              <div className={loading ? "opacity-60" : ""}>
                <NearestHubResult result={result} />
                {result.ranking.length > 1 && (
                  <div className="mt-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Alternative hubs</p>
                    <AlternativeHubs result={result} selectedHubId={selectedHubId} onSelect={(id) => void f.search.selectHub(id)} />
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Hubs per cluster" subtitle="Live vs inactive hubs (from the KML ‘Hub status’ attribute)" icon={BarChart3}>
          <HubsPerClusterChart data={analytics.hubs_per_cluster} selectedClusterId={selectedClusterId} onSelect={setSelectedClusterId} />
        </Card>
        <div className="space-y-5">
          <Card
            title="Cluster summary"
            subtitle="Click a row to focus the cluster on the map"
            actions={
              <Link to="/clusters" className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline">
                Cluster analysis <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            }
            bodyClassName="max-h-[430px] overflow-y-auto p-0"
          >
            <ClusterSummaryTable data={analytics.hubs_per_cluster} selectedClusterId={selectedClusterId} onSelect={setSelectedClusterId} compact />
          </Card>
          <Card title="Data quality" icon={ShieldAlert} actions={<Link to="/import" className="text-xs font-semibold text-brand-700 hover:underline">Details</Link>}>
            <p className="text-sm text-slate-600">
              {issues === 0 ? "No data-quality issues detected." : `${issues} items need review:`}{" "}
              {q.boundary_mismatches > 0 && <span>{q.boundary_mismatches} hubs outside their cluster boundary, </span>}
              {q.isolated_hubs > 0 && <span>{q.isolated_hubs} isolated hubs, </span>}
              {q.duplicate_ids} duplicate IDs, {q.invalid_locations} invalid coordinates. Hub locations are inferred from service-area polygons for{" "}
              {q.location_inferred} hubs.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
