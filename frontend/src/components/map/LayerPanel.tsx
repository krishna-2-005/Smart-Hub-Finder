import { Layers, X } from "lucide-react";
import { useState } from "react";
import { cx } from "../ui";

export type BaseLayer = "light" | "streets" | "satellite";

export interface LayerState {
  base: BaseLayer;
  clusters: boolean;
  labels: boolean;
  hubs: boolean;
  centers: boolean;
  serviceAreas: boolean;
  regions: boolean;
  demand: boolean;
  competitors: boolean;
}

export const DEFAULT_LAYERS: LayerState = {
  base: "light",
  clusters: true,
  labels: false,
  hubs: true,
  centers: false,
  serviceAreas: false,
  regions: false,
  demand: false,
  competitors: false,
};

const OVERLAYS: { key: keyof Omit<LayerState, "base">; label: string; hint?: string }[] = [
  { key: "clusters", label: "Cluster boundaries" },
  { key: "labels", label: "Cluster name labels" },
  { key: "hubs", label: "Hubs" },
  { key: "centers", label: "Cluster centers" },
  { key: "serviceAreas", label: "Hub service areas", hint: "Polygons from the KML" },
  { key: "regions", label: "Service lines (South / East / North)" },
  { key: "demand", label: "Demand hotspots (PMF)", hint: "1,700+ points" },
  { key: "competitors", label: "Competitor locations" },
];

export function LayerPanel({ value, onChange }: { value: LayerState; onChange: (v: LayerState) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="absolute right-3 top-3 z-[1000]">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-ink shadow-pop hover:bg-slate-50"
          aria-label="Map layers"
        >
          <Layers className="h-4 w-4" aria-hidden /> Layers
        </button>
      ) : (
        <div className="w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-pop">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Base map</p>
            <button type="button" onClick={() => setOpen(false)} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close layers">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-0.5" role="radiogroup" aria-label="Base map">
            {(["light", "streets", "satellite"] as BaseLayer[]).map((b) => (
              <button
                key={b}
                type="button"
                role="radio"
                aria-checked={value.base === b}
                onClick={() => onChange({ ...value, base: b })}
                className={cx(
                  "rounded-md py-1 text-xs font-medium capitalize",
                  value.base === b ? "bg-white text-ink shadow-sm" : "text-slate-600 hover:text-ink",
                )}
              >
                {b}
              </button>
            ))}
          </div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Overlays</p>
          <div className="space-y-1">
            {OVERLAYS.map((o) => (
              <label key={o.key} className="flex cursor-pointer items-start gap-2 rounded-md px-1 py-1 hover:bg-slate-50">
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
                  checked={value[o.key]}
                  onChange={(e) => onChange({ ...value, [o.key]: e.target.checked })}
                />
                <span className="text-sm leading-tight text-ink">
                  {o.label}
                  {o.hint && <span className="block text-[11px] text-slate-500">{o.hint}</span>}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
