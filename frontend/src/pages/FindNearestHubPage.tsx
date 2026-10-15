import { ListOrdered, MapPinned, Navigation, Route as RouteIcon } from "lucide-react";
import { useEffect, useMemo, useRef, type ReactNode } from "react";
import { InteractiveMap, type FitTarget } from "../components/map/InteractiveMap";
import { AlternativeHubs } from "../components/results/AlternativeHubs";
import { NearestHubResult } from "../components/results/NearestHubResult";
import { RouteInformation } from "../components/results/RouteInformation";
import { CoordinateSearch } from "../components/search/CoordinateSearch";
import { CurrentLocationButton } from "../components/search/CurrentLocationButton";
import { SearchOptions } from "../components/search/SearchOptions";
import { Alert, Spinner } from "../components/ui";
import { useAppData } from "../context/AppData";
import { useSearchForm } from "../hooks/useSearchForm";
import { boundsOfPoints } from "../lib/geo";

function Section({ title, icon: Icon, children }: { title: string; icon: typeof Navigation; children: ReactNode }) {
  return (
    <section className="border-t border-slate-200 px-4 py-4 sm:px-5">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon className="h-4 w-4 text-slate-400" aria-hidden /> {title}
      </h2>
      {children}
    </section>
  );
}

export function FindNearestHubPage() {
  const { clusters, hubs, clustersById, error: dataError } = useAppData();
  const f = useSearchForm();
  const { result, loading, error, selectedHubId, selectedRoute, routeLoading, routeError, origin } = f.search;
  const resultsRef = useRef<HTMLDivElement>(null);

  // Bring a fresh result into view (the form fills the panel, especially on phones).
  useEffect(() => {
    if (result && !loading) resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [result?.result_id, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const fitTarget = useMemo<FitTarget | null>(() => {
    if (selectedRoute && origin) {
      const pts: [number, number][] = [...selectedRoute.geometry, [origin.lat, origin.lng]];
      const b = boundsOfPoints(pts);
      return b ? { key: `route-${result?.result_id}-${selectedHubId}`, bounds: b, maxZoom: 16 } : null;
    }
    if (result && origin) {
      const pts: [number, number][] = [[origin.lat, origin.lng], ...result.ranking.map((r) => [r.latitude, r.longitude] as [number, number])];
      const b = boundsOfPoints(pts);
      return b ? { key: `res-${result.result_id}`, bounds: b, maxZoom: 15 } : null;
    }
    if (f.options.clusterId !== "auto" && f.options.clusterId !== "all") {
      const c = clustersById[f.options.clusterId];
      if (c?.bbox) return { key: `cl-${c.cluster_id}`, bounds: [[c.bbox[0], c.bbox[1]], [c.bbox[2], c.bbox[3]]] };
    }
    return null;
  }, [selectedRoute, origin, result, selectedHubId, f.options.clusterId, clustersById]);

  const selectedName =
    result?.ranking.find((r) => r.hub_id === selectedHubId)?.display_name ??
    hubs.find((h) => h.hub_id === selectedHubId)?.display_name ??
    result?.nearest?.display_name;
  const highlight = f.options.clusterId !== "auto" && f.options.clusterId !== "all" ? f.options.clusterId : result?.nearest?.cluster_id ?? null;

  return (
    <div className="flex h-full flex-col-reverse lg:flex-row">
      <aside className="min-h-0 flex-1 overflow-y-auto bg-white lg:w-[440px] lg:flex-none lg:border-r lg:border-slate-200">
        <div className="space-y-4 px-4 py-4 sm:px-5">
          <div>
            <h1 className="text-base font-semibold text-ink">Find the nearest hub by road</h1>
            <p className="mt-0.5 text-xs text-slate-500">
              Enter coordinates, click the map, or share your location. Hubs are compared by real road distance from the routing engine — never by
              straight line.
            </p>
          </div>
          {dataError && <Alert tone="error">{dataError}</Alert>}
          <CurrentLocationButton
            geo={f.geo}
            onLocate={() => void f.locate()}
            onStartTracking={f.startTracking}
            disabled={loading && !f.geo.tracking}
            saveGps={f.saveGps}
            onSaveGpsChange={f.setSaveGps}
          />
          <div className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-wide text-slate-400">
            <span className="h-px flex-1 bg-slate-200" /> or enter coordinates <span className="h-px flex-1 bg-slate-200" />
          </div>
          <CoordinateSearch
            lat={f.lat}
            lng={f.lng}
            onLatChange={f.setLat}
            onLngChange={f.setLng}
            errors={f.errors}
            onSubmit={f.submit}
            onClear={result || f.lat || f.lng ? f.clear : undefined}
            loading={loading}
          >
            <SearchOptions
              value={f.options}
              onChange={f.setOptions}
              clusters={clusters}
              activeProvider={f.activeProvider}
              saveHistory={f.saveManual}
              onSaveHistoryChange={f.setSaveManual}
            />
          </CoordinateSearch>
          {!f.activeProvider && (
            <Alert tone="error" title="No routing provider available">
              Road routing is not configured, so nearest-hub search cannot run. Configure a provider in Settings.
            </Alert>
          )}
        </div>

        {loading && !result && (
          <div className="border-t border-slate-200 px-5 py-6">
            <Spinner label="Evaluating candidate hubs by road distance…" />
          </div>
        )}
        {error && (
          <div className="border-t border-slate-200 px-4 py-4 sm:px-5">
            <Alert tone="error" title="Search failed">
              {error}
            </Alert>
          </div>
        )}
        {result && (
          <div ref={resultsRef} className={loading ? "pointer-events-none scroll-mt-2 opacity-60 transition-opacity" : "scroll-mt-2 transition-opacity"} aria-busy={loading}>
            <Section title="Nearest hub" icon={MapPinned}>
              <NearestHubResult result={result} />
            </Section>
            {result.ranking.length > 0 && (
              <Section title={`Top ${result.ranking.length} reachable hubs`} icon={ListOrdered}>
                <AlternativeHubs result={result} selectedHubId={selectedHubId} onSelect={(id) => void f.search.selectHub(id)} />
              </Section>
            )}
            {(selectedRoute || routeLoading || routeError) && (
              <Section title="Road route & directions" icon={RouteIcon}>
                <RouteInformation route={selectedRoute} loading={routeLoading} error={routeError} hubName={selectedName} />
              </Section>
            )}
          </div>
        )}
      </aside>

      <div className="relative h-[42vh] shrink-0 lg:h-full lg:min-w-0 lg:flex-1">
        <InteractiveMap
          className="h-full"
          clusters={clusters}
          hubs={hubs}
          highlightClusterId={highlight}
          fitTarget={fitTarget}
          search={{ origin, result, selectedHubId, route: selectedRoute, tracking: f.geo.tracking }}
          onMapClick={(la, lo) => f.pick(la, lo)}
          pickedPoint={f.picked}
          onHubAction={result ? (h) => h.hub_id && void f.search.selectHub(h.hub_id) : undefined}
          hubActionLabel="Show road route from search location"
        />
        {!result && !loading && (
          <div className="pointer-events-none absolute left-1/2 top-3 z-[1000] -translate-x-1/2 rounded-full bg-slate-900/80 px-3 py-1.5 text-xs font-medium text-white shadow">
            Click anywhere on the map to set a search location
          </div>
        )}
      </div>
    </div>
  );
}
