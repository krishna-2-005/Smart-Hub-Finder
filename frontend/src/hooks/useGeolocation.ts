import { useCallback, useEffect, useRef, useState } from "react";

export interface GeoFix {
  lat: number;
  lng: number;
  accuracy: number;
  timestamp: number;
}

export type GeoStatus = "idle" | "requesting" | "ok" | "tracking" | "error";

const ERROR_TEXT: Record<number, string> = {
  1: "Location permission was denied. Allow location access for this site in your browser settings, or enter coordinates manually.",
  2: "Your position is unavailable (no GPS / network location). Enter coordinates manually instead.",
  3: "Getting your location timed out. Try again, move to an open area, or enter coordinates manually.",
};

function describe(err: GeolocationPositionError): string {
  return ERROR_TEXT[err.code] ?? `Could not get your location: ${err.message}`;
}

export function geolocationSupportIssue(): string | null {
  if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
    return "This browser does not support location sharing. Enter coordinates manually.";
  }
  if (typeof window !== "undefined" && !window.isSecureContext) {
    return "Location sharing needs a secure connection (HTTPS or localhost). Open the app via https:// or enter coordinates manually.";
  }
  return null;
}

/** Browser geolocation with one-shot and continuous (tracking) modes. Nothing is stored. */
export function useGeolocation() {
  const [status, setStatus] = useState<GeoStatus>("idle");
  const [fix, setFix] = useState<GeoFix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const watchId = useRef<number | null>(null);

  const toFix = (p: GeolocationPosition): GeoFix => ({
    lat: p.coords.latitude,
    lng: p.coords.longitude,
    accuracy: p.coords.accuracy,
    timestamp: p.timestamp,
  });

  const locateOnce = useCallback((): Promise<GeoFix | null> => {
    const issue = geolocationSupportIssue();
    if (issue) {
      setStatus("error");
      setError(issue);
      return Promise.resolve(null);
    }
    setStatus("requesting");
    setError(null);
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (p) => {
          const f = toFix(p);
          setFix(f);
          setError(null);
          setStatus(watchId.current !== null ? "tracking" : "ok");
          resolve(f);
        },
        (e) => {
          setStatus("error");
          setError(describe(e));
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
      );
    });
  }, []);

  const stopTracking = useCallback(() => {
    if (watchId.current !== null) {
      navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
    }
    setError(null);
    setStatus((s) => (s === "tracking" || s === "requesting" ? "ok" : s));
  }, []);

  const startTracking = useCallback(() => {
    const issue = geolocationSupportIssue();
    if (issue) {
      setStatus("error");
      setError(issue);
      return;
    }
    if (watchId.current !== null) return;
    setError(null);
    setStatus("requesting");
    watchId.current = navigator.geolocation.watchPosition(
      (p) => {
        setFix(toFix(p));
        setError(null);
        setStatus("tracking");
      },
      (e) => {
        setError(describe(e));
        if (e.code === 1) {
          if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
          watchId.current = null;
          setStatus("error");
        }
      },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 5000 },
    );
  }, []);

  /** Hide the last one-shot status/error (e.g. after the user switches to manual coordinates). */
  const dismiss = useCallback(() => {
    if (watchId.current !== null) return;
    setError(null);
    setStatus("idle");
  }, []);

  useEffect(() => () => {
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
  }, []);

  return { status, fix, error, locateOnce, startTracking, stopTracking, dismiss, tracking: status === "tracking" };
}
