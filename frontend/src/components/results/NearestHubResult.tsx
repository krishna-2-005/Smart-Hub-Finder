import { Clock, Download, ExternalLink, MapPin, Navigation, Route as RouteIcon, ShieldAlert, ShieldCheck } from "lucide-react";
import { exportUrl } from "../../api/client";
import type { NearestHubResult as Result } from "../../api/types";
import { fmtCoord, fmtKm, fmtMinutes, rankingLabel, strategyLabel, travelModeLabel } from "../../lib/format";
import { Alert, Badge, KeyValue, LinkButton } from "../ui";

const STATUS_TITLE: Record<string, string> = {
  no_eligible_hubs: "No eligible hubs",
  no_hubs_in_radius: "No hubs within the search radius",
  routing_unavailable: "Road routing unavailable",
  no_reachable_hubs: "No reachable hubs",
};

export function NearestHubResult({ result }: { result: Result }) {
  const n = result.nearest;
  const ev = result.evaluation;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <Badge tone={result.location.within_coverage ? "blue" : "amber"}>
          <MapPin className="h-3 w-3" /> {result.location.detection_label}
        </Badge>
        {result.scope.fallback && <Badge tone="amber">Fallback: all clusters</Badge>}
      </div>
      {result.scope.fallback && (
        <Alert tone="warning" title="Outside cluster coverage">
          {result.scope.description}
        </Alert>
      )}

      {result.status !== "ok" || !n ? (
        <>
          <Alert tone={result.status === "routing_unavailable" ? "error" : "warning"} title={STATUS_TITLE[result.status] ?? "No result"}>
            {result.message}
          </Alert>
          {result.candidates_preview && (
            <div className="rounded-lg border border-dashed border-slate-300 p-3">
              <p className="mb-1.5 text-xs font-semibold text-slate-600">{result.candidates_preview.label}</p>
              <ul className="space-y-1 text-xs text-slate-600">
                {result.candidates_preview.hubs.map((h) => (
                  <li key={h.hub_id} className="flex justify-between gap-2">
                    <span className="truncate">{h.display_name}</span>
                    <span className="tabular text-slate-400">{fmtKm(h.straight_line_km)} straight-line</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-slate-500">These are not road distances and are not used to pick a hub.</p>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
              Nearest {result.query.live_only ? "live " : ""}hub · {rankingLabel[result.query.ranking].toLowerCase()}
            </p>
            <p className="mt-1 text-lg font-semibold leading-tight text-ink">{n.display_name}</p>
            <p className="mt-0.5 text-xs text-slate-500">
              {n.cluster_name} cluster · ID <span className="font-mono">{n.hub_id}</span>
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-white p-2.5 ring-1 ring-emerald-100">
                <p className="flex items-center gap-1 text-[11px] font-medium text-slate-500">
                  <RouteIcon className="h-3.5 w-3.5" /> Road distance
                </p>
                <p className="text-2xl font-semibold text-ink">{fmtKm(result.route?.distance_km ?? n.road_distance_km)}</p>
              </div>
              <div className="rounded-lg bg-white p-2.5 ring-1 ring-emerald-100">
                <p className="flex items-center gap-1 text-[11px] font-medium text-slate-500">
                  <Clock className="h-3.5 w-3.5" /> Est. {travelModeLabel[result.query.travel_mode].toLowerCase()} time
                </p>
                <p className="text-2xl font-semibold text-ink">{fmtMinutes(result.route?.duration_min ?? n.duration_min)}</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {result.links.google_maps && (
                <LinkButton href={result.links.google_maps} external variant="primary" icon={Navigation} size="sm">
                  Navigate in Google Maps
                </LinkButton>
              )}
              <LinkButton href={exportUrl.kml("route", { result_id: result.result_id })} download icon={Download} size="sm">
                Export route KML
              </LinkButton>
              {result.links.google_earth_destination && (
                <LinkButton href={result.links.google_earth_destination} external icon={ExternalLink} size="sm" variant="ghost">
                  Google Earth
                </LinkButton>
              )}
            </div>
          </div>

          <KeyValue
            className="text-[13px]"
            items={[
              ["Hub coordinates", `${fmtCoord(n.latitude)}, ${fmtCoord(n.longitude)}`],
              ["Your coordinates", `${fmtCoord(result.query.latitude)}, ${fmtCoord(result.query.longitude)}`],
              ["Selected cluster", result.scope.cluster_ids?.length === 1 ? n.cluster_name : result.scope.selection === "all" ? "All clusters" : "All (fallback)"],
              ["Ranking criterion", rankingLabel[result.query.ranking]],
              ["Candidates evaluated", `${ev.candidates_evaluated} of ${ev.candidates_within_radius} in radius`],
              ["Route provider", result.provider?.label ?? "—"],
              ["Route status", result.route_status === "available" ? "Road route available" : `Unavailable${result.route_error ? `: ${result.route_error.message}` : ""}`],
            ]}
          />

          <div className={`flex gap-2 rounded-lg border px-3 py-2 text-xs ${ev.guaranteed ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
            {ev.guaranteed ? <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" /> : <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />}
            <div>
              <p className="font-semibold">
                {ev.guaranteed ? "Guaranteed nearest within the search radius" : "Shortlist result — not guaranteed"} · {strategyLabel(ev.strategy)}
              </p>
              <p className="mt-0.5 leading-snug opacity-90">{ev.explanation}</p>
              {ev.excluded_inactive > 0 && <p className="mt-0.5 opacity-90">{ev.excluded_inactive} inactive hub(s) excluded.</p>}
            </div>
          </div>
        </>
      )}

      {result.warnings.map((w, i) => (
        <Alert key={i} tone="warning">
          {w}
        </Alert>
      ))}
    </div>
  );
}
