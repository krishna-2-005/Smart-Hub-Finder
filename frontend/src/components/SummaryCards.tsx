import { Building2, CircleDashed, Layers3, MapPinCheck, Navigation, Target } from "lucide-react";
import { useAppData } from "../context/AppData";
import { useSearch } from "../context/SearchContext";
import { fmtKm, fmtMinutes, pct } from "../lib/format";
import { StatTile } from "./ui";

export function SummaryCards() {
  const { analytics, clustersById, selectedClusterId } = useAppData();
  const { result, selectedRoute } = useSearch();
  if (!analytics) return null;
  const t = analytics.totals;
  const selected = selectedClusterId ? clustersById[selectedClusterId] : null;
  const nearest = result?.nearest;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
      <StatTile icon={Building2} label="Total hubs" value={t.hubs} hint={`${t.active_hubs} live · ${t.inactive_hubs} inactive`} />
      <StatTile icon={Layers3} label="Total clusters" value={t.clusters} hint={`${(t.hubs / Math.max(t.clusters, 1)).toFixed(1)} hubs per cluster on average`} accent="text-violet-700 bg-violet-50" />
      <StatTile
        icon={MapPinCheck}
        label="Valid locations"
        value={`${t.valid_locations}`}
        hint={`${pct(t.valid_locations, t.hubs)}% of hubs · ${t.invalid_locations} invalid`}
        accent="text-emerald-700 bg-emerald-50"
      />
      <StatTile
        icon={CircleDashed}
        label="Unassigned hubs"
        value={t.unassigned_hubs}
        hint={t.unassigned_hubs ? "Hubs without a cluster" : "Every hub has a cluster"}
        accent="text-slate-700 bg-slate-100"
      />
      <StatTile
        icon={Target}
        label="Selected cluster"
        value={selected ? selected.display_name : "None"}
        hint={selected ? `${selected.hub_count} hubs · ${selected.active_hub_count} live` : "Select a cluster or run a search"}
        accent="text-sky-700 bg-sky-50"
      />
      <StatTile
        icon={Navigation}
        label="Nearest hub distance"
        value={nearest ? fmtKm(selectedRoute?.hub_id === nearest.hub_id ? selectedRoute.distance_km : nearest.road_distance_km) : "—"}
        hint={nearest ? `${nearest.display_name} · ${fmtMinutes(nearest.duration_min)} by road` : "Run a nearest-hub search"}
        accent="text-orange-700 bg-orange-50"
      />
    </div>
  );
}
