import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import type { Cluster, ProviderStatus, TravelMode } from "../../api/types";
import type { SearchOptionsState } from "../../context/SearchContext";
import { travelModeLabel } from "../../lib/format";
import { Segmented, Toggle, cx } from "../ui";
import { ClusterSelector } from "./ClusterSelector";

export function SearchOptions({
  value,
  onChange,
  clusters,
  activeProvider,
  saveHistory,
  onSaveHistoryChange,
}: {
  value: SearchOptionsState;
  onChange: (v: SearchOptionsState) => void;
  clusters: Cluster[];
  activeProvider: ProviderStatus | undefined;
  saveHistory: boolean;
  onSaveHistoryChange: (v: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const modes: TravelMode[] = ["driving", "two_wheeler", "cycling", "walking"];
  const supported = new Set(activeProvider?.modes ?? []);

  return (
    <div className="space-y-3">
      <ClusterSelector id="search-cluster" value={value.clusterId} onChange={(clusterId) => onChange({ ...value, clusterId })} clusters={clusters} />
      <div>
        <span className="label mb-1">Travel mode</span>
        <Segmented
          ariaLabel="Travel mode"
          value={value.travelMode}
          onChange={(travelMode) => onChange({ ...value, travelMode })}
          options={modes.map((m) => ({
            value: m,
            label: travelModeLabel[m],
            disabled: activeProvider ? !supported.has(m) : false,
            title: activeProvider && !supported.has(m) ? `${activeProvider.label} does not support this mode` : undefined,
          }))}
        />
      </div>
      <div>
        <span className="label mb-1">Rank nearest hub by</span>
        <Segmented
          ariaLabel="Ranking criterion"
          value={value.ranking}
          onChange={(ranking) => onChange({ ...value, ranking })}
          options={[
            { value: "distance", label: "Shortest road distance" },
            { value: "duration", label: "Shortest travel time" },
          ]}
        />
      </div>

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-lg px-1 py-1 text-xs font-semibold text-slate-600 hover:text-ink"
        aria-expanded={open}
      >
        <span className="flex items-center gap-1.5">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Advanced options
        </span>
        <ChevronDown className={cx("h-4 w-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="radius" className="label mb-1">
                Search radius (km)
              </label>
              <input
                id="radius"
                type="number"
                min={0.5}
                max={200}
                step={0.5}
                className="input tabular"
                value={value.radiusKm}
                onChange={(e) => onChange({ ...value, radiusKm: Math.max(0.5, Number(e.target.value) || 0.5) })}
              />
            </div>
            <div>
              <label htmlFor="maxc" className="label mb-1">
                Max candidates
              </label>
              <input
                id="maxc"
                type="number"
                min={1}
                max={500}
                className="input tabular"
                value={value.maxCandidates}
                onChange={(e) => onChange({ ...value, maxCandidates: Math.max(1, Math.round(Number(e.target.value) || 1)) })}
              />
            </div>
          </div>
          <p className="text-[11px] leading-snug text-slate-500">
            The radius is a straight-line pre-filter only. Candidates inside it are compared by real road distance; the result says whether the
            answer is guaranteed.
          </p>
          <Toggle
            id="live-only"
            checked={value.liveOnly}
            onChange={(liveOnly) => onChange({ ...value, liveOnly })}
            label="Only live hubs"
            description="Exclude hubs whose KML status is ‘Not Live’ or ‘To be made live’."
          />
          <Toggle
            id="save-history"
            checked={saveHistory}
            onChange={onSaveHistoryChange}
            label="Save coordinate searches to route history"
            description="Stores the coordinates locally in SQLite. GPS locations have a separate consent option."
          />
        </div>
      )}
    </div>
  );
}
