import { CheckCircle2, ClipboardList, Database, FileCode2, FileWarning, FolderTree, Upload, Wrench } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { DataQuality, ImportResult } from "../api/types";
import { Alert, Badge, Button, Card, KeyValue, PageHeader, Spinner, cx } from "../components/ui";
import { useAppData } from "../context/AppData";
import { fmtDateTime, fmtInt } from "../lib/format";

function IssueBlock({ title, count, tone = "amber", children }: { title: string; count: number; tone?: "amber" | "red" | "green"; children?: ReactNode }) {
  const ok = count === 0;
  return (
    <details className="group rounded-lg border border-slate-200 bg-white open:shadow-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5">
        <span className="text-sm font-medium text-ink">{title}</span>
        <Badge tone={ok ? "green" : tone === "red" ? "red" : "amber"}>{ok ? "None" : count}</Badge>
      </summary>
      {!ok && children && <div className="border-t border-slate-100 px-3 py-2.5 text-xs text-slate-600">{children}</div>}
    </details>
  );
}

export function DataImportPage() {
  const { analytics, reload } = useAppData();
  const [dq, setDq] = useState<DataQuality | null>(null);
  const [dqError, setDqError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"preview" | "activate" | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  useEffect(() => {
    api.dataQuality().then(setDq).catch((e) => setDqError((e as Error).message));
  }, [analytics?.dataset.sha256]);

  const run = async (activate: boolean) => {
    if (!file) return;
    if (activate && !window.confirm("Replace the active hub dataset with this file? The current processed data is archived.")) return;
    setBusy(activate ? "activate" : "preview");
    setImportError(null);
    try {
      const r = await api.importKml(file, activate);
      setImportResult(r);
      if (activate) await reload();
    } catch (e) {
      setImportError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const q = dq?.quality;
  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
      <PageHeader title="Data import & quality" description="Upload a KML/KMZ to analyse or replace the hub dataset, and review every data-quality finding from the current file." />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Active dataset" icon={Database}>
          {analytics ? (
            <KeyValue
              items={[
                ["Source file", analytics.dataset.file_name],
                ["Processed", fmtDateTime(analytics.dataset.processed_at)],
                ["Placemarks", fmtInt(analytics.dataset.placemarks)],
                ["Hubs / clusters", `${analytics.totals.hubs} / ${analytics.totals.clusters}`],
                ["XML repairs applied", analytics.dataset.repairs],
                ["SHA-256", <span key="sha" className="font-mono text-[11px]">{analytics.dataset.sha256.slice(0, 20)}…</span>],
              ]}
            />
          ) : (
            <p className="text-sm text-slate-500">No dataset loaded.</p>
          )}
        </Card>
        <Card title="Import a KML or KMZ" icon={Upload} subtitle="Files are repaired safely (escaped entities only) and never modified in place">
          <div className="space-y-3">
            <label
              htmlFor="kml-file"
              className={cx(
                "flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm",
                file ? "border-brand-300 bg-brand-50" : "border-slate-300 hover:border-brand-400 hover:bg-slate-50",
              )}
            >
              <FileCode2 className="h-6 w-6 text-slate-400" />
              <span className="font-medium text-ink">{file ? file.name : "Choose a .kml or .kmz file"}</span>
              <span className="text-xs text-slate-500">{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "Up to 60 MB"}</span>
              <input
                id="kml-file"
                type="file"
                accept=".kml,.kmz,application/vnd.google-earth.kml+xml,application/vnd.google-earth.kmz"
                className="sr-only"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setImportResult(null);
                  setImportError(null);
                }}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button icon={ClipboardList} onClick={() => void run(false)} disabled={!file} loading={busy === "preview"}>
                Analyse only
              </Button>
              <Button variant="primary" icon={Upload} onClick={() => void run(true)} disabled={!file} loading={busy === "activate"}>
                Analyse &amp; activate
              </Button>
            </div>
            {importError && <Alert tone="error" title="Import failed">{importError}</Alert>}
            {importResult && (
              <Alert tone={importResult.activated ? "success" : "info"} title={importResult.activated ? "Dataset activated" : "Analysis complete (not activated)"}>
                <p>
                  {importResult.summary.placemarks} placemarks · <b>{importResult.summary.hubs} hubs</b> · <b>{importResult.summary.clusters} clusters</b> ·{" "}
                  {importResult.summary.repairs} XML repairs · coordinates {importResult.summary.coordinates_unchanged ? "unchanged" : "CHANGED"}
                </p>
                <p className="mt-1">Cluster method: {importResult.summary.cluster_method}</p>
                {importResult.report_markdown && (
                  <details className="mt-2">
                    <summary className="cursor-pointer font-medium">Full analysis report</summary>
                    <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-white/70 p-2 text-[11px] text-slate-700">{importResult.report_markdown}</pre>
                  </details>
                )}
              </Alert>
            )}
          </div>
        </Card>
      </div>

      {dqError && <Alert tone="error">{dqError}</Alert>}
      {!dq ? (
        <Spinner label="Loading data-quality analysis…" />
      ) : (
        <>
          <div className="grid gap-5 lg:grid-cols-3">
            <Card title="XML repair" icon={Wrench} className="lg:col-span-1">
              <div className="space-y-2 text-sm">
                <p className="flex items-center gap-2">
                  {dq.repair.valid_before ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <FileWarning className="h-4 w-4 text-amber-600" />}
                  Original file {dq.repair.valid_before ? "was valid XML" : "was not valid XML"}
                </p>
                {dq.repair.parse_error_before && <p className="rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-600">{dq.repair.parse_error_before}</p>}
                <p>
                  <b>{dq.repair.total_changes}</b> safe fixes applied:{" "}
                  {Object.entries(dq.repair.changes_by_kind).map(([k, v]) => `${v} × ${k.replace(/_/g, " ")}`).join(", ") || "none"}.
                </p>
                {dq.repair.distinct_contexts.map((c) => (
                  <p key={c.context} className="rounded bg-slate-50 p-2 font-mono text-[11px] text-slate-600">
                    {c.context} <span className="text-slate-400">× {c.occurrences}</span>
                  </p>
                ))}
                <p className="flex items-center gap-2">
                  <CheckCircle2 className={cx("h-4 w-4", dq.repair.coordinates_unchanged ? "text-emerald-600" : "text-red-600")} />
                  {fmtInt(dq.repair.coordinate_blocks)} coordinate blocks {dq.repair.coordinates_unchanged ? "verified unchanged" : "CHANGED"}
                </p>
                <p className="text-xs text-slate-500">Original preserved as data/source/original_backup.kml.</p>
              </div>
            </Card>
            <Card title="Data-quality findings" icon={FileWarning} className="lg:col-span-2" bodyClassName="space-y-2">
              <IssueBlock title="Duplicate hub IDs" count={Object.keys(q!.duplicate_hub_ids).length} tone="red">
                {Object.entries(q!.duplicate_hub_ids).map(([k, v]) => `${k} ×${v}`).join(", ")}
              </IssueBlock>
              <IssueBlock title="Duplicate hub names" count={Object.keys(q!.duplicate_hub_names).length}>
                {Object.entries(q!.duplicate_hub_names).map(([k, v]) => `${k} ×${v}`).join(", ")}
              </IssueBlock>
              <IssueBlock title={`Duplicate hub locations (≤ ${q!.duplicate_location_threshold_m} m)`} count={q!.duplicate_locations.length}>
                {q!.duplicate_locations.map((d) => `${d.hub_a} / ${d.hub_b} (${d.distance_m} m)`).join("; ")}
              </IssueBlock>
              <IssueBlock title="Invalid or missing coordinates" count={q!.invalid_locations.length} tone="red">
                {q!.invalid_locations.map((d) => `${d.name}: ${d.issues.join("; ")}`).join(" · ")}
              </IssueBlock>
              <IssueBlock title="Missing hub names" count={q!.missing_hub_names.length}>{q!.missing_hub_names.join(", ")}</IssueBlock>
              <IssueBlock title="Unassigned hubs (no cluster)" count={q!.unassigned_hubs.length}>{q!.unassigned_hubs.map((h) => h.name).join(", ")}</IssueBlock>
              <IssueBlock title="Hubs outside their cluster boundary" count={q!.cluster_boundary_mismatches.length}>
                <ul className="space-y-0.5">
                  {q!.cluster_boundary_mismatches.map((m) => (
                    <li key={m.hub_id}>
                      <b>{m.name}</b> ({m.assigned_cluster}): {m.distance_outside_assigned_boundary_km} km outside
                      {m.location_inside_cluster_boundaries.length ? `, inside ${m.location_inside_cluster_boundaries.join(", ")}` : ""}
                    </li>
                  ))}
                </ul>
              </IssueBlock>
              <IssueBlock title={`Isolated hubs (> ${q!.isolation_threshold_km} km from same-cluster hubs)`} count={q!.isolated_hubs.length}>
                <ul className="space-y-0.5">
                  {q!.isolated_hubs.map((m) => (
                    <li key={m.hub_id}>
                      <b>{m.name}</b> ({m.cluster}): {m.reason}
                    </li>
                  ))}
                </ul>
              </IssueBlock>
              <IssueBlock title="Overlapping hub service areas" count={q!.overlapping_service_areas.length}>
                {q!.overlapping_service_areas.map((o) => `${o.name_a} ↔ ${o.name_b} (${o.overlap_pct_of_smaller}%)`).join("; ")}
              </IssueBlock>
              <IssueBlock title="Hub records with notes (e.g. WKT mismatch, encoding)" count={q!.hubs_with_issues.length}>
                <ul className="max-h-60 space-y-0.5 overflow-y-auto">
                  {q!.hubs_with_issues.map((h) => (
                    <li key={h.hub_id}>
                      <b>{h.name}</b> (line {h.source_line}): {h.issues.join("; ")}
                    </li>
                  ))}
                </ul>
              </IssueBlock>
              <IssueBlock title="Unclassified placemarks" count={dq.unclassified.length}>
                {dq.unclassified.map((u) => `“${u.name}” (${u.geometry}, folder ${u.folder}, line ${u.source_line})`).join("; ")}
              </IssueBlock>
              <IssueBlock title="Text encoding anomalies" count={dq.encoding_anomalies.length}>
                {dq.encoding_anomalies.map((e) => `line ${e.source_line} ${e.field}`).join(", ")}
              </IssueBlock>
            </Card>
          </div>

          <Card title="KML folder inventory & classification" icon={FolderTree} bodyClassName="p-0">
            <div className="overflow-x-auto">
              <table className="table-base">
                <thead>
                  <tr>
                    <th>Folder</th>
                    <th className="text-right">Placemarks</th>
                    <th>Geometry</th>
                    <th>Classified as</th>
                  </tr>
                </thead>
                <tbody>
                  {dq.folders.map((f) => (
                    <tr key={f.path}>
                      <td className="max-w-md">
                        <p className="truncate font-medium" title={f.name}>
                          {f.name}
                        </p>
                        <p className="text-[11px] text-slate-400">line {f.source_line}</p>
                      </td>
                      <td className="tabular text-right">{f.placemark_count}</td>
                      <td className="text-xs">{Object.entries(f.geometry_counts).map(([k, v]) => `${k} ${v}`).join(", ") || "—"}</td>
                      <td className="text-xs">
                        <span className="flex flex-wrap gap-1">
                          {Object.entries(f.categories).map(([k, v]) => (
                            <Badge key={k} tone={k === "hub" ? "green" : k === "unclassified" ? "amber" : "slate"}>
                              {k.replace(/_/g, " ")} {v}
                            </Badge>
                          ))}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Classification rules & assumptions" icon={ClipboardList}>
            <ul className="space-y-2 text-sm">
              {dq.assumptions.map((a) => (
                <li key={a.topic} className="flex gap-2">
                  <Badge tone={a.inferred === "yes" ? "violet" : "slate"} className="h-fit shrink-0">
                    {a.inferred === "yes" ? "Inferred" : "Explicit"}
                  </Badge>
                  <span>
                    <b>{a.topic}.</b> {a.text}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-slate-500">Rules are configurable in backend/config/classification.json.</p>
          </Card>
        </>
      )}
    </div>
  );
}
