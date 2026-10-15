"""Road-network routing behind a provider abstraction.

Providers
---------
* ``google`` - Google Maps Routes API (computeRoutes + computeRouteMatrix).
  Needs ``GOOGLE_MAPS_API_KEY``.
* ``osrm``   - OSRM HTTP API. Defaults to the public OpenStreetMap demo servers
  (car: router.project-osrm.org, bike/foot: routing.openstreetmap.de). No key.
* ``ors``    - OpenRouteService. Needs ``ORS_API_KEY``.

Every provider returns real road-network distance, duration and route
geometry. Nothing in this module ever substitutes a straight line: when a
provider fails, a :class:`RoutingError` is raised and surfaced to the user.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from ..config import Settings
from .geo_utils import decode_polyline, haversine_km

log = logging.getLogger(__name__)

TRAVEL_MODES = ("driving", "two_wheeler", "cycling", "walking")
LatLng = tuple[float, float]


class RoutingError(Exception):
    """A routing request could not be answered. ``code`` is machine-readable."""

    def __init__(self, code: str, message: str, provider: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "provider": self.provider}


@dataclass
class MatrixCell:
    distance_m: float | None
    duration_s: float | None
    snap_distance_m: float | None
    status: str  # ok | no_route


@dataclass
class MatrixResult:
    cells: list[MatrixCell]
    origin_snapped: LatLng | None
    origin_snap_m: float | None
    requests: int


@dataclass
class RouteStep:
    instruction: str
    distance_m: float
    duration_s: float
    maneuver: str | None
    road_name: str | None
    location: LatLng | None


@dataclass
class RouteResult:
    provider: str
    provider_label: str
    travel_mode: str
    distance_m: float
    duration_s: float
    geometry: list[LatLng]
    steps: list[RouteStep] = field(default_factory=list)
    summary: str | None = None
    origin_snapped: LatLng | None = None
    destination_snapped: LatLng | None = None
    origin_snap_m: float | None = None
    destination_snap_m: float | None = None
    alternatives: list["RouteResult"] = field(default_factory=list)
    traffic_aware: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["distance_km"] = round(self.distance_m / 1000, 3)
        d["duration_min"] = round(self.duration_s / 60, 1)
        d["point_count"] = len(self.geometry)
        if self.geometry:
            lats = [p[0] for p in self.geometry]
            lngs = [p[1] for p in self.geometry]
            d["bbox"] = [min(lats), min(lngs), max(lats), max(lngs)]
        for alt in d["alternatives"]:
            alt["distance_km"] = round(alt["distance_m"] / 1000, 3)
            alt["duration_min"] = round(alt["duration_s"] / 60, 1)
            alt["point_count"] = len(alt["geometry"])
            alt.pop("steps", None)
            alt.pop("alternatives", None)
        return d


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

RETRY_STATUS = {429, 500, 502, 503, 504}


async def _request(client: httpx.AsyncClient, provider: str, method: str, url: str, **kw: Any) -> Any:
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = await client.request(method, url, **kw)
            if resp.status_code in RETRY_STATUS and attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                detail = resp.text[:300]
                if resp.status_code in (401, 403):
                    raise RoutingError("auth_failed", f"{provider} rejected the API key ({resp.status_code}): {detail}", provider)
                if resp.status_code == 429:
                    raise RoutingError("rate_limited", f"{provider} rate limit reached; try again shortly", provider)
                raise RoutingError("provider_error", f"{provider} returned HTTP {resp.status_code}: {detail}", provider)
            return resp.json()
        except httpx.TimeoutException as exc:
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
        if attempt < 2:
            await asyncio.sleep(0.8 * (attempt + 1))
    if isinstance(last_exc, httpx.TimeoutException):
        raise RoutingError("timeout", f"{provider} did not respond in time", provider)
    raise RoutingError("network_error", f"Could not reach {provider}: {last_exc!r}", provider)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class RoutingProvider(ABC):
    name: str = ""
    label: str = ""
    matrix_batch_size: int = 25

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    def supported_modes(self) -> list[str]: ...

    def not_configured_reason(self) -> str | None:
        return None

    def check_mode(self, mode: str) -> None:
        if mode not in self.supported_modes():
            raise RoutingError(
                "unsupported_mode",
                f"{self.label} does not support travel mode '{mode}'. Supported: {', '.join(self.supported_modes())}",
                self.name,
            )

    @abstractmethod
    async def _matrix_batch(self, origin: LatLng, dests: list[LatLng], mode: str) -> MatrixResult: ...

    async def matrix(self, origin: LatLng, dests: list[LatLng], mode: str) -> MatrixResult:
        self.check_mode(mode)
        cells: list[MatrixCell] = []
        origin_snapped = origin_snap = None
        requests = 0
        for i in range(0, len(dests), self.matrix_batch_size):
            part = await self._matrix_batch(origin, dests[i : i + self.matrix_batch_size], mode)
            cells.extend(part.cells)
            origin_snapped = origin_snapped or part.origin_snapped
            origin_snap = origin_snap if origin_snap is not None else part.origin_snap_m
            requests += part.requests
        return MatrixResult(cells, origin_snapped, origin_snap, requests)

    @abstractmethod
    async def route(self, origin: LatLng, dest: LatLng, mode: str, alternatives: bool = True) -> RouteResult: ...


def _ordinal(n: int) -> str:
    return f"{n}{'tsnrhtdd'[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10::4]}"


def _compass(bearing: float | None) -> str:
    if bearing is None:
        return ""
    dirs = ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"]
    return dirs[int(((bearing % 360) + 22.5) // 45) % 8]


def osrm_instruction(step: dict[str, Any]) -> str:
    m = step.get("maneuver", {})
    t = m.get("type", "")
    mod = m.get("modifier")
    name = step.get("name") or step.get("ref") or ""
    onto = f" onto {name}" if name else ""
    if t == "depart":
        return f"Head {_compass(m.get('bearing_after'))}" + (f" on {name}" if name else "")
    if t == "arrive":
        side = f" on the {mod}" if mod in ("left", "right") else ""
        return f"Arrive at the destination{side}"
    if t in ("roundabout", "rotary", "roundabout turn"):
        exit_no = m.get("exit")
        rname = step.get("rotary_name")
        what = f"the {rname} roundabout" if rname else "the roundabout"
        return f"Enter {what}" + (f" and take the {_ordinal(exit_no)} exit" if exit_no else "") + onto
    if t in ("exit roundabout", "exit rotary"):
        return f"Exit the roundabout{onto}"
    direction = {
        "uturn": "Make a U-turn", "sharp right": "Turn sharp right", "right": "Turn right",
        "slight right": "Bear right", "straight": "Continue straight", "slight left": "Bear left",
        "left": "Turn left", "sharp left": "Turn sharp left",
    }.get(mod or "", "Continue")
    if t == "new name":
        return f"Continue{onto}" if name else "Continue"
    if t == "merge":
        return f"Merge {mod or ''}{onto}".replace("  ", " ")
    if t == "on ramp":
        return f"Take the ramp{' on the ' + mod if mod in ('left', 'right') else ''}{onto}"
    if t == "off ramp":
        return f"Take the exit{' on the ' + mod if mod in ('left', 'right') else ''}{onto}"
    if t == "fork":
        side = "left" if mod and "left" in mod else "right" if mod and "right" in mod else ""
        return f"Keep {side} at the fork{onto}".replace("  ", " ")
    if t == "end of road":
        return f"At the end of the road, {direction.lower()}{onto}"
    if t == "continue":
        return f"{direction}{onto}" if mod and mod != "straight" else f"Continue straight{onto}"
    return f"{direction}{onto}"


class OsrmProvider(RoutingProvider):
    name = "osrm"
    label = "OSRM (OpenStreetMap road network)"
    matrix_batch_size = 90  # public servers accept up to 100 coordinates per table request

    def configured(self) -> bool:
        return True

    def _base(self, mode: str) -> str:
        return {
            "driving": self.settings.osrm_driving_url,
            "cycling": self.settings.osrm_cycling_url,
            "walking": self.settings.osrm_walking_url,
        }[mode].rstrip("/")

    def supported_modes(self) -> list[str]:
        return ["driving", "cycling", "walking"]

    async def _matrix_batch(self, origin: LatLng, dests: list[LatLng], mode: str) -> MatrixResult:
        coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in [origin, *dests])
        dest_idx = ";".join(str(i) for i in range(1, len(dests) + 1))
        url = f"{self._base(mode)}/table/v1/driving/{coords}"
        data = await _request(self.client, self.name, "GET", url, params={
            "sources": "0", "destinations": dest_idx, "annotations": "distance,duration",
        })
        if data.get("code") != "Ok":
            raise RoutingError("provider_error", f"OSRM table error: {data.get('code')} {data.get('message', '')}", self.name)
        dists = data["distances"][0]
        durs = data["durations"][0]
        dmeta = data.get("destinations", [{}] * len(dests))
        cells = []
        for j in range(len(dests)):
            ok = dists[j] is not None and durs[j] is not None
            cells.append(MatrixCell(
                distance_m=dists[j], duration_s=durs[j],
                snap_distance_m=dmeta[j].get("distance") if j < len(dmeta) else None,
                status="ok" if ok else "no_route",
            ))
        src = (data.get("sources") or [{}])[0]
        loc = src.get("location")
        return MatrixResult(cells, (loc[1], loc[0]) if loc else None, src.get("distance"), 1)

    async def route(self, origin: LatLng, dest: LatLng, mode: str, alternatives: bool = True) -> RouteResult:
        self.check_mode(mode)
        url = f"{self._base(mode)}/route/v1/driving/{origin[1]:.6f},{origin[0]:.6f};{dest[1]:.6f},{dest[0]:.6f}"
        data = await _request(self.client, self.name, "GET", url, params={
            "overview": "full", "geometries": "polyline6", "steps": "true",
            "alternatives": "2" if alternatives else "false",
        })
        if data.get("code") == "NoRoute" or not data.get("routes"):
            raise RoutingError("no_route", "No road route exists between these points", self.name)
        if data.get("code") != "Ok":
            raise RoutingError("provider_error", f"OSRM route error: {data.get('code')} {data.get('message', '')}", self.name)
        wps = data.get("waypoints") or [{}, {}]

        def build(r: dict[str, Any], with_steps: bool) -> RouteResult:
            steps = []
            if with_steps:
                for leg in r.get("legs", []):
                    for s in leg.get("steps", []):
                        loc = s.get("maneuver", {}).get("location")
                        steps.append(RouteStep(
                            instruction=osrm_instruction(s),
                            distance_m=s.get("distance", 0.0), duration_s=s.get("duration", 0.0),
                            maneuver=" ".join(x for x in (s.get("maneuver", {}).get("type"),
                                                          s.get("maneuver", {}).get("modifier")) if x) or None,
                            road_name=s.get("name") or s.get("ref") or None,
                            location=(loc[1], loc[0]) if loc else None,
                        ))
            o_loc, d_loc = wps[0].get("location"), wps[-1].get("location")
            return RouteResult(
                provider=self.name, provider_label=self.label, travel_mode=mode,
                distance_m=r["distance"], duration_s=r["duration"],
                geometry=decode_polyline(r["geometry"], precision=6),
                steps=steps,
                summary=", ".join(leg.get("summary", "") for leg in r.get("legs", []) if leg.get("summary")) or None,
                origin_snapped=(o_loc[1], o_loc[0]) if o_loc else None,
                destination_snapped=(d_loc[1], d_loc[0]) if d_loc else None,
                origin_snap_m=wps[0].get("distance"), destination_snap_m=wps[-1].get("distance"),
            )

        routes = data["routes"]
        primary = build(routes[0], True)
        primary.alternatives = [build(r, False) for r in routes[1:]]
        return primary


class GoogleRoutesProvider(RoutingProvider):
    name = "google"
    label = "Google Maps Routes API"
    matrix_batch_size = 25
    MODES = {"driving": "DRIVE", "two_wheeler": "TWO_WHEELER", "cycling": "BICYCLE", "walking": "WALK"}

    def configured(self) -> bool:
        return bool(self.settings.google_maps_api_key)

    def not_configured_reason(self) -> str | None:
        return None if self.configured() else "GOOGLE_MAPS_API_KEY is not set in backend/.env"

    def supported_modes(self) -> list[str]:
        return list(self.MODES)

    def _headers(self, field_mask: str) -> dict[str, str]:
        if not self.configured():
            raise RoutingError("not_configured", self.not_configured_reason() or "", self.name)
        return {
            "X-Goog-Api-Key": self.settings.google_maps_api_key or "",
            "X-Goog-FieldMask": field_mask,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _wp(p: LatLng) -> dict[str, Any]:
        return {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}

    def _traffic(self, mode: str) -> dict[str, Any]:
        return {"routingPreference": "TRAFFIC_AWARE"} if mode in ("driving", "two_wheeler") else {}

    @staticmethod
    def _secs(v: str | None) -> float | None:
        if not v:
            return None
        return float(v.rstrip("s"))

    async def _matrix_batch(self, origin: LatLng, dests: list[LatLng], mode: str) -> MatrixResult:
        body = {
            "origins": [{"waypoint": self._wp(origin)}],
            "destinations": [{"waypoint": self._wp(d)} for d in dests],
            "travelMode": self.MODES[mode],
            **self._traffic(mode),
        }
        data = await _request(
            self.client, self.name, "POST",
            "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
            json=body, headers=self._headers("originIndex,destinationIndex,distanceMeters,duration,condition,status"),
        )
        if isinstance(data, dict) and data.get("error"):
            raise RoutingError("provider_error", f"Google: {data['error'].get('message')}", self.name)
        cells = [MatrixCell(None, None, None, "no_route") for _ in dests]
        for el in data:
            j = el.get("destinationIndex", 0)
            if el.get("condition") == "ROUTE_EXISTS" and el.get("distanceMeters") is not None:
                cells[j] = MatrixCell(float(el["distanceMeters"]), self._secs(el.get("duration")), None, "ok")
        return MatrixResult(cells, None, None, 1)

    async def route(self, origin: LatLng, dest: LatLng, mode: str, alternatives: bool = True) -> RouteResult:
        self.check_mode(mode)
        body = {
            "origin": self._wp(origin), "destination": self._wp(dest),
            "travelMode": self.MODES[mode], **self._traffic(mode),
            "computeAlternativeRoutes": alternatives, "polylineQuality": "HIGH_QUALITY",
            "languageCode": "en-IN", "units": "METRIC",
        }
        mask = ("routes.distanceMeters,routes.duration,routes.polyline.encodedPolyline,routes.description,"
                "routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration,"
                "routes.legs.steps.navigationInstruction,routes.legs.steps.startLocation")
        data = await _request(self.client, self.name, "POST",
                              "https://routes.googleapis.com/directions/v2:computeRoutes",
                              json=body, headers=self._headers(mask))
        routes = data.get("routes") or []
        if not routes:
            raise RoutingError("no_route", "Google found no route between these points", self.name)

        def build(r: dict[str, Any]) -> RouteResult:
            geom = decode_polyline(r["polyline"]["encodedPolyline"], precision=5)
            steps = []
            for leg in r.get("legs", []):
                for s in leg.get("steps", []):
                    ni = s.get("navigationInstruction") or {}
                    ll = (s.get("startLocation") or {}).get("latLng")
                    steps.append(RouteStep(
                        instruction=ni.get("instructions") or ni.get("maneuver", "Continue").replace("_", " ").title(),
                        distance_m=float(s.get("distanceMeters", 0)),
                        duration_s=self._secs(s.get("staticDuration")) or 0.0,
                        maneuver=(ni.get("maneuver") or "").lower().replace("_", " ") or None,
                        road_name=None,
                        location=(ll["latitude"], ll["longitude"]) if ll else None,
                    ))
            return RouteResult(
                provider=self.name, provider_label=self.label, travel_mode=mode,
                distance_m=float(r.get("distanceMeters", 0)), duration_s=self._secs(r.get("duration")) or 0.0,
                geometry=geom, steps=steps, summary=r.get("description"),
                origin_snapped=geom[0] if geom else None, destination_snapped=geom[-1] if geom else None,
                origin_snap_m=haversine_km(*origin, *geom[0]) * 1000 if geom else None,
                destination_snap_m=haversine_km(*dest, *geom[-1]) * 1000 if geom else None,
                traffic_aware=mode in ("driving", "two_wheeler"),
            )

        primary = build(routes[0])
        primary.alternatives = [build(r) for r in routes[1:]]
        return primary


class OpenRouteServiceProvider(RoutingProvider):
    name = "ors"
    label = "OpenRouteService"
    matrix_batch_size = 50
    PROFILES = {"driving": "driving-car", "cycling": "cycling-regular", "walking": "foot-walking"}

    def configured(self) -> bool:
        return bool(self.settings.ors_api_key)

    def not_configured_reason(self) -> str | None:
        return None if self.configured() else "ORS_API_KEY is not set in backend/.env"

    def supported_modes(self) -> list[str]:
        return list(self.PROFILES)

    def _headers(self) -> dict[str, str]:
        if not self.configured():
            raise RoutingError("not_configured", self.not_configured_reason() or "", self.name)
        return {"Authorization": self.settings.ors_api_key or "", "Content-Type": "application/json"}

    async def _matrix_batch(self, origin: LatLng, dests: list[LatLng], mode: str) -> MatrixResult:
        locs = [[p[1], p[0]] for p in [origin, *dests]]
        data = await _request(
            self.client, self.name, "POST",
            f"https://api.openrouteservice.org/v2/matrix/{self.PROFILES[mode]}",
            json={"locations": locs, "sources": [0], "destinations": list(range(1, len(locs))),
                  "metrics": ["distance", "duration"], "units": "m"},
            headers=self._headers(),
        )
        dists, durs = data["distances"][0], data["durations"][0]
        dmeta = data.get("destinations") or [{}] * len(dests)
        cells = [
            MatrixCell(dists[j], durs[j], (dmeta[j] or {}).get("snapped_distance"),
                       "ok" if dists[j] is not None and durs[j] is not None else "no_route")
            for j in range(len(dests))
        ]
        src = (data.get("sources") or [{}])[0] or {}
        loc = src.get("location")
        return MatrixResult(cells, (loc[1], loc[0]) if loc else None, src.get("snapped_distance"), 1)

    async def route(self, origin: LatLng, dest: LatLng, mode: str, alternatives: bool = True) -> RouteResult:
        self.check_mode(mode)
        body: dict[str, Any] = {
            "coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]],
            "instructions": True, "geometry_simplify": False, "units": "m",
        }
        if alternatives:
            body["alternative_routes"] = {"target_count": 2, "weight_factor": 1.4, "share_factor": 0.6}
        data = await _request(self.client, self.name, "POST",
                              f"https://api.openrouteservice.org/v2/directions/{self.PROFILES[mode]}/geojson",
                              json=body, headers=self._headers())
        feats = data.get("features") or []
        if not feats:
            raise RoutingError("no_route", "OpenRouteService found no route", self.name)

        def build(f: dict[str, Any], with_steps: bool) -> RouteResult:
            coords = [(c[1], c[0]) for c in f["geometry"]["coordinates"]]
            props = f.get("properties", {})
            steps = []
            if with_steps:
                for seg in props.get("segments", []):
                    for s in seg.get("steps", []):
                        wp = (s.get("way_points") or [0])[0]
                        steps.append(RouteStep(
                            instruction=s.get("instruction", ""), distance_m=s.get("distance", 0.0),
                            duration_s=s.get("duration", 0.0), maneuver=str(s.get("type")),
                            road_name=(s.get("name") or None) if s.get("name") != "-" else None,
                            location=coords[wp] if wp < len(coords) else None,
                        ))
            summ = props.get("summary", {})
            return RouteResult(
                provider=self.name, provider_label=self.label, travel_mode=mode,
                distance_m=float(summ.get("distance", 0)), duration_s=float(summ.get("duration", 0)),
                geometry=coords, steps=steps,
                origin_snapped=coords[0] if coords else None, destination_snapped=coords[-1] if coords else None,
                origin_snap_m=haversine_km(*origin, *coords[0]) * 1000 if coords else None,
                destination_snap_m=haversine_km(*dest, *coords[-1]) * 1000 if coords else None,
            )

        primary = build(feats[0], True)
        primary.alternatives = [build(f, False) for f in feats[1:]]
        return primary


# ---------------------------------------------------------------------------
# Service facade (provider selection + caching)
# ---------------------------------------------------------------------------

class _TTLCache:
    def __init__(self, ttl_s: float = 3600, max_items: int = 512):
        self.ttl, self.max = ttl_s, max_items
        self._d: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any:
        hit = self._d.get(key)
        if hit is None or time.monotonic() - hit[0] > self.ttl:
            self._d.pop(key, None)
            return None
        return hit[1]

    def set(self, key: Any, value: Any) -> None:
        if len(self._d) >= self.max:
            self._d.pop(next(iter(self._d)))
        self._d[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._d.clear()


def _rk(p: LatLng) -> tuple[float, float]:
    return (round(p[0], 6), round(p[1], 6))


class RoutingService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.routing_timeout_s, connect=10.0),
            headers={"User-Agent": settings.routing_user_agent},
            follow_redirects=True,
        )
        self.providers: dict[str, RoutingProvider] = {
            p.name: p
            for p in (
                GoogleRoutesProvider(settings, self.client),
                OsrmProvider(settings, self.client),
                OpenRouteServiceProvider(settings, self.client),
            )
        }
        self._matrix_cache = _TTLCache()
        self._route_cache = _TTLCache()

    async def aclose(self) -> None:
        await self.client.aclose()

    def resolve(self, name: str | None = None) -> RoutingProvider:
        name = (name or self.settings.routing_provider or "auto").lower()
        if name == "auto":
            google = self.providers["google"]
            return google if google.configured() else self.providers["osrm"]
        if name not in self.providers:
            raise RoutingError("unknown_provider", f"Unknown routing provider '{name}'", name)
        p = self.providers[name]
        if not p.configured():
            raise RoutingError("not_configured", f"{p.label} is not configured: {p.not_configured_reason()}", name)
        return p

    def status(self, preferred: str | None = None) -> dict[str, Any]:
        try:
            active = self.resolve(preferred).name
            error = None
        except RoutingError as exc:
            active, error = None, exc.message
        return {
            "preferred": preferred or self.settings.routing_provider,
            "active": active,
            "error": error,
            "providers": [
                {
                    "name": p.name, "label": p.label, "configured": p.configured(),
                    "reason": p.not_configured_reason(), "modes": p.supported_modes(),
                    "requires_key": p.name in ("google", "ors"),
                }
                for p in self.providers.values()
            ],
        }

    async def matrix(self, provider: RoutingProvider, origin: LatLng, dests: list[LatLng], mode: str) -> MatrixResult:
        key = (provider.name, mode, _rk(origin), tuple(_rk(d) for d in dests))
        hit = self._matrix_cache.get(key)
        if hit is not None:
            return MatrixResult(hit.cells, hit.origin_snapped, hit.origin_snap_m, 0)
        res = await provider.matrix(origin, dests, mode)
        self._matrix_cache.set(key, res)
        return res

    async def route(self, provider: RoutingProvider, origin: LatLng, dest: LatLng, mode: str,
                    alternatives: bool = True) -> RouteResult:
        key = (provider.name, mode, _rk(origin), _rk(dest), alternatives)
        hit = self._route_cache.get(key)
        if hit is not None:
            return hit
        res = await provider.route(origin, dest, mode, alternatives)
        if len(res.geometry) < 2:
            raise RoutingError("invalid_geometry", "Routing provider returned no usable route geometry", provider.name)
        self._route_cache.set(key, res)
        return res

    async def self_test(self, preferred: str | None = None, mode: str = "driving") -> dict[str, Any]:
        """Live connectivity check with a short real route in Hyderabad."""
        t0 = time.perf_counter()
        try:
            p = self.resolve(preferred)
            r = await p.route((17.4474, 78.3762), (17.4401, 78.3489), mode, alternatives=False)
            return {"ok": True, "provider": p.name, "label": p.label, "mode": mode,
                    "distance_m": r.distance_m, "duration_s": r.duration_s, "geometry_points": len(r.geometry),
                    "latency_ms": round((time.perf_counter() - t0) * 1000)}
        except RoutingError as exc:
            return {"ok": False, **exc.to_dict(), "latency_ms": round((time.perf_counter() - t0) * 1000)}
