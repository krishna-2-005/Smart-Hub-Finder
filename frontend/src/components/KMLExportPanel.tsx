import { Download, Earth, ExternalLink, FileDown, FolderDown, MapPinned, Route as RouteIcon } from "lucide-react";
import { useState } from "react";
import { api, exportUrl } from "../api/client";
import { useAppData } from "../context/AppData";
import { useSearch } from "../context/SearchContext";
import { Alert, Badge, Button, Card, LinkButton } from "./ui";
import { ClusterSelector } from "./search/ClusterSelector";

function ExportRow({ title, description, href, disabled, disabledReason }: { title: string; description: string; href: string; disabled?: boolean; disabledReason?: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-slate-200 p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-ink">{title}</p>
        <p className="text-xs text-slate-500">{disabled && disabledReason ? disabledReason : description}</p>
      </div>
      {disabled ? (
        <Button size="sm" icon={Download} disabled>
          Download
        </Button>
      ) : (
        <LinkButton size="sm" icon={Download} href={href} download variant="primary">
          Download
        </LinkButton>
      )}
    </div>
  );
}

export function KMLExportPanel() {
  const { clusters, selectedClusterId } = useAppData();
  const { result, selectedHubId } = useSearch();
  const [clusterId, setClusterId] = useState(selectedClusterId ?? clusters[0]?.cluster_id ?? "");
  const [written, setWritten] = useState<string | null>(null);
  const [writing, setWriting] = useState(false);
  const hasRoute = Boolean(result?.route);
  const routeHub = selectedHubId && selectedHubId !== result?.nearest?.hub_id ? selectedHubId : undefined;

  const writeFiles = async () => {
    setWriting(true);
    try {
      const r = await api.generateExportFiles(result?.result_id, clusterId || undefined);
      setWritten(
        `${r.files.filter((f) => f.written).length} files written to ${r.directory}` +
          (r.files.some((f) => !f.written) ? ` (skipped: ${r.files.filter((f) => !f.written).map((f) => `${f.file} – ${f.reason}`).join("; ")})` : ""),
      );
    } catch (e) {
      setWritten(`Failed: ${(e as Error).message}`);
    } finally {
      setWriting(false);
    }
  };

  return (
    <div className="space-y-5">
      <Card title="Google Earth KML files" icon={Earth} subtitle="Styled, folder-organised KML: cluster colours, hub balloons with full metadata, road routes as LineStrings">
        <div className="space-y-2.5">
          <ExportRow title="all_hubs.kml" description="All hubs organised in one folder per cluster, coloured by cluster, with hub ID, coordinates and metadata." href={exportUrl.kml("all_hubs", { include_service_areas: true })} />
          <ExportRow title="all_clusters.kml" description="Cluster boundary polygons, labelled cluster centres with hub counts, and hubs per cluster." href={exportUrl.kml("all_clusters")} />
          <div className="rounded-lg border border-slate-200 p-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink">selected_cluster.kml</p>
                <p className="mb-2 text-xs text-slate-500">One cluster: boundary, centre, hubs and their service areas.</p>
                <ClusterSelector id="export-cluster" label="" value={clusterId} onChange={setClusterId} clusters={clusters} includeAuto={false} includeAll={false} />
              </div>
              <LinkButton size="sm" icon={Download} variant="primary" href={exportUrl.kml("selected_cluster", { cluster_id: clusterId, include_service_areas: true })} download>
                Download
              </LinkButton>
            </div>
          </div>
          <ExportRow
            title="nearest_hub_route.kml"
            description={`Search location, nearest hub${routeHub ? " (your selected alternative)" : ""}, the full road-following route (${result?.route?.point_count ?? 0} points) and ranked alternatives.`}
            href={exportUrl.kml("route", { result_id: result?.result_id, hub_id: routeHub })}
            disabled={!hasRoute}
            disabledReason="Run a nearest-hub search first (Find Nearest Hub) to export its road route."
          />
          <ExportRow
            title="company_demo.kml"
            description={`Complete network (all clusters, hubs, service lines)${hasRoute ? " plus the latest search and its road route" : ""}.`}
            href={exportUrl.kml("company_demo", { result_id: result?.result_id, include_service_areas: true })}
          />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
          <Button icon={FolderDown} onClick={() => void writeFiles()} loading={writing}>
            Write all 5 files to the project’s exports/ folder
          </Button>
          {written && <p className="text-xs text-slate-600">{written}</p>}
        </div>
      </Card>

      <Card title="Reports & GeoJSON" icon={FileDown}>
        <div className="flex flex-wrap gap-2">
          <LinkButton size="sm" icon={Download} href={exportUrl.csv("clusters")} download>
            Cluster summary CSV
          </LinkButton>
          <LinkButton size="sm" icon={Download} href={exportUrl.csv("hubs")} download>
            Hub directory CSV
          </LinkButton>
          {result ? (
            <LinkButton size="sm" icon={Download} href={exportUrl.csv("search", { result_id: result.result_id })} download>
              Nearest-hub results CSV
            </LinkButton>
          ) : (
            <Button size="sm" icon={Download} disabled title="Run a search first">
              Nearest-hub results CSV
            </Button>
          )}
          <LinkButton size="sm" icon={Download} href={exportUrl.geojson("hubs")} download>
            Hubs GeoJSON
          </LinkButton>
          <LinkButton size="sm" icon={Download} href={exportUrl.geojson("clusters")} download>
            Clusters GeoJSON
          </LinkButton>
          <LinkButton size="sm" icon={Download} href={exportUrl.geojson("service_areas")} download>
            Service areas GeoJSON
          </LinkButton>
          {hasRoute && (
            <LinkButton size="sm" icon={Download} href={exportUrl.geojson("route", { result_id: result!.result_id })} download>
              Route GeoJSON
            </LinkButton>
          )}
        </div>
      </Card>
    </div>
  );
}

export function GoogleEarthGuide() {
  const { result } = useSearch();
  const target = result?.nearest
    ? `https://earth.google.com/web/@${result.query.latitude.toFixed(6)},${result.query.longitude.toFixed(6)},500a,6000d,35y,0h,0t,0r`
    : "https://earth.google.com/web/@17.4300,78.4300,500a,45000d,35y,0h,0t,0r";
  return (
    <Card title="Import into Google Earth Web" icon={MapPinned} subtitle="earth.google.com/web runs in Chrome, Edge or Firefox">
      <ol className="space-y-3 text-sm">
        {[
          ["Download", "Download one of the KML files above (company_demo.kml shows everything)."],
          ["Open Google Earth Web", "Use the button below. It opens Earth already pointed at Hyderabad or at your search location."],
          ["Create a project", "In the left menu choose Projects → New project → Import KML file from computer. (If asked, enable ‘KML file import’ under Settings.)"],
          ["Select the file", "Pick the downloaded .kml. Earth flies to the data. Folders appear per cluster; click any hub for its ID, cluster, coordinates and metadata."],
          ["Present", "Toggle folders to show clusters, hubs, the road route (orange line) and alternatives. Use Present mode for a walkthrough."],
        ].map(([t, d], i) => (
          <li key={t} className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-700 text-xs font-bold text-white">{i + 1}</span>
            <span>
              <b>{t}.</b> {d}
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap gap-2">
        <LinkButton href={target} external icon={ExternalLink} variant="primary">
          Open Google Earth Web
        </LinkButton>
        {result?.links.google_maps && (
          <LinkButton href={result.links.google_maps} external icon={RouteIcon}>
            Open route in Google Maps
          </LinkButton>
        )}
      </div>
      <Alert tone="info" className="mt-4" title="What Google Earth Web can and cannot do">
        Google Earth Web displays the KML you import; it does not run this application’s search, GPS or routing, and it does not sync automatically.
        Re-export and re-import after a new search. <Badge tone="slate">KML 2.2</Badge>
      </Alert>
    </Card>
  );
}
