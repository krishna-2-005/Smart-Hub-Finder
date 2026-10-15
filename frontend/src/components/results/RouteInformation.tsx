import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  CornerUpLeft,
  CornerUpRight,
  Flag,
  MoveUpLeft,
  MoveUpRight,
  Navigation2,
  RotateCcw,
  RotateCw,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import type { Route } from "../../api/types";
import { fmtKm, fmtMeters, fmtMinutes, fmtSecondsAsMin, travelModeLabel } from "../../lib/format";
import { Alert, Button, Spinner } from "../ui";

function maneuverIcon(m: string | null): LucideIcon {
  const s = (m ?? "").toLowerCase();
  if (s.includes("arrive")) return Flag;
  if (s.includes("depart")) return Navigation2;
  if (s.includes("roundabout") || s.includes("rotary")) return RotateCw;
  if (s.includes("uturn") || s.includes("u-turn") || s.includes("u turn")) return RotateCcw;
  if (s.includes("sharp left")) return CornerUpLeft;
  if (s.includes("sharp right")) return CornerUpRight;
  if (s.includes("slight left") || s.includes("fork left") || s.includes("ramp left") || s.includes("keep left")) return MoveUpLeft;
  if (s.includes("slight right") || s.includes("fork right") || s.includes("ramp right") || s.includes("keep right")) return MoveUpRight;
  if (s.includes("left")) return ArrowLeft;
  if (s.includes("right")) return ArrowRight;
  return ArrowUp;
}

export function RouteInformation({
  route,
  loading,
  error,
  hubName,
}: {
  route: Route | null;
  loading: boolean;
  error: string | null;
  hubName: string | null | undefined;
}) {
  const [showAll, setShowAll] = useState(false);
  if (loading) return <Spinner label="Calculating the road route…" />;
  if (error) return <Alert tone="error" title="Road route unavailable">{error}</Alert>;
  if (!route) return <p className="text-sm text-slate-500">No route to display.</p>;

  const steps = showAll ? route.steps : route.steps.slice(0, 8);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500">Distance</p>
          <p className="text-sm font-semibold">{fmtKm(route.distance_km)}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500">{travelModeLabel[route.travel_mode] ?? route.travel_mode}</p>
          <p className="text-sm font-semibold">{fmtMinutes(route.duration_min)}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500">Geometry</p>
          <p className="text-sm font-semibold">{route.point_count} pts</p>
        </div>
      </div>
      <p className="text-[11px] leading-snug text-slate-500">
        Road-following route to <b>{hubName}</b> from {route.provider_label}
        {route.traffic_aware ? " (traffic-aware)" : ""}
        {route.summary ? ` via ${route.summary}` : ""}.
        {route.origin_snap_m !== null && route.origin_snap_m > 30 && ` Starts ${fmtMeters(route.origin_snap_m)} from your point at the nearest road.`}
      </p>
      {route.alternatives.length > 0 && (
        <div className="rounded-lg border border-slate-200 p-2.5 text-xs">
          <p className="mb-1 font-semibold text-slate-600">Alternative road routes (dashed on map)</p>
          {route.alternatives.map((a, i) => (
            <p key={i} className="flex justify-between text-slate-600">
              <span>Alternative {i + 1}{a.summary ? ` via ${a.summary}` : ""}</span>
              <span className="tabular">
                {fmtKm(a.distance_km)} · {fmtMinutes(a.duration_min)}
              </span>
            </p>
          ))}
        </div>
      )}
      {route.steps.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Turn-by-turn directions</p>
          <ol className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {steps.map((s, i) => {
              const Icon = maneuverIcon(s.maneuver ?? s.instruction);
              return (
                <li key={i} className="flex items-start gap-2.5 px-3 py-2 text-[13px]">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-brand-700" aria-hidden />
                  <span className="flex-1 text-ink">{s.instruction}</span>
                  {s.distance_m > 0 && (
                    <span className="tabular shrink-0 text-xs text-slate-500">
                      {fmtMeters(s.distance_m)}
                      <span className="block text-right">{fmtSecondsAsMin(s.duration_s)}</span>
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
          {route.steps.length > 8 && (
            <Button variant="ghost" size="sm" className="mt-1" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Show fewer steps" : `Show all ${route.steps.length} steps`}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
