import { LocateFixed, Radio, Square } from "lucide-react";
import type { useGeolocation } from "../../hooks/useGeolocation";
import { Alert, Button } from "../ui";

type Geo = ReturnType<typeof useGeolocation>;

export function CurrentLocationButton({
  geo,
  onLocate,
  onStartTracking,
  disabled,
  saveGps,
  onSaveGpsChange,
}: {
  geo: Geo;
  onLocate: () => void;
  onStartTracking: () => void;
  disabled?: boolean;
  saveGps: boolean;
  onSaveGpsChange: (v: boolean) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button
          icon={LocateFixed}
          onClick={onLocate}
          loading={geo.status === "requesting" && !geo.tracking}
          disabled={disabled}
          className="flex-1"
        >
          Use my current location
        </Button>
        {geo.tracking ? (
          <Button variant="danger" icon={Square} onClick={geo.stopTracking} title="Stop live location tracking">
            Stop
          </Button>
        ) : (
          <Button icon={Radio} onClick={onStartTracking} disabled={disabled} title="Follow my location and re-run the search when I move">
            Track
          </Button>
        )}
      </div>
      <label className="flex cursor-pointer items-start gap-2 text-[11px] leading-snug text-slate-600">
        <input
          type="checkbox"
          className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-brand-700 focus:ring-brand-500"
          checked={saveGps}
          onChange={(e) => onSaveGpsChange(e.target.checked)}
        />
        <span>Save my GPS location in route history. When unchecked, the location is used for this search only and not stored.</span>
      </label>
      {geo.tracking && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900" role="status">
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75 motion-reduce:animate-none" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-600" />
          </span>
          <span>
            <b>Live tracking on.</b> Your browser shares your location with this page only
            {geo.fix ? ` (±${Math.round(geo.fix.accuracy)} m)` : ""}. The search re-runs when you move. Press Stop to end.
          </span>
        </div>
      )}
      {geo.status === "ok" && geo.fix && !geo.tracking && (
        <p className="text-[11px] text-slate-500">Location received (accuracy ±{Math.round(geo.fix.accuracy)} m).</p>
      )}
      {geo.error && (
        <Alert tone="warning" title="Location unavailable">
          {geo.error}
        </Alert>
      )}
    </div>
  );
}
