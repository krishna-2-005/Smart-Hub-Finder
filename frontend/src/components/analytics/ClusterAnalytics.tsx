import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import type { AnalyticsOverview, ClusterStat } from "../../api/types";
import { fmtNum, pct } from "../../lib/format";
import { ClusterDot, cx } from "../ui";

// Validated categorical slots (dataviz reference palette, light surface).
export const SERIES = { live: "#2a78d6", inactive: "#eb6834", single: "#2a78d6" };
const INK_MUTED = "#64748b";
const GRID = "#e2e8f0";

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((s, p) => s + (Number(p.value) || 0), 0);
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-pop">
      <p className="mb-1 font-semibold text-ink">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey as string} className="flex items-center justify-between gap-4 text-slate-600">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-sm" style={{ background: p.color }} />
            {p.name}
          </span>
          <span className="tabular font-medium text-ink">{p.value}</span>
        </p>
      ))}
      <p className="mt-1 flex justify-between gap-4 border-t border-slate-100 pt-1 text-slate-600">
        <span>Total hubs</span>
        <span className="tabular font-semibold text-ink">{total}</span>
      </p>
    </div>
  );
}

function selectFromBar(item: unknown, onSelect?: (id: string) => void) {
  const id = (item as { payload?: { cluster_id?: string } }).payload?.cluster_id;
  if (id) onSelect?.(id);
}

/** Horizontal stacked bars: live vs inactive hubs per cluster, sorted by size. */
export function HubsPerClusterChart({
  data,
  selectedClusterId,
  onSelect,
  maxRows,
}: {
  data: ClusterStat[];
  selectedClusterId?: string | null;
  onSelect?: (clusterId: string) => void;
  maxRows?: number;
}) {
  const rows = useMemo(
    () =>
      [...data]
        .sort((a, b) => b.hub_count - a.hub_count || a.display_name.localeCompare(b.display_name))
        .slice(0, maxRows ?? data.length)
        .map((c) => ({ ...c, label: c.display_name })),
    [data, maxRows],
  );
  const height = rows.length * 24 + 56;
  return (
    <div style={{ height }} role="img" aria-label="Bar chart of live and inactive hubs per cluster. The cluster table below lists the same values.">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 4 }} barCategoryGap={5}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" allowDecimals={false} tick={{ fill: INK_MUTED, fontSize: 11 }} axisLine={{ stroke: GRID }} tickLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={118}
            tick={({ x, y, payload }) => {
              const sel = rows.find((r) => r.label === payload.value)?.cluster_id === selectedClusterId;
              return (
                <text x={x} y={y} dy={4} textAnchor="end" fontSize={11} fill={sel ? "#0f172a" : "#475569"} fontWeight={sel ? 700 : 400}>
                  {payload.value}
                </text>
              );
            }}
            axisLine={false}
            tickLine={false}
            interval={0}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(15,23,42,0.04)" }} />
          <Legend verticalAlign="top" align="right" height={26} iconType="square" iconSize={9} wrapperStyle={{ fontSize: 12, color: "#475569" }} />
          <Bar
            dataKey="active"
            name="Live"
            stackId="h"
            fill={SERIES.live}
            stroke="#ffffff"
            strokeWidth={2}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(d) => selectFromBar(d, onSelect)}
          />
          <Bar
            dataKey="inactive"
            name="Not live / to be made live"
            stackId="h"
            fill={SERIES.inactive}
            stroke="#ffffff"
            strokeWidth={2}
            radius={[0, 4, 4, 0]}
            cursor={onSelect ? "pointer" : undefined}
            onClick={(d) => selectFromBar(d, onSelect)}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

type SortKey = "display_name" | "hub_count" | "active" | "boundary_area_km2" | "hub_density_per_km2" | "service_area_union_km2" | "max_hub_distance_km" | "mean_nearest_neighbor_km" | "hubs_outside_boundary";

export function ClusterSummaryTable({
  data,
  selectedClusterId,
  onSelect,
  compact,
}: {
  data: ClusterStat[];
  selectedClusterId?: string | null;
  onSelect?: (clusterId: string) => void;
  compact?: boolean;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "hub_count", dir: -1 });
  const rows = useMemo(() => {
    return [...data].sort((a, b) => {
      const av = a[sort.key] ?? -Infinity;
      const bv = b[sort.key] ?? -Infinity;
      if (typeof av === "string" && typeof bv === "string") return av.localeCompare(bv) * sort.dir;
      return ((av as number) - (bv as number)) * sort.dir;
    });
  }, [data, sort]);

  const cols: { key: SortKey; label: string; num?: boolean; hideCompact?: boolean; title?: string }[] = [
    { key: "display_name", label: "Cluster" },
    { key: "hub_count", label: "Hubs", num: true },
    { key: "active", label: "Live", num: true },
    { key: "boundary_area_km2", label: "Area km²", num: true, title: "Cluster boundary polygon area" },
    { key: "hub_density_per_km2", label: "Hubs/km²", num: true, hideCompact: true },
    { key: "service_area_union_km2", label: "Coverage km²", num: true, hideCompact: true, title: "Union of hub service-area polygons" },
    { key: "max_hub_distance_km", label: "Spread km", num: true, hideCompact: true, title: "Max straight-line distance from cluster center to a hub" },
    { key: "mean_nearest_neighbor_km", label: "Hub spacing km", num: true, hideCompact: true, title: "Mean straight-line distance to the nearest hub in the same cluster" },
    { key: "hubs_outside_boundary", label: "Outside bdry", num: true, hideCompact: true, title: "Hubs whose location falls outside the cluster boundary polygon" },
  ];
  const visibleCols = cols.filter((c) => !(compact && c.hideCompact));

  return (
    <div className="overflow-x-auto">
      <table className="table-base">
        <thead>
          <tr>
            {visibleCols.map((c) => {
              const active = sort.key === c.key;
              const Icon = active ? (sort.dir === 1 ? ArrowUp : ArrowDown) : ArrowUpDown;
              return (
                <th key={c.key} className={c.num ? "text-right" : ""} title={c.title} aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                  <button
                    type="button"
                    className={cx("inline-flex items-center gap-1 uppercase", c.num && "flex-row-reverse")}
                    onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? ((s.dir * -1) as 1 | -1) : c.num ? -1 : 1 }))}
                  >
                    {c.label}
                    <Icon className={cx("h-3 w-3", !active && "opacity-40")} />
                  </button>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="tabular">
          {rows.map((r) => (
            <tr
              key={r.cluster_id}
              onClick={() => onSelect?.(r.cluster_id)}
              className={cx(onSelect && "cursor-pointer", r.cluster_id === selectedClusterId ? "bg-brand-50" : "hover:bg-slate-50")}
            >
              <td className="font-medium text-ink">
                <span className="flex items-center gap-2 whitespace-nowrap">
                  <ClusterDot color={r.color} /> {r.display_name}
                </span>
              </td>
              <td className="text-right font-semibold">{r.hub_count}</td>
              <td className="text-right">{r.active}</td>
              <td className="text-right">{fmtNum(r.boundary_area_km2, 1)}</td>
              {!compact && (
                <>
                  <td className="text-right">{fmtNum(r.hub_density_per_km2, 2)}</td>
                  <td className="text-right">{fmtNum(r.service_area_union_km2, 1)}</td>
                  <td className="text-right">{fmtNum(r.max_hub_distance_km, 1)}</td>
                  <td className="text-right">{fmtNum(r.mean_nearest_neighbor_km, 2)}</td>
                  <td className={cx("text-right", r.hubs_outside_boundary > 0 && "font-semibold text-amber-700")}>{r.hubs_outside_boundary}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Labelled single-colour bar list (a table with bars) for small categorical breakdowns. */
export function BarList({ data, total, labels }: { data: Record<string, number>; total: number; labels?: Record<string, string> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  return (
    <ul className="space-y-2">
      {entries.map(([k, v]) => (
        <li key={k} className="text-xs">
          <div className="mb-0.5 flex justify-between gap-2">
            <span className="truncate text-slate-600">{labels?.[k] ?? k}</span>
            <span className="tabular shrink-0 font-medium text-ink">
              {v} <span className="font-normal text-slate-400">({pct(v, total)}%)</span>
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-slate-100">
            <div className="h-1.5 rounded-full" style={{ width: `${(v / max) * 100}%`, background: SERIES.single }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function MissingDataIndicators({ data }: { data: AnalyticsOverview["missing_data"] }) {
  return (
    <ul className="space-y-2.5">
      {data.map((d) => {
        const complete = d.total - d.missing;
        const p = pct(complete, d.total);
        const tone = d.missing === 0 ? "text-emerald-700" : p >= 90 ? "text-amber-700" : "text-red-700";
        return (
          <li key={d.field} className="text-xs">
            <div className="mb-0.5 flex justify-between gap-2">
              <span className="text-slate-600">{d.label}</span>
              <span className={cx("tabular font-medium", tone)}>
                {d.missing === 0 ? "Complete" : `${d.missing} missing`} · {p}%
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-100">
              <div className="h-1.5 rounded-full bg-slate-500" style={{ width: `${p}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
