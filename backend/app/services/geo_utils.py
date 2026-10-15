"""Geodesic helpers shared by the services.

Haversine distance is used ONLY for geographic pre-filtering and as a
mathematical lower bound on road distance. It is never reported as a road
distance.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def validate_lat_lng(lat: object, lng: object) -> list[str]:
    """Return human-readable validation errors (empty list when valid)."""
    errors: list[str] = []
    for label, value, lo, hi in (("Latitude", lat, -90, 90), ("Longitude", lng, -180, 180)):
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{label} is required.")
            continue
        try:
            num = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            errors.append(f"{label} must be a number.")
            continue
        if math.isnan(num) or math.isinf(num):
            errors.append(f"{label} must be a finite number.")
        elif not lo <= num <= hi:
            errors.append(f"{label} must be between {lo} and {hi}.")
    return errors


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline into ``[(lat, lng), ...]``.

    OSRM uses the same algorithm with ``precision=6`` when ``geometries=polyline6``.
    """
    coords: list[tuple[float, float]] = []
    index = lat = lng = 0
    factor = 10**precision
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                if index >= length:
                    raise ValueError("Malformed polyline string")
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lng += deltas[1]
        coords.append((lat / factor, lng / factor))
    return coords


def encode_polyline(points: Iterable[Sequence[float]], precision: int = 5) -> str:
    """Encode ``[(lat, lng), ...]`` as a polyline string (used in tests)."""
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lng = 0
    for lat, lng in points:
        ilat, ilng = round(lat * factor), round(lng * factor)
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)


def to_local_km(geom: BaseGeometry, lat0: float | None = None, lon0: float | None = None) -> BaseGeometry:
    """Project lon/lat geometry to a local equirectangular plane in kilometres.

    Accurate to well under 1% for city-scale geometries, which is all we use
    it for (areas and coverage radii).
    """
    if lat0 is None or lon0 is None:
        c = geom.centroid
        lon0, lat0 = c.x, c.y
    k_lat = math.pi * EARTH_RADIUS_KM / 180.0
    k_lon = k_lat * math.cos(math.radians(lat0))

    def _proj(x, y, z=None):
        return ((x - lon0) * k_lon, (y - lat0) * k_lat)

    return transform(_proj, geom)


def area_km2(geom: BaseGeometry | None) -> float | None:
    if geom is None or geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        return None
    return round(to_local_km(geom).area, 4)


def bbox_of(points: Iterable[tuple[float, float]]) -> list[float] | None:
    """``[(lat, lng)] -> [min_lat, min_lng, max_lat, max_lng]``."""
    pts = list(points)
    if not pts:
        return None
    lats = [p[0] for p in pts]
    lngs = [p[1] for p in pts]
    return [min(lats), min(lngs), max(lats), max(lngs)]


def google_maps_directions_url(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, travel_mode: str = "driving"
) -> str:
    mode = {
        "driving": "driving",
        "two_wheeler": "two-wheeler",
        "cycling": "bicycling",
        "walking": "walking",
    }.get(travel_mode, "driving")
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin_lat:.6f},{origin_lng:.6f}"
        f"&destination={dest_lat:.6f},{dest_lng:.6f}"
        f"&travelmode={mode}"
    )


def google_earth_web_url(lat: float, lng: float, range_m: float = 6000) -> str:
    """Camera link for Google Earth Web (``@lat,lng,altitude a,range d,fov y,heading h,tilt t,roll r``)."""
    return f"https://earth.google.com/web/@{lat:.6f},{lng:.6f},500a,{range_m:.0f}d,35y,0h,0t,0r"
