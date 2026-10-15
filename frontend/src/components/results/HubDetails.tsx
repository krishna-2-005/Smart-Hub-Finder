import { AlertTriangle } from "lucide-react";
import type { Hub } from "../../api/types";
import { fmtCoord, fmtNum, locationMethodLabel } from "../../lib/format";
import { Badge, KeyValue, StatusBadge } from "../ui";

export function HubDetails({ hub, clusterColor }: { hub: Hub; clusterColor?: string }) {
  const meta = Object.entries(hub.metadata ?? {}).filter(([, v]) => v !== "" && v !== null);
  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-ink">{hub.display_name}</h3>
          <StatusBadge status={hub.status} active={hub.is_active} />
          {hub.location_inferred && (
            <Badge tone="violet" title="No explicit hub point exists in the KML; the location is derived from the service-area polygon">
              Inferred location
            </Badge>
          )}
        </div>
        <p className="mt-0.5 font-mono text-xs text-slate-500">{hub.hub_id}</p>
      </div>
      <KeyValue
        items={[
          ["Hub name (KML)", hub.name],
          ["Hub code", hub.hub_code ?? "—"],
          [
            "Cluster",
            <span key="c" className="inline-flex items-center gap-1.5">
              {clusterColor && <span className="h-2.5 w-2.5 rounded-full" style={{ background: clusterColor }} />}
              {hub.cluster_name ?? "Unassigned"}
            </span>,
          ],
          ["Region / Line", hub.region ?? "—"],
          ["Hub type", hub.hub_type ?? "Not in source data"],
          ["Cluster mapping", hub.cluster_mapping ?? "—"],
          ["Priority", hub.priority ?? "—"],
          ["Demand level", hub.demand_level ?? "—"],
          ["Latitude, longitude", `${fmtCoord(hub.latitude)}, ${fmtCoord(hub.longitude)}`],
          ["Location method", locationMethodLabel[hub.location_method ?? ""] ?? hub.location_method ?? "—"],
          ["Service area", hub.service_area_km2 !== null ? `${fmtNum(hub.service_area_km2, 3)} km²` : "—"],
          ["Original KML folder", hub.original_folder ?? "—"],
          ["KML source line", hub.source_line ?? "—"],
        ]}
      />
      {hub.issues.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="mb-1 flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="h-3.5 w-3.5" /> Data quality notes
          </p>
          <ul className="list-disc space-y-0.5 pl-4">
            {hub.issues.map((i, k) => (
              <li key={k}>{i}</li>
            ))}
          </ul>
        </div>
      )}
      {meta.length > 0 && (
        <details className="rounded-lg border border-slate-200">
          <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-slate-600">All KML attributes ({meta.length})</summary>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 border-t border-slate-100 px-3 py-2 text-xs sm:grid-cols-[minmax(0,1fr),minmax(0,1.4fr)]">
            {meta.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="truncate text-slate-500" title={k}>
                  {k}
                </dt>
                <dd className="break-words text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
