import { Eye, History, Lock, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { HistoryRecord } from "../api/types";
import { Alert, Badge, Button, Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { useSearch } from "../context/SearchContext";
import { fmtCoord, fmtDateTime, fmtMeters, fmtSecondsAsMin, travelModeLabel } from "../lib/format";

export function RouteHistoryPage() {
  const [records, setRecords] = useState<HistoryRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { loadResult } = useSearch();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setError(null);
    try {
      setRecords((await api.history()).records);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const open = async (id: number) => {
    setBusy(true);
    try {
      const rec = await api.historyRecord(id);
      loadResult(rec.result);
      navigate("/find");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    await api.deleteHistory(id);
    setRecords((r) => r?.filter((x) => x.id !== id) ?? null);
  };

  const clearAll = async () => {
    if (!window.confirm("Delete all saved searches and their locations? This cannot be undone.")) return;
    await api.clearHistory();
    setRecords([]);
  };

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Route history"
        description="Searches saved to the local SQLite database. Coordinate searches are saved by default; GPS locations only when you tick the consent box."
        actions={
          <>
            <Button size="sm" icon={RefreshCw} onClick={() => void load()}>
              Refresh
            </Button>
            <Button size="sm" variant="danger" icon={Trash2} onClick={() => void clearAll()} disabled={!records?.length}>
              Clear all
            </Button>
          </>
        }
      />
      <Alert tone="info" title="Privacy">
        <span className="inline-flex items-center gap-1">
          <Lock className="h-3.5 w-3.5" /> History stays on this server (data/app.db). Nothing is sent to third parties except the coordinates needed to compute a
          route with the configured routing provider.
        </span>
      </Alert>
      {error && <Alert tone="error">{error}</Alert>}
      <Card bodyClassName="p-0" icon={History} title={`Saved searches${records ? ` (${records.length})` : ""}`}>
        {!records ? (
          <div className="p-6">
            <Spinner />
          </div>
        ) : !records.length ? (
          <EmptyState icon={History} title="No saved searches yet">
            Run a nearest-hub search with “Save to route history” enabled.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-base">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Source</th>
                  <th className="text-right">Location</th>
                  <th>Cluster</th>
                  <th>Nearest hub</th>
                  <th className="text-right">Road distance</th>
                  <th className="text-right">Time</th>
                  <th>Mode</th>
                  <th>Provider</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap text-xs">{fmtDateTime(r.created_at)}</td>
                    <td>
                      <Badge tone={r.source === "manual" ? "slate" : "blue"}>{r.source === "manual" ? "Coordinates" : "GPS"}</Badge>
                    </td>
                    <td className="tabular whitespace-nowrap text-right text-xs">
                      {fmtCoord(r.latitude, 5)}, {fmtCoord(r.longitude, 5)}
                    </td>
                    <td className="text-xs">{r.cluster_name ?? "—"}</td>
                    <td className="font-medium">{r.nearest_hub_name ?? <span className="text-slate-400">{r.status}</span>}</td>
                    <td className="tabular text-right">{fmtMeters(r.road_distance_m)}</td>
                    <td className="tabular text-right">{fmtSecondsAsMin(r.duration_s)}</td>
                    <td className="text-xs">{travelModeLabel[r.travel_mode ?? ""] ?? r.travel_mode}</td>
                    <td className="text-xs uppercase text-slate-500">{r.provider ?? "—"}</td>
                    <td>
                      <span className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" icon={Eye} onClick={() => void open(r.id)} disabled={busy}>
                          Open
                        </Button>
                        <Button size="sm" variant="ghost" icon={Trash2} onClick={() => void remove(r.id)} aria-label="Delete record" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
