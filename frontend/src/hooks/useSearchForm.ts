import { useCallback, useEffect, useRef, useState } from "react";
import { useAppData } from "../context/AppData";
import { useSearch, type SearchOptionsState } from "../context/SearchContext";
import { haversineMeters } from "../lib/geo";
import { validateCoordinates, type CoordinateErrors } from "../lib/validation";
import { useGeolocation } from "./useGeolocation";

/** Form state + actions for the nearest-hub search (manual coordinates, one-shot GPS, live tracking). */
export function useSearchForm() {
  const { preferences, settings } = useAppData();
  const search = useSearch();
  const geo = useGeolocation();

  const [lat, setLat] = useState(() => (search.origin ? search.origin.lat.toFixed(6) : ""));
  const [lng, setLng] = useState(() => (search.origin ? search.origin.lng.toFixed(6) : ""));
  const [errors, setErrors] = useState<CoordinateErrors>({});
  const [picked, setPicked] = useState<{ lat: number; lng: number } | null>(null);
  const [options, setOptions] = useState<SearchOptionsState>({
    clusterId: "auto",
    travelMode: "driving",
    ranking: "distance",
    radiusKm: 15,
    maxCandidates: 60,
    liveOnly: true,
  });
  const [saveManual, setSaveManual] = useState(true);
  const [saveGps, setSaveGps] = useState(false);
  const initialised = useRef(false);

  // Adopt server-side defaults once they are loaded.
  useEffect(() => {
    if (!preferences || initialised.current) return;
    initialised.current = true;
    setOptions((o) => ({
      ...o,
      travelMode: preferences.travel_mode,
      ranking: preferences.ranking,
      radiusKm: preferences.search_radius_km,
      maxCandidates: preferences.max_candidates,
      liveOnly: preferences.live_only,
    }));
    setSaveManual(preferences.save_manual_searches);
    setSaveGps(preferences.save_gps_searches);
  }, [preferences]);

  const activeProvider = settings?.routing.providers.find((p) => p.name === settings.routing.active);

  // If the active provider cannot do the chosen mode, fall back to driving.
  useEffect(() => {
    if (activeProvider && !activeProvider.modes.includes(options.travelMode)) {
      setOptions((o) => ({ ...o, travelMode: "driving" }));
    }
  }, [activeProvider, options.travelMode]);

  const setLatClear = (v: string) => {
    setLat(v);
    setErrors((e) => ({ ...e, latitude: undefined }));
  };
  const setLngClear = (v: string) => {
    setLng(v);
    setErrors((e) => ({ ...e, longitude: undefined }));
  };

  const submit = useCallback(() => {
    const parsed = validateCoordinates(lat, lng);
    if (!parsed.ok) {
      setErrors(parsed.errors);
      return;
    }
    setErrors({});
    setPicked(null);
    geo.dismiss();
    void search.runSearch(parsed.latitude, parsed.longitude, "manual", options, saveManual);
  }, [lat, lng, options, saveManual, search, geo]);

  const locate = useCallback(async () => {
    const fix = await geo.locateOnce();
    if (!fix) return;
    setLat(fix.lat.toFixed(6));
    setLng(fix.lng.toFixed(6));
    setErrors({});
    setPicked(null);
    void search.runSearch(fix.lat, fix.lng, "gps", options, saveGps);
  }, [geo, options, saveGps, search]);

  // Live tracking: re-run the search when the user has moved far enough.
  const lastTracked = useRef<{ lat: number; lng: number } | null>(null);
  const minMove = preferences?.tracking_min_move_m ?? 150;
  useEffect(() => {
    if (!geo.tracking || !geo.fix) return;
    const { lat: la, lng: lo } = geo.fix;
    const prev = lastTracked.current;
    if (prev && haversineMeters(prev.lat, prev.lng, la, lo) < minMove) return;
    lastTracked.current = { lat: la, lng: lo };
    setLat(la.toFixed(6));
    setLng(lo.toFixed(6));
    void search.runSearch(la, lo, "tracking", options, saveGps);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.fix, geo.tracking]);

  const startTracking = useCallback(() => {
    lastTracked.current = null;
    geo.startTracking();
  }, [geo]);

  const pick = useCallback((la: number, lo: number) => {
    setLat(la.toFixed(6));
    setLng(lo.toFixed(6));
    setErrors({});
    setPicked({ lat: la, lng: lo });
  }, []);

  const clear = useCallback(() => {
    geo.stopTracking();
    search.clear();
    setLat("");
    setLng("");
    setErrors({});
    setPicked(null);
  }, [geo, search]);

  return {
    lat,
    lng,
    setLat: setLatClear,
    setLng: setLngClear,
    errors,
    options,
    setOptions,
    saveManual,
    setSaveManual,
    saveGps,
    setSaveGps,
    geo,
    picked,
    pick,
    submit,
    locate,
    startTracking,
    clear,
    activeProvider,
    search,
  };
}
