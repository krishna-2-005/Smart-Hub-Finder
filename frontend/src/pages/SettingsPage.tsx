import { CheckCircle2, KeyRound, PlugZap, RotateCcw, Route as RouteIcon, Save, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Preferences, ProviderName, TravelMode } from "../api/types";
import { Alert, Badge, Button, Card, PageHeader, Segmented, Spinner, Toggle } from "../components/ui";
import { useAppData } from "../context/AppData";
import { travelModeLabel } from "../lib/format";

function NumberField({ id, label, value, onChange, min, max, step = 1, hint }: { id: string; label: string; value: number; onChange: (v: number) => void; min: number; max: number; step?: number; hint?: string }) {
  return (
    <div>
      <label htmlFor={id} className="label mb-1">
        {label}
      </label>
      <input id={id} type="number" className="input tabular" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
}

export function SettingsPage() {
  const { settings, setSettings, health } = useAppData();
  const ephemeral = health?.deployment.persistent_storage === false;
  const [draft, setDraft] = useState<Preferences | null>(settings?.preferences ?? null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [test, setTest] = useState<Record<string, unknown> | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (settings && !draft) setDraft(settings.preferences);
  }, [settings, draft]);

  if (!settings || !draft) return <div className="p-6"><Spinner /></div>;
  const set = <K extends keyof Preferences>(k: K, v: Preferences[K]) => setDraft({ ...draft, [k]: v });
  const routing = settings.routing;
  const chosen = draft.routing_provider === "auto" ? routing.providers.find((p) => p.name === (routing.providers.find((x) => x.name === "google")?.configured ? "google" : "osrm")) : routing.providers.find((p) => p.name === draft.routing_provider);

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const r = await api.updateSettings(draft);
      setSettings(r);
      setDraft(r.preferences);
      setMsg(r.routing.error ? { tone: "error", text: `Saved, but routing is unavailable: ${r.routing.error}` } : { tone: "success", text: "Settings saved." });
    } catch (e) {
      setMsg({ tone: "error", text: (e as Error).message });
    } finally {
      setSaving(false);
    }
  };
  const reset = async () => {
    const r = await api.resetSettings();
    setSettings(r);
    setDraft(r.preferences);
    setMsg({ tone: "success", text: "Defaults restored." });
  };
  const runTest = async () => {
    setTesting(true);
    setTest(null);
    try {
      setTest(await api.routingTest(draft.routing_provider, draft.travel_mode === "two_wheeler" && chosen?.name !== "google" ? "driving" : draft.travel_mode));
    } catch (e) {
      setTest({ ok: false, message: (e as Error).message });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1100px] space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Settings"
        description="Routing provider and search defaults. API keys are read from backend/.env on the server and never sent to the browser."
        actions={
          <>
            <Button size="sm" icon={RotateCcw} onClick={() => void reset()}>
              Reset defaults
            </Button>
            <Button size="sm" variant="primary" icon={Save} onClick={() => void save()} loading={saving}>
              Save settings
            </Button>
          </>
        }
      />
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      {ephemeral && (
        <Alert tone="warning" title="Settings are temporary on the cloud deployment">
          Serverless instances do not share storage, so saved defaults can reset. Each search still sends its own travel mode, ranking, radius and
          candidate limit from the search panel. API keys are configured as Vercel environment variables.
        </Alert>
      )}

      <Card title="Routing provider" icon={RouteIcon} subtitle="All providers return real road-network geometry, distance and duration. None ever falls back to a straight line.">
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            {[{ name: "auto", label: "Automatic", configured: true, modes: [] as TravelMode[], reason: null, requires_key: false }, ...routing.providers].map((p) => (
              <label key={p.name} className={`flex cursor-pointer gap-3 rounded-lg border p-3 ${draft.routing_provider === p.name ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500" : "border-slate-200 hover:bg-slate-50"}`}>
                <input type="radio" name="provider" className="mt-1 h-4 w-4 text-brand-700" checked={draft.routing_provider === p.name} onChange={() => set("routing_provider", p.name as ProviderName)} />
                <span className="min-w-0 text-sm">
                  <span className="flex flex-wrap items-center gap-2 font-semibold text-ink">
                    {p.label}
                    {p.name !== "auto" &&
                      (p.configured ? (
                        <Badge tone="green">
                          <CheckCircle2 className="h-3 w-3" /> Ready
                        </Badge>
                      ) : (
                        <Badge tone="red">
                          <KeyRound className="h-3 w-3" /> Key missing
                        </Badge>
                      ))}
                    {routing.active === p.name && <Badge tone="blue">Active</Badge>}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {p.name === "auto"
                      ? "Google Routes API when GOOGLE_MAPS_API_KEY is set, otherwise OSRM."
                      : p.reason ?? `Modes: ${p.modes.map((m) => travelModeLabel[m]).join(", ")}`}
                  </span>
                </span>
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button icon={PlugZap} onClick={() => void runTest()} loading={testing}>
              Test live routing
            </Button>
            {test && (
              <span className={`flex items-center gap-1.5 text-sm ${test.ok ? "text-emerald-700" : "text-red-700"}`}>
                {test.ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                {test.ok
                  ? `${String(test.label)} OK — ${(Number(test.distance_m) / 1000).toFixed(2)} km route with ${String(test.geometry_points)} road points in ${String(test.latency_ms)} ms`
                  : String(test.message)}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500">
            The OSRM default uses the free public OpenStreetMap demo servers (fair-use, no SLA). For production, set GOOGLE_MAPS_API_KEY or ORS_API_KEY,
            or point OSRM_DRIVING_URL at a self-hosted OSRM server.
          </p>
        </div>
      </Card>

      <Card title="Search defaults">
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-4">
            <div>
              <span className="label mb-1">Default travel mode</span>
              <Segmented
                ariaLabel="Default travel mode"
                value={draft.travel_mode}
                onChange={(v) => set("travel_mode", v)}
                options={(["driving", "two_wheeler", "cycling", "walking"] as TravelMode[]).map((m) => ({ value: m, label: travelModeLabel[m], disabled: chosen ? !chosen.modes.includes(m) && chosen.name !== "auto" : false }))}
              />
            </div>
            <div>
              <span className="label mb-1">Default nearest-hub ranking</span>
              <Segmented
                ariaLabel="Default ranking"
                value={draft.ranking}
                onChange={(v) => set("ranking", v)}
                options={[
                  { value: "distance", label: "Shortest road distance" },
                  { value: "duration", label: "Shortest travel time" },
                ]}
              />
            </div>
            <Toggle id="pref-live" checked={draft.live_only} onChange={(v) => set("live_only", v)} label="Only live hubs by default" description="Uses the ‘Hub status’ attribute from the KML." />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <NumberField id="pref-radius" label="Search radius (km)" value={draft.search_radius_km} onChange={(v) => set("search_radius_km", v)} min={0.5} max={200} step={0.5} hint="Straight-line pre-filter" />
            <NumberField id="pref-maxc" label="Max candidates" value={draft.max_candidates} onChange={(v) => set("max_candidates", v)} min={1} max={500} hint="Cap for large searches" />
            <NumberField id="pref-exh" label="Exhaustive threshold" value={draft.exhaustive_threshold} onChange={(v) => set("exhaustive_threshold", v)} min={1} max={200} hint="Evaluate all when ≤ this" />
            <NumberField id="pref-topn" label="Hubs to rank" value={draft.top_n} onChange={(v) => set("top_n", v)} min={1} max={20} />
            <NumberField id="pref-snap" label="Max road snap (m)" value={draft.max_snap_distance_m} onChange={(v) => set("max_snap_distance_m", v)} min={10} max={10000} hint="Hub farther from a road = unreachable" />
            <NumberField id="pref-move" label="Tracking re-search (m)" value={draft.tracking_min_move_m} onChange={(v) => set("tracking_min_move_m", v)} min={10} max={10000} hint="Movement before re-searching" />
          </div>
        </div>
      </Card>

      <Card title="Privacy & history">
        <div className="space-y-4">
          <Toggle id="pref-save-manual" checked={draft.save_manual_searches} onChange={(v) => set("save_manual_searches", v)} label="Save coordinate searches to route history by default" />
          <Toggle
            id="pref-save-gps"
            checked={draft.save_gps_searches}
            onChange={(v) => set("save_gps_searches", v)}
            label="Save GPS locations to route history by default"
            description="Off by default: shared locations are used for the search only, unless the user ticks the consent box."
          />
        </div>
      </Card>
    </div>
  );
}
