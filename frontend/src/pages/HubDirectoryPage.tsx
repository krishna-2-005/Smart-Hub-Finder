import { AlertTriangle, ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Search, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { exportUrl } from "../api/client";
import type { Hub } from "../api/types";
import { HubDetails } from "../components/results/HubDetails";
import { ClusterSelector } from "../components/search/ClusterSelector";
import { Badge, Button, Card, ClusterDot, EmptyState, LinkButton, PageHeader, StatusBadge, cx } from "../components/ui";
import { useAppData } from "../context/AppData";
import { fmtCoord } from "../lib/format";

type SortKey = "display_name" | "hub_id" | "cluster_name" | "status" | "region";
const PAGE = 25;

export function HubDirectoryPage() {
  const { hubs, clusters, clustersById } = useAppData();
  const [q, setQ] = useState("");
  const [cluster, setCluster] = useState("all");
  const [status, setStatus] = useState("all");
  const [issuesOnly, setIssuesOnly] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "display_name", dir: 1 });
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Hub | null>(null);

  const statuses = useMemo(() => [...new Set(hubs.map((h) => h.status ?? "Unknown"))].sort(), [hubs]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return hubs
      .filter((h) => cluster === "all" || h.cluster_id === cluster)
      .filter((h) => status === "all" || (h.status ?? "Unknown") === status)
      .filter((h) => !issuesOnly || h.issues.length > 0)
      .filter((h) => !needle || [h.display_name, h.name, h.hub_id, h.hub_code, h.cluster_name].some((v) => (v ?? "").toLowerCase().includes(needle)))
      .sort((a, b) => String(a[sort.key] ?? "").localeCompare(String(b[sort.key] ?? "")) * sort.dir);
  }, [hubs, q, cluster, status, issuesOnly, sort]);

  useEffect(() => setPage(0), [q, cluster, status, issuesOnly]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const rows = filtered.slice(page * PAGE, page * PAGE + PAGE);

  const th = (key: SortKey, label: string) => (
    <th aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button type="button" className="inline-flex items-center gap-1 uppercase" onClick={() => setSort((s) => ({ key, dir: s.key === key ? ((s.dir * -1) as 1 | -1) : 1 }))}>
        {label}
        {sort.key === key && (sort.dir === 1 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </button>
    </th>
  );

  return (
    <div className="mx-auto max-w-[1600px] space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Hub directory"
        description="Every hub identified in the KML, with its cluster, status and the location used for routing."
        actions={
          <>
            <LinkButton href={exportUrl.csv("hubs", { cluster_id: cluster === "all" ? undefined : cluster })} download icon={Download} size="sm">
              CSV{cluster !== "all" ? " (this cluster)" : ""}
            </LinkButton>
            <LinkButton href={exportUrl.geojson("hubs")} download icon={Download} size="sm">
              GeoJSON
            </LinkButton>
          </>
        }
      />
      <Card bodyClassName="p-0">
        <div className="grid gap-3 border-b border-slate-100 p-4 md:grid-cols-[1fr,220px,180px,auto] md:items-end">
          <div className="relative">
            <label htmlFor="hub-q" className="label mb-1">
              Search hubs
            </label>
            <Search className="pointer-events-none absolute left-2.5 top-[30px] h-4 w-4 text-slate-400" />
            <input id="hub-q" className="input pl-8" placeholder="Name, hub ID, code or cluster" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <ClusterSelector id="dir-cluster" value={cluster} onChange={setCluster} clusters={clusters} includeAuto={false} />
          <div>
            <label htmlFor="dir-status" className="label mb-1">
              Status
            </label>
            <select id="dir-status" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">All statuses</option>
              {statuses.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <label className="flex cursor-pointer items-center gap-2 pb-2 text-sm">
            <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-brand-700" checked={issuesOnly} onChange={(e) => setIssuesOnly(e.target.checked)} />
            With data issues
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="table-base">
            <thead>
              <tr>
                {th("display_name", "Hub")}
                {th("hub_id", "Hub ID")}
                {th("cluster_name", "Cluster")}
                {th("region", "Line")}
                {th("status", "Status")}
                <th className="text-right">Latitude</th>
                <th className="text-right">Longitude</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <tr key={h.hub_id} className="cursor-pointer hover:bg-slate-50" onClick={() => setSelected(h)}>
                  <td className="font-medium text-ink">{h.display_name}</td>
                  <td className="font-mono text-xs text-slate-500">{h.hub_id}</td>
                  <td>
                    <span className="flex items-center gap-2 whitespace-nowrap">
                      <ClusterDot color={clustersById[h.cluster_id ?? ""]?.color ?? "#64748b"} />
                      {h.cluster_name ?? <Badge tone="amber">Unassigned</Badge>}
                    </span>
                  </td>
                  <td className="whitespace-nowrap text-xs text-slate-500">{h.region ?? "—"}</td>
                  <td>
                    <StatusBadge status={h.status} active={h.is_active} />
                  </td>
                  <td className="tabular text-right text-xs">{fmtCoord(h.latitude, 5)}</td>
                  <td className="tabular text-right text-xs">{fmtCoord(h.longitude, 5)}</td>
                  <td>
                    <span className="flex gap-1">
                      {h.location_inferred && <Badge tone="violet" title="Location inferred from service-area polygon">Inferred</Badge>}
                      {h.issues.length > 0 && (
                        <Badge tone="amber" title={h.issues.join("\n")}>
                          <AlertTriangle className="h-3 w-3" /> {h.issues.length}
                        </Badge>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <EmptyState title="No hubs match these filters">Try clearing the search or choosing another cluster.</EmptyState>}
        </div>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm">
          <span className="text-slate-500">
            {filtered.length} hub{filtered.length === 1 ? "" : "s"} · page {page + 1} of {pages}
          </span>
          <div className="flex gap-1">
            <Button size="sm" variant="secondary" icon={ChevronLeft} disabled={page === 0} onClick={() => setPage((p) => p - 1)} aria-label="Previous page" />
            <Button size="sm" variant="secondary" icon={ChevronRight} disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} aria-label="Next page" />
          </div>
        </div>
      </Card>

      {selected && (
        <div className="fixed inset-0 z-[1300] flex justify-end bg-slate-900/30" onClick={() => setSelected(null)} role="dialog" aria-modal="true" aria-label="Hub details">
          <div className={cx("h-full w-full max-w-md overflow-y-auto bg-white p-5 shadow-pop")} onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex justify-end">
              <Button variant="ghost" size="sm" icon={X} onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
            <HubDetails hub={selected} clusterColor={clustersById[selected.cluster_id ?? ""]?.color} />
          </div>
        </div>
      )}
    </div>
  );
}
