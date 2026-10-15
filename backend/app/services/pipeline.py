"""End-to-end KML processing pipeline.

source KML -> backup -> repair -> parse -> classify -> hubs/clusters/layers
-> quality checks -> JSON/GeoJSON/KML outputs + markdown analysis report.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import Point, mapping

from . import export_service
from .cluster_service import ClusterRecord, build_clusters, extract_boundaries, quality_checks
from .hub_classifier import (
    MOJIBAKE_RE,
    Classification,
    HubRecord,
    build_hub,
    classify_placemark,
    load_classification_config,
)
from .kml_parser import ParsedPlacemark, parse_kml_text
from .kml_repair import repair_kml_bytes
from .report_service import render_markdown_report

log = logging.getLogger(__name__)

REGION_COLORS = {"South": "#c2410c", "East": "#0369a1", "North": "#7e22ce"}


class KmlProcessingError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _num(v: str | None) -> float | int | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def hub_to_dict(h: HubRecord) -> dict[str, Any]:
    d = asdict(h)
    d.pop("service_area", None)
    d["location_inferred"] = bool(h.location_method and h.location_method != "point_geometry")
    d["has_service_area"] = h.service_area is not None
    return d


def cluster_to_dict(c: ClusterRecord) -> dict[str, Any]:
    d = asdict(c)
    d["boundary"] = mapping(c.boundary) if c.boundary is not None else None
    d.pop("key", None)
    return json.loads(json.dumps(d))  # tuples -> lists


def _feature(geom, props: dict[str, Any], fid: Any = None) -> dict[str, Any]:
    f = {"type": "Feature", "geometry": mapping(geom), "properties": props}
    if fid is not None:
        f["id"] = fid
    return f


def _fc(features: list[dict[str, Any]]) -> dict[str, Any]:
    return json.loads(json.dumps({"type": "FeatureCollection", "features": features}))


def _write_json(path: Path, obj: Any, indent: int | None = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent, default=str)


def process_kml(
    source_path: Path,
    output_dir: Path,
    config_path: Path,
    backup_path: Path | None = None,
    source_display_name: str | None = None,
) -> dict[str, Any]:
    """Process ``source_path`` and write all artefacts to ``output_dir``. Returns the analysis dict."""
    cfg = load_classification_config(config_path)
    data = source_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)

    if backup_path is not None:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        if not backup_path.exists() or hashlib.sha256(backup_path.read_bytes()).hexdigest() != sha:
            shutil.copy2(source_path, backup_path)

    # 1. Repair ----------------------------------------------------------------
    repair = repair_kml_bytes(data)
    if not repair.valid_after:
        raise KmlProcessingError(
            "KML is still not well-formed after safe automatic repairs",
            {"parse_error_before": repair.parse_error_before, "parse_error_after": repair.parse_error_after},
        )
    if not repair.coordinates_unchanged:
        raise KmlProcessingError("Repair would have modified coordinate data; aborting")
    (output_dir / "repaired_full.kml").write_text(repair.text, encoding="utf-8")

    # 2. Parse + classify -------------------------------------------------------
    parsed = parse_kml_text(repair.text)
    classified: list[tuple[ParsedPlacemark, Classification]] = [
        (pm, classify_placemark(pm, cfg)) for pm in parsed.placemarks
    ]

    hubs: list[HubRecord] = [build_hub(pm, cfg) for pm, c in classified if c.category == "hub"]
    strip = (cfg.get("cluster_boundary") or {}).get("name_strip_pattern", r"(?i)[ _-]?cluster$")
    boundaries = extract_boundaries([(pm, c) for pm, c in classified if c.category == "cluster_boundary"], strip)

    # 3. Clusters + quality ------------------------------------------------------
    clusters, cluster_notes = build_clusters(hubs, boundaries, cfg)
    quality = quality_checks(hubs, clusters, cfg)

    hub_dicts = [hub_to_dict(h) for h in hubs]
    cluster_dicts = [cluster_to_dict(c) for c in clusters]

    # 4. Other layers -------------------------------------------------------------
    region_cfg = cfg.get("region") or {}
    regions = []
    for pm, c in classified:
        if c.category != "region" or pm.analysis_geometry() is None:
            continue
        geom = pm.analysis_geometry()
        hub_line = (region_cfg.get("hub_region_mapping") or {}).get(pm.name or "")
        inside = [h for h in hubs if h.latitude is not None and geom.covers(Point(h.longitude, h.latitude))]
        line_hubs = [h for h in hubs if hub_line and h.region == hub_line]
        regions.append({
            "id": (pm.name or f"region{pm.index}").lower().replace(" ", "_"),
            "name": pm.name,
            "label": pm.extended_data.get("Cluster_name") or None,
            "hub_line": hub_line,
            "note": region_cfg.get("mapping_note"),
            "color": REGION_COLORS.get(pm.name or "", "#475569"),
            "hubs_inside_polygon": len(inside),
            "hubs_with_line_attribute": len(line_hubs),
            "line_hubs_inside_polygon": sum(1 for h in line_hubs if h in inside),
            "geometry": json.loads(json.dumps(mapping(geom))),
        })

    demand_features, competitor_features, route_features = [], [], []
    for pm, c in classified:
        g = pm.analysis_geometry()
        if g is None:
            continue
        ed = pm.extended_data
        if c.category == "demand_point" and g.geom_type == "Point":
            demand_features.append(_feature(g, {
                "plus_code": ed.get("PLUS_CODE_280"),
                "users": _num(ed.get("USERS")),
                "deliveries": _num(ed.get("DELS")),
                "rank": _num(ed.get("RANK")),
                "del_contribution_pct": _num(ed.get("DEL_CONTRIBUTION_PERC")),
                "bucket": ed.get("DEL_BUCKET"),
                "insta_hub": (ed.get("INSTA_HUB") or "").replace("\n", "") or None,
                "live": ed.get("LIVE"),
                "folder": pm.folder,
            }))
        elif c.category == "competitor_location":
            competitor_features.append(_feature(g, {
                "name": pm.name, "city": ed.get("City"), "plus_code": ed.get("Plus Code"), "folder": pm.folder,
            }))
        elif c.category == "route_line":
            route_features.append(_feature(g, {
                "name": pm.name or "(unnamed line)", "folder": pm.folder,
                "points": pm.coordinate_count, "source_line": pm.source_line,
            }))

    boundary_features = [
        {"type": "Feature", "id": c["cluster_id"], "geometry": c["boundary"],
         "properties": {"cluster_id": c["cluster_id"], "name": c["name"], "display_name": c["display_name"],
                        "hub_count": c["hub_count"], "color": c["color"]}}
        for c in cluster_dicts if c.get("boundary")
    ]
    cluster_color = {c.cluster_id: c.color for c in clusters}
    service_area_features = [
        _feature(h.service_area, {
            "hub_id": h.hub_id, "name": h.name, "display_name": h.display_name, "cluster_id": h.cluster_id,
            "status": h.status, "color": cluster_color.get(h.cluster_id, "#64748b"),
            "area_km2": h.service_area_km2,
        }, h.hub_id)
        for h in hubs if h.service_area is not None
    ]

    # 5. Analysis -------------------------------------------------------------------
    folder_info = []
    for f in parsed.folders:
        members = [(pm, c) for pm, c in classified if pm.folder_path[: len(f.path)] == f.path]
        fields: Counter[str] = Counter()
        for pm, _ in members:
            fields.update(pm.extended_data.keys())
        folder_info.append({
            "name": f.name,
            "path": " / ".join(f.path),
            "source_line": f.source_line,
            "placemark_count": f.placemark_count,
            "geometry_counts": dict(Counter(pm.geometry_type or "none" for pm, _ in members)),
            "categories": dict(Counter(c.category for _, c in members)),
            "attribute_fields": sorted(fields.keys()),
        })

    cat_counts = Counter(c.category for _, c in classified)
    cat_details = {}
    for pm, c in classified:
        d = cat_details.setdefault(c.category, {
            "category": c.category, "label": c.label, "count": 0, "inferred": c.inferred,
            "pii": c.pii, "rule": c.reason,
        })
        d["count"] += 1

    coordinate_issues = [
        {"placemark_index": pm.index, "source_line": pm.source_line, "name": pm.name, "folder": pm.folder,
         "category": c.category, "issues": pm.issues}
        for pm, c in classified if pm.issues
    ]
    unclassified = [
        {"placemark_index": pm.index, "source_line": pm.source_line, "name": pm.name, "folder": pm.folder,
         "geometry": pm.geometry_type}
        for pm, c in classified if c.category == "unclassified"
    ]
    screening = [pm for pm, c in classified if c.category == "screening_record"]
    mojibake = [
        {"source_line": pm.source_line, "field": k, "category": c.category}
        for pm, c in classified
        for k, v in [("<name>", pm.name or ""), *pm.extended_data.items()]
        if MOJIBAKE_RE.search(v)
    ]

    plus_codes = defaultdict(set)
    for f in demand_features:
        plus_codes[f["properties"]["plus_code"]].add(f["properties"]["folder"])
    shared_codes = sum(1 for v in plus_codes.values() if len(v) > 1)

    status_counts = Counter(h.status or "unknown" for h in hubs)
    analysis: dict[str, Any] = {
        "source": {
            "file_name": source_display_name or source_path.name,
            "size_bytes": len(data),
            "sha256": sha,
            "line_count": data.count(b"\n") + 1,
            "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "document_name": parsed.document_name,
            "style_count": len(parsed.style_ids),
        },
        "repair": repair.summary(),
        "folders": folder_info,
        "placemark_count": len(parsed.placemarks),
        "geometry_counts": dict(Counter(pm.geometry_type or "none" for pm in parsed.placemarks)),
        "category_counts": dict(cat_counts),
        "categories": list(cat_details.values()),
        "hubs": {
            "total": len(hubs),
            "valid_location": sum(1 for h in hubs if h.valid),
            "invalid_location": sum(1 for h in hubs if not h.valid),
            "active": sum(1 for h in hubs if h.is_active),
            "inactive": sum(1 for h in hubs if h.is_active is False),
            "status_unknown": sum(1 for h in hubs if h.is_active is None),
            "status_counts": dict(status_counts),
            "location_methods": dict(Counter(h.location_method or "none" for h in hubs)),
            "with_service_area": sum(1 for h in hubs if h.service_area is not None),
            "unique_hub_ids": len({h.hub_id for h in hubs if h.hub_id}),
            "region_counts": dict(Counter(h.region or "unknown" for h in hubs)),
            "hub_type_available": any(h.hub_type for h in hubs),
        },
        "clusters": {
            "total": len(clusters),
            "with_hubs": sum(1 for c in clusters if c.hub_count),
            "with_boundary": sum(1 for c in clusters if c.boundary is not None),
            "boundary_polygons_in_source": len(boundaries),
            "method": cluster_notes.get("method"),
            "clusters_without_boundary": cluster_notes.get("clusters_without_boundary"),
            "boundaries_without_hubs": cluster_notes.get("unmatched_boundaries"),
            "raw_cluster_values": len({h.cluster_raw for h in hubs if h.cluster_raw}),
            "hub_counts": {c.name: c.hub_count for c in clusters},
        },
        "regions": [{k: v for k, v in r.items() if k != "geometry"} for r in regions],
        "layers": {
            "demand_points": len(demand_features),
            "demand_points_shared_plus_codes": shared_codes,
            "competitor_locations": len(competitor_features),
            "source_route_lines": len(route_features),
            "screening_records_excluded_pii": len(screening),
        },
        "quality": quality,
        "coordinate_issues": coordinate_issues,
        "unclassified": unclassified,
        "encoding_anomalies": mojibake,
        "assumptions": _assumptions(cfg, hubs, clusters, regions),
    }

    # 6. Write outputs -----------------------------------------------------------------
    _write_json(output_dir / "hubs.json", {"count": len(hub_dicts), "hubs": hub_dicts})
    _write_json(output_dir / "hubs.geojson", export_service.hubs_geojson(hub_dicts), indent=None)
    _write_json(output_dir / "clusters.json", {
        "count": len(cluster_dicts),
        "method": cluster_notes.get("method"),
        "clusters": cluster_dicts,
    })
    layers_dir = output_dir / "layers"
    _write_json(layers_dir / "cluster_boundaries.geojson", _fc(boundary_features), indent=None)
    _write_json(layers_dir / "hub_service_areas.geojson", _fc(service_area_features), indent=None)
    _write_json(layers_dir / "regions.geojson", _fc([
        {"type": "Feature", "id": r["id"], "geometry": r["geometry"],
         "properties": {k: v for k, v in r.items() if k != "geometry"}} for r in regions
    ]), indent=None)
    _write_json(layers_dir / "demand_points.geojson", _fc(demand_features), indent=None)
    _write_json(layers_dir / "competitor_locations.geojson", _fc(competitor_features), indent=None)
    _write_json(layers_dir / "source_route_lines.geojson", _fc(route_features), indent=None)
    _write_json(output_dir / "analysis.json", analysis)

    service_areas = {f["id"]: f["geometry"] for f in _fc(service_area_features)["features"]}
    (output_dir / "cleaned_hubs.kml").write_bytes(
        export_service.build_company_demo_kml(hub_dicts, cluster_dicts, regions=regions,
                                              service_areas=service_areas, title="Cleaned hubs and clusters")
    )
    (output_dir / "kml_analysis_report.md").write_text(render_markdown_report(analysis), encoding="utf-8")
    log.info("Processed %s: %d placemarks, %d hubs, %d clusters",
             source_path.name, len(parsed.placemarks), len(hubs), len(clusters))
    return analysis


def _assumptions(cfg, hubs, clusters, regions) -> list[dict[str, str]]:
    out = [
        {"topic": "Hub identification",
         "text": "A placemark is treated as a hub only if it carries a 'Hub ID' attribute (or both 'Hub' and "
                 "'Cluster'). Demand points, competitor points, screening records, cluster/region polygons and "
                 "drawn lines are classified separately and are never treated as hubs.",
         "inferred": "no"},
    ]
    methods = Counter(h.location_method for h in hubs)
    if any(m and m.startswith("service_area") for m in methods):
        out.append({
            "topic": "Hub coordinates",
            "text": "Hubs are stored in the KML as service-area polygons without an explicit hub point. The hub "
                    "location used for search and routing is the polygon centroid ("
                    f"{methods.get('service_area_centroid', 0)} hubs) or, where the centroid falls outside a "
                    "concave polygon, an interior point guaranteed to lie inside it "
                    f"({methods.get('service_area_interior_point', 0)} hubs). Original polygon coordinates are "
                    "preserved unchanged.",
            "inferred": "yes"})
    merged = {c.name: c.name_variants for c in clusters if len(c.name_variants) > 1}
    if merged:
        out.append({
            "topic": "Cluster names",
            "text": "Cluster attribute values are matched case- and punctuation-insensitively, and a trailing "
                    "'Cluster' is ignored when matching boundary polygons, so variants such as "
                    + ", ".join(f"{k} = {v}" for k, v in list(merged.items())[:4]) + " are one cluster.",
            "inferred": "yes"})
    out.append({
        "topic": "Operational status",
        "text": "The 'Hub status' attribute is used as given. Only 'Live' counts as active; 'Not Live' and "
                "'To be made live' are inactive and can be excluded from nearest-hub searches.",
        "inferred": "no"})
    if regions:
        out.append({"topic": "Regions", "text": (cfg.get("region") or {}).get("mapping_note", ""),
                    "inferred": "yes"})
    for rule in cfg.get("other_categories", []):
        if rule.get("inferred") and rule.get("note"):
            out.append({"topic": rule.get("label", rule["category"]), "text": rule["note"], "inferred": "yes"})
    out.append({"topic": "Hub type",
                "text": "The KML has no explicit hub type/category field, so hub_type is stored as null. "
                        "'Cluster Mapping' (competitive / non-competitive) and the PMF demand level are exposed "
                        "as separate attributes.",
                "inferred": "no"})
    return out
