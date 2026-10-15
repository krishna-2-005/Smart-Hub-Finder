import { describe, expect, it } from "vitest";
import { fmtKm, fmtMeters, fmtMinutes, strategyLabel } from "./format";
import { haversineMeters } from "./geo";
import { splitPastedPair, validateCoordinates } from "./validation";

describe("validateCoordinates", () => {
  it("accepts decimal and negative coordinates", () => {
    expect(validateCoordinates("17.4485", "78.3908")).toEqual({ ok: true, latitude: 17.4485, longitude: 78.3908 });
    expect(validateCoordinates("-33.8688", "151.2093")).toMatchObject({ ok: true, latitude: -33.8688 });
    expect(validateCoordinates(" 90 ", "-180")).toMatchObject({ ok: true, latitude: 90, longitude: -180 });
    expect(validateCoordinates(".5", "+1.25")).toMatchObject({ ok: true, latitude: 0.5, longitude: 1.25 });
  });

  it("rejects out-of-range values", () => {
    const r = validateCoordinates("90.0001", "181");
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.errors.latitude).toBe("Latitude must be between -90 and 90.");
      expect(r.errors.longitude).toBe("Longitude must be between -180 and 180.");
    }
  });

  it("rejects missing and non-numeric values", () => {
    const r = validateCoordinates("", "abc");
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.errors.latitude).toBe("Latitude is required.");
      expect(r.errors.longitude).toMatch(/must be a number/);
    }
    for (const bad of ["17,44", "1e", "NaN", "Infinity", "17.4.4", "--1", "0x11"]) {
      expect(validateCoordinates(bad, "78").ok).toBe(false);
    }
  });
});

describe("splitPastedPair", () => {
  it("splits Google Maps style pairs", () => {
    expect(splitPastedPair("17.4485, 78.3908")).toEqual({ lat: "17.4485", lng: "78.3908" });
    expect(splitPastedPair("(17.4485,78.3908)")).toEqual({ lat: "17.4485", lng: "78.3908" });
    expect(splitPastedPair("-33.86 151.20")).toEqual({ lat: "-33.86", lng: "151.20" });
  });
  it("ignores single numbers and text", () => {
    expect(splitPastedPair("17.4485")).toBeNull();
    expect(splitPastedPair("Hitech City")).toBeNull();
  });
});

describe("formatting", () => {
  it("formats distances and durations", () => {
    expect(fmtKm(0.913)).toBe("0.91 km");
    expect(fmtKm(15.141)).toBe("15.1 km");
    expect(fmtKm(null)).toBe("—");
    expect(fmtMeters(850)).toBe("850 m");
    expect(fmtMeters(1500)).toBe("1.50 km");
    expect(fmtMinutes(0.4)).toBe("< 1 min");
    expect(fmtMinutes(20.1)).toBe("20 min");
    expect(fmtMinutes(95)).toBe("1 h 35 min");
    expect(strategyLabel("progressive (capped)")).toBe("Progressive, capped shortlist");
  });
});

describe("haversineMeters", () => {
  it("matches a known distance", () => {
    const d = haversineMeters(17.3616, 78.4747, 17.3833, 78.4011);
    expect(d).toBeGreaterThan(8000);
    expect(d).toBeLessThan(8600);
  });
});
