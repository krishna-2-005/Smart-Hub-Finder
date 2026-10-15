import { Eraser, Search } from "lucide-react";
import type { ClipboardEvent, FormEvent, ReactNode } from "react";
import { splitPastedPair, type CoordinateErrors } from "../../lib/validation";
import { Button, cx } from "../ui";

export function CoordinateSearch({
  lat,
  lng,
  onLatChange,
  onLngChange,
  errors,
  onSubmit,
  onClear,
  loading,
  children,
}: {
  lat: string;
  lng: string;
  onLatChange: (v: string) => void;
  onLngChange: (v: string) => void;
  errors: CoordinateErrors;
  onSubmit: () => void;
  onClear?: () => void;
  loading: boolean;
  children?: ReactNode;
}) {
  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const pair = splitPastedPair(e.clipboardData.getData("text"));
    if (pair) {
      e.preventDefault();
      onLatChange(pair.lat);
      onLngChange(pair.lng);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="lat" className="label mb-1">
            Latitude
          </label>
          <input
            id="lat"
            inputMode="decimal"
            autoComplete="off"
            placeholder="17.448500"
            className={cx("input tabular", errors.latitude && "input-error")}
            value={lat}
            onChange={(e) => onLatChange(e.target.value)}
            onPaste={handlePaste}
            aria-invalid={Boolean(errors.latitude)}
            aria-describedby={errors.latitude ? "lat-err" : "coord-hint"}
          />
          {errors.latitude && (
            <p id="lat-err" className="mt-1 text-xs text-red-600">
              {errors.latitude}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="lng" className="label mb-1">
            Longitude
          </label>
          <input
            id="lng"
            inputMode="decimal"
            autoComplete="off"
            placeholder="78.390800"
            className={cx("input tabular", errors.longitude && "input-error")}
            value={lng}
            onChange={(e) => onLngChange(e.target.value)}
            onPaste={handlePaste}
            aria-invalid={Boolean(errors.longitude)}
            aria-describedby={errors.longitude ? "lng-err" : "coord-hint"}
          />
          {errors.longitude && (
            <p id="lng-err" className="mt-1 text-xs text-red-600">
              {errors.longitude}
            </p>
          )}
        </div>
      </div>
      <p id="coord-hint" className="text-[11px] text-slate-500">
        Decimal degrees (WGS84). Tip: paste “17.4485, 78.3908” from Google Maps into either box, or click the map to pick a point.
      </p>
      {children}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" icon={Search} loading={loading} className="flex-1">
          Find nearest hub
        </Button>
        {onClear && (
          <Button variant="ghost" icon={Eraser} onClick={onClear} aria-label="Clear search">
            Clear
          </Button>
        )}
      </div>
    </form>
  );
}
