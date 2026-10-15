import { Download } from "lucide-react";
import { exportUrl } from "../../api/client";
import type { NearestHubResult } from "../../api/types";
import { fmtKm, fmtMinutes } from "../../lib/format";
import { LinkButton, cx } from "../ui";

/** Top-N reachable hubs ranked by road distance/time, with an inline route comparison. */
export function AlternativeHubs({
  result,
  selectedHubId,
  onSelect,
}: {
  result: NearestHubResult;
  selectedHubId: string | null;
  onSelect: (hubId: string) => void;
}) {
  const rows = result.ranking;
  if (!rows.length) return <p className="text-sm text-slate-500">No reachable hubs to compare.</p>;
  const maxKm = Math.max(...rows.map((r) => r.road_distance_km ?? 0), 0.001);
  const maxMin = Math.max(...rows.map((r) => r.duration_min ?? 0), 0.001);
  const byTime = result.query.ranking === "duration";

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-slate-500">
        Ranked by {byTime ? "road travel time" : "road distance"}. Select a hub to calculate and display its road route.
      </p>
      <ul className="space-y-1.5" aria-label="Alternative hubs">
        {rows.map((r) => {
          const selected = r.hub_id === selectedHubId;
          return (
            <li key={r.hub_id}>
              <button
                type="button"
                onClick={() => r.hub_id && onSelect(r.hub_id)}
                aria-pressed={selected}
                className={cx(
                  "w-full rounded-lg border px-3 py-2 text-left transition-colors",
                  selected ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500" : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50",
                )}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={cx(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white",
                      r.rank === 1 ? "bg-emerald-700" : "bg-sky-700",
                    )}
                  >
                    {r.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{r.display_name}</p>
                    <p className="truncate text-[11px] text-slate-500">
                      {r.cluster_name} · {r.status}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="tabular text-sm font-semibold text-ink">{fmtKm(r.road_distance_km)}</p>
                    <p className="tabular text-[11px] text-slate-500">{fmtMinutes(r.duration_min)}</p>
                  </div>
                </div>
                {/* Route comparison: one bar per measure, single colour, value labelled */}
                <div className="mt-2 grid grid-cols-[52px,1fr] items-center gap-x-2 gap-y-1 text-[10px] text-slate-500">
                  <span>Distance</span>
                  <span className="h-1.5 rounded-full bg-slate-100">
                    <span className="block h-1.5 rounded-full bg-[#2a78d6]" style={{ width: `${((r.road_distance_km ?? 0) / maxKm) * 100}%` }} />
                  </span>
                  <span>Time</span>
                  <span className="h-1.5 rounded-full bg-slate-100">
                    <span className="block h-1.5 rounded-full bg-[#eb6834]" style={{ width: `${((r.duration_min ?? 0) / maxMin) * 100}%` }} />
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-slate-400">Straight-line {fmtKm(r.straight_line_km)} (pre-filter only)</p>
              </button>
            </li>
          );
        })}
      </ul>
      {result.unreachable.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs text-red-800">
          <p className="font-semibold">{result.unreachable.length} hub(s) not reachable by road</p>
          <ul className="mt-1 space-y-0.5">
            {result.unreachable.slice(0, 5).map((u) => (
              <li key={u.hub_id}>
                {u.display_name}: {u.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        <LinkButton size="sm" icon={Download} href={exportUrl.csv("search", { result_id: result.result_id })} download>
          Results CSV
        </LinkButton>
        {selectedHubId && selectedHubId !== result.nearest?.hub_id && (
          <LinkButton size="sm" icon={Download} href={exportUrl.kml("route", { result_id: result.result_id, hub_id: selectedHubId })} download>
            Selected route KML
          </LinkButton>
        )}
      </div>
    </div>
  );
}
