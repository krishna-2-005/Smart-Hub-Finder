"""Rule-based placemark classification (hubs, cluster boundaries, regions, ...).

Nothing here assumes every placemark is a hub: a placemark is a hub only if it
satisfies the configured ``hub.match_any`` rule (by default: it carries a
``Hub ID`` attribute, or both ``Hub`` and ``Cluster`` attributes).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shapely import wkt as shapely_wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from .geo_utils import area_km2
from .kml_parser import ParsedPlacemark

UNNAMED_RE = re.compile(r"^unnamed \(\d+\)$")
# UTF-8 bytes mis-decoded as Latin-1 (e.g. "â€‹", "ã¢"): a lead char followed by C1/Latin-1 symbols.
MOJIBAKE_RE = re.compile("[ÂÃâã][\u0080-¿]+|�")


def load_classification_config(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class Classification:
    category: str
    label: str
    reason: str
    inferred: bool = False
    pii: bool = False


@dataclass
class HubRecord:
    hub_id: str | None
    name: str | None
    display_name: str | None
    hub_code: str | None
    latitude: float | None
    longitude: float | None
    location_method: str | None
    cluster_raw: str | None
    cluster_id: str | None = None
    cluster_name: str | None = None
    cluster_source: str | None = None
    region: str | None = None
    status: str | None = None
    is_active: bool | None = None
    hub_type: str | None = None
    cluster_mapping: str | None = None
    priority: str | None = None
    demand_level: str | None = None
    original_folder: str | None = None
    source_line: int | None = None
    placemark_index: int | None = None
    service_area: BaseGeometry | None = None
    service_area_km2: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    valid: bool = True


def _norm_field(data: dict[str, str], key: str | None) -> str | None:
    if not key:
        return None
    v = data.get(key)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _matches_fields(pm: ParsedPlacemark, fields: list[str]) -> bool:
    return all(f in pm.extended_data for f in fields)


def _geom_kind(pm: ParsedPlacemark) -> str | None:
    return pm.geometry.geom_type if pm.geometry is not None else None


def classify_placemark(pm: ParsedPlacemark, cfg: dict[str, Any]) -> Classification:
    hub_cfg = cfg["hub"]
    for rule in hub_cfg["match_any"]:
        if _matches_fields(pm, rule["fields"]):
            return Classification("hub", "Hub", f"has attribute(s) {rule['fields']}")

    cb = cfg.get("cluster_boundary") or {}
    if cb and _geom_kind(pm) in cb["geometry_types"] and pm.name and re.search(cb["name_pattern"], pm.name.strip()):
        return Classification(
            "cluster_boundary", "Cluster boundary", f"polygon whose name matches /{cb['name_pattern']}/"
        )

    rg = cfg.get("region") or {}
    if rg and pm.folder and re.search(rg["folder_pattern"], pm.folder) and _geom_kind(pm) in rg["geometry_types"]:
        return Classification("region", "Service line / region", f"polygon in folder matching /{rg['folder_pattern']}/")

    for rule in cfg.get("other_categories", []):
        ok = True
        reasons = []
        if "fields" in rule:
            ok &= _matches_fields(pm, rule["fields"])
            reasons.append(f"attributes {rule['fields']}")
        if "folder_pattern" in rule:
            ok &= bool(pm.folder and re.search(rule["folder_pattern"], pm.folder))
            reasons.append(f"folder /{rule['folder_pattern']}/")
        if "geometry_types" in rule:
            ok &= _geom_kind(pm) in rule["geometry_types"]
            reasons.append(f"geometry {rule['geometry_types']}")
        if ok:
            return Classification(
                rule["category"],
                rule.get("label", rule["category"]),
                "matched " + ", ".join(reasons),
                inferred=bool(rule.get("inferred")),
                pii=bool(rule.get("pii")),
            )

    return Classification("unclassified", "Unclassified", "no rule matched")


def display_name(raw: str | None) -> str | None:
    if not raw:
        return raw
    words = re.split(r"[_\s]+", raw.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w)


def derive_location(geom: BaseGeometry | None) -> tuple[float | None, float | None, str | None]:
    """Representative hub location ``(lat, lng, method)``.

    Point hubs use their coordinate directly. Polygon hubs (service areas) have
    no explicit hub point in the source, so the polygon centroid is used when it
    falls inside the polygon, otherwise shapely's representative point (always
    inside). The method is recorded so the UI/report can label it as inferred.
    """
    if geom is None or geom.is_empty:
        return None, None, None
    gt = geom.geom_type
    if gt == "Point":
        return geom.y, geom.x, "point_geometry"
    if gt == "MultiPoint":
        c = geom.centroid
        return c.y, c.x, "multipoint_centroid"
    if gt in ("Polygon", "MultiPolygon", "GeometryCollection"):
        target = geom
        if gt != "Polygon":
            polys = [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]
            if polys:
                target = max(polys, key=lambda g: g.area)
        c = target.centroid
        if target.contains(c):
            return c.y, c.x, "service_area_centroid"
        rp = target.representative_point()
        return rp.y, rp.x, "service_area_interior_point"
    c = geom.centroid
    return c.y, c.x, f"{gt.lower()}_centroid"


def build_hub(pm: ParsedPlacemark, cfg: dict[str, Any]) -> HubRecord:
    hub_cfg = cfg["hub"]
    f = hub_cfg["fields"]
    data = pm.extended_data
    issues = list(pm.issues)

    geom = pm.analysis_geometry()
    lat, lng, method = derive_location(geom)

    name = pm.name if hub_cfg.get("name_source") == "placemark_name" else _norm_field(data, f.get("hub_code"))
    name = (name or _norm_field(data, f.get("hub_code")) or None)
    if not name:
        issues.append("missing hub name")
    clean_name = name
    if name and MOJIBAKE_RE.search(name):
        clean_name = MOJIBAKE_RE.sub("", name)
        issues.append(
            f"hub name contains garbled encoding characters {MOJIBAKE_RE.findall(name)!r}; kept unchanged in "
            f"'name', removed from 'display_name'"
        )

    hub_id = _norm_field(data, f.get("hub_id"))
    if not hub_id:
        issues.append("missing hub ID")

    status = _norm_field(data, f.get("status"))
    active_values = {v.lower() for v in hub_cfg.get("active_status_values", [])}
    is_active = (status.lower() in active_values) if status else None

    drop = set(hub_cfg.get("drop_metadata_fields", []))
    metadata: dict[str, str] = {}
    for k, v in data.items():
        if k in drop:
            continue
        if hub_cfg.get("drop_empty_unnamed_fields") and UNNAMED_RE.match(k) and not v.strip():
            continue
        metadata[k] = v

    wkt_field = hub_cfg.get("compare_wkt_field")
    if wkt_field and data.get(wkt_field):
        try:
            other = shapely_wkt.loads(data[wkt_field])
            if pm.geometry is not None and not other.equals_exact(pm.geometry, tolerance=1e-6):
                # ~111 km per degree; adequate for reporting the size of the discrepancy
                dev_m = other.hausdorff_distance(pm.geometry) * 111_000
                union = other.union(pm.geometry).area
                overlap = other.intersection(pm.geometry).area / union if union else 0
                issues.append(
                    f"'{wkt_field}' WKT attribute differs from the drawn polygon (max deviation ≈{dev_m:.0f} m, "
                    f"{overlap * 100:.0f}% area overlap); the drawn polygon is used"
                )
        except Exception:  # noqa: BLE001 - report, don't fail
            issues.append(f"'{wkt_field}' WKT attribute could not be parsed")

    service_area = geom if geom is not None and geom.geom_type in ("Polygon", "MultiPolygon") else None
    valid = lat is not None and lng is not None

    return HubRecord(
        hub_id=hub_id,
        name=name,
        display_name=display_name(clean_name),
        hub_code=_norm_field(data, f.get("hub_code")),
        latitude=round(lat, 7) if lat is not None else None,
        longitude=round(lng, 7) if lng is not None else None,
        location_method=method,
        cluster_raw=_norm_field(data, f.get("cluster")),
        region=_norm_field(data, f.get("region")),
        status=status,
        is_active=is_active,
        hub_type=_norm_field(data, f.get("hub_type")),
        cluster_mapping=_norm_field(data, f.get("cluster_mapping")),
        priority=_norm_field(data, f.get("priority")),
        demand_level=_norm_field(data, f.get("demand_level")),
        original_folder=pm.folder,
        source_line=pm.source_line,
        placemark_index=pm.index,
        service_area=service_area,
        service_area_km2=area_km2(service_area),
        metadata=metadata,
        issues=issues,
        valid=valid,
    )


def point_of(h: HubRecord) -> Point | None:
    if h.latitude is None or h.longitude is None:
        return None
    return Point(h.longitude, h.latitude)
