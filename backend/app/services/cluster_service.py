"""Cluster construction, verification and data-quality analysis.

Cluster membership precedence for each hub:

1. the hub's explicit cluster attribute (normalised so ``hitech_city`` and
   ``Hitech_City`` are the same cluster),
2. otherwise the cluster boundary polygon that contains the hub (labelled
   *inferred*),
3. otherwise DBSCAN over hub locations - only when the dataset has neither
   cluster attributes nor cluster boundaries at all (labelled *inferred*).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from .geo_utils import area_km2, haversine_km, to_local_km
from .hub_classifier import HubRecord
from .kml_parser import ParsedPlacemark

# Tailwind 600/700-ish tones: readable on light basemaps, distinct as fills at ~25% opacity.
CLUSTER_PALETTE = [
    "#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#db2777",
    "#65a30d", "#b45309", "#4f46e5", "#0d9488", "#e11d48", "#7c3aed", "#ca8a04",
    "#059669", "#c026d3", "#0284c7", "#be123c", "#1d4ed8", "#15803d", "#7e22ce",
    "#c2410c", "#0e7490", "#be185d", "#4d7c0f", "#a16207", "#6d28d9", "#0369a1",
]
UNASSIGNED_COLOR = "#64748b"


def cluster_key(name: str | None, strip_pattern: str = r"(?i)[ _-]?cluster$") -> str:
    """Normalised matching key: case/punctuation-insensitive, without a trailing 'cluster'."""
    if not name:
        return ""
    base = re.sub(strip_pattern, "", name.strip())
    return re.sub(r"[^a-z0-9]", "", base.lower())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


@dataclass
class ClusterBoundary:
    name: str
    key: str
    geometry: BaseGeometry
    source_line: int | None
    placemark_index: int


@dataclass
class ClusterRecord:
    cluster_id: str
    name: str
    display_name: str
    key: str
    source: str
    inferred: bool
    name_variants: list[str] = field(default_factory=list)
    boundary: BaseGeometry | None = None
    boundary_name: str | None = None
    hub_ids: list[str] = field(default_factory=list)
    hub_count: int = 0
    active_hub_count: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    region_counts: dict[str, int] = field(default_factory=dict)
    cluster_mapping_counts: dict[str, int] = field(default_factory=dict)
    center_lat: float | None = None
    center_lng: float | None = None
    center_method: str | None = None
    boundary_area_km2: float | None = None
    service_area_union_km2: float | None = None
    bbox: list[float] | None = None
    max_hub_distance_km: float | None = None
    mean_nearest_neighbor_km: float | None = None
    hubs_outside_boundary: list[str] = field(default_factory=list)
    color: str = UNASSIGNED_COLOR


def extract_boundaries(placemarks: list[tuple[ParsedPlacemark, Any]], strip_pattern: str) -> list[ClusterBoundary]:
    out = []
    for pm, _cls in placemarks:
        geom = pm.analysis_geometry()
        if geom is None:
            continue
        name = re.sub(strip_pattern, "", (pm.name or "").strip()) or (pm.name or "")
        out.append(
            ClusterBoundary(
                name=name,
                key=cluster_key(pm.name, strip_pattern),
                geometry=geom,
                source_line=pm.source_line,
                placemark_index=pm.index,
            )
        )
    return out


def dbscan_haversine(points: list[tuple[float, float]], eps_km: float, min_samples: int) -> list[int]:
    """DBSCAN with great-circle distance. Returns a label per point (-1 = noise).

    A uniform lat/lng grid with cell size >= eps keeps neighbour queries local.
    """
    n = len(points)
    if n == 0:
        return []
    cell_lat = eps_km / 111.0
    max_lat = max(abs(p[0]) for p in points)
    cell_lng = eps_km / (111.0 * max(math.cos(math.radians(min(max_lat, 89.0))), 1e-6))
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (lat, lng) in enumerate(points):
        grid[(int(lat // cell_lat), int(lng // cell_lng))].append(i)

    def neighbours(i: int) -> list[int]:
        lat, lng = points[i]
        gi, gj = int(lat // cell_lat), int(lng // cell_lng)
        res = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for j in grid.get((gi + di, gj + dj), ()):
                    if haversine_km(lat, lng, points[j][0], points[j][1]) <= eps_km:
                        res.append(j)
        return res

    labels = [None] * n  # type: list[int | None]
    cid = -1
    for i in range(n):
        if labels[i] is not None:
            continue
        nb = neighbours(i)
        if len(nb) < min_samples:
            labels[i] = -1
            continue
        cid += 1
        labels[i] = cid
        queue = [j for j in nb if j != i]
        while queue:
            j = queue.pop()
            if labels[j] == -1:
                labels[j] = cid  # border point
            if labels[j] is not None:
                continue
            labels[j] = cid
            nb_j = neighbours(j)
            if len(nb_j) >= min_samples:
                queue.extend(nb_j)
    return [lbl if lbl is not None else -1 for lbl in labels]


def _assign_colors(clusters: list[ClusterRecord]) -> None:
    """Greedy colouring so clusters whose boundaries/hubs lie close together get different colours."""
    def geom_of(c: ClusterRecord) -> BaseGeometry | None:
        if c.boundary is not None:
            return c.boundary
        if c.center_lat is not None:
            return Point(c.center_lng, c.center_lat).buffer(0.01)
        return None

    ordered = sorted(clusters, key=lambda c: -c.hub_count)
    used: Counter[str] = Counter()
    for c in ordered:
        g = geom_of(c)
        taken = set()
        for other in clusters:
            if other is c or other.color == UNASSIGNED_COLOR:
                continue
            og = geom_of(other)
            if g is not None and og is not None and g.distance(og) < 0.03:  # ~3 km
                taken.add(other.color)
        choices = [p for p in CLUSTER_PALETTE if p not in taken] or CLUSTER_PALETTE
        c.color = min(choices, key=lambda p: (used[p], CLUSTER_PALETTE.index(p)))
        used[c.color] += 1


def build_clusters(
    hubs: list[HubRecord],
    boundaries: list[ClusterBoundary],
    cfg: dict[str, Any],
) -> tuple[list[ClusterRecord], dict[str, Any]]:
    """Assign hubs to clusters (mutating hubs) and compute cluster statistics."""
    notes: dict[str, Any] = {"method": None, "unmatched_boundaries": [], "clusters_without_boundary": []}
    boundary_by_key: dict[str, ClusterBoundary] = {}
    for b in boundaries:
        if b.key in boundary_by_key:
            notes.setdefault("duplicate_boundaries", []).append(b.name)
            # union duplicates so no polygon is lost
            boundary_by_key[b.key].geometry = boundary_by_key[b.key].geometry.union(b.geometry)
        else:
            boundary_by_key[b.key] = b

    has_attr = any(h.cluster_raw for h in hubs)
    by_key: dict[str, list[HubRecord]] = defaultdict(list)
    variants: dict[str, Counter[str]] = defaultdict(Counter)

    if has_attr or boundaries:
        notes["method"] = "explicit cluster attribute" + (" + cluster boundary polygons" if boundaries else "")
        tree_items = list(boundary_by_key.values())
        tree = STRtree([b.geometry for b in tree_items]) if tree_items else None
        for h in hubs:
            if h.cluster_raw:
                k = cluster_key(h.cluster_raw)
                h.cluster_source = "attribute"
                by_key[k].append(h)
                variants[k][h.cluster_raw] += 1
            elif tree is not None and h.latitude is not None:
                p = Point(h.longitude, h.latitude)
                hits = [tree_items[i] for i in tree.query(p, predicate="within")]
                if len(hits) >= 1:
                    k = hits[0].key
                    h.cluster_source = "spatial_boundary (inferred)"
                    by_key[k].append(h)
                    h.issues.append("cluster attribute missing; cluster inferred from containing boundary polygon")
                else:
                    h.cluster_source = None
    else:
        fb = cfg.get("clustering_fallback", {})
        eps, ms = float(fb.get("eps_km", 2.0)), int(fb.get("min_samples", 3))
        notes["method"] = f"DBSCAN (haversine, eps={eps} km, min_samples={ms}) - inferred"
        located = [h for h in hubs if h.latitude is not None]
        labels = dbscan_haversine([(h.latitude, h.longitude) for h in located], eps, ms)
        for h, lbl in zip(located, labels):
            if lbl >= 0:
                k = f"dbscan{lbl + 1}"
                h.cluster_source = "dbscan (inferred)"
                by_key[k].append(h)
                variants[k][f"Cluster {lbl + 1} (DBSCAN)"] += 1

    clusters: list[ClusterRecord] = []
    all_keys = list(dict.fromkeys(list(by_key.keys()) + list(boundary_by_key.keys())))
    for k in all_keys:
        members = by_key.get(k, [])
        b = boundary_by_key.get(k)
        if variants.get(k):
            # canonical spelling = most common; ties broken in favour of Capitalised forms
            name = sorted(variants[k].items(), key=lambda kv: (-kv[1], not kv[0][:1].isupper(), kv[0]))[0][0]
        else:
            name = b.name if b else k
        dbscan = k.startswith("dbscan") and not b
        if dbscan:
            source = "dbscan"
        elif members and b:
            source = "attribute+boundary"
        elif members:
            source = "attribute"
            notes["clusters_without_boundary"].append(name)
        else:
            source = "boundary_only"
            notes["unmatched_boundaries"].append(b.name if b else k)

        c = ClusterRecord(
            cluster_id=slugify(name) if not dbscan else k.replace("dbscan", "dbscan_"),
            name=name,
            display_name=name.replace("_", " "),
            key=k,
            source=source,
            inferred=dbscan,
            name_variants=sorted(set(variants.get(k, {}).keys()) | ({b.name} if b else set())),
            boundary=b.geometry if b else None,
            boundary_name=b.name if b else None,
        )
        for h in members:
            h.cluster_id = c.cluster_id
            h.cluster_name = c.name
        _cluster_stats(c, members)
        clusters.append(c)

    _assign_colors(clusters)
    clusters.sort(key=lambda c: (-c.hub_count, c.name))
    return clusters, notes


def _cluster_stats(c: ClusterRecord, members: list[HubRecord]) -> None:
    located = [h for h in members if h.latitude is not None]
    c.hub_ids = [h.hub_id or f"idx{h.placemark_index}" for h in members]
    c.hub_count = len(members)
    c.active_hub_count = sum(1 for h in members if h.is_active)
    c.status_counts = dict(Counter(h.status or "unknown" for h in members))
    c.region_counts = dict(Counter(h.region or "unknown" for h in members))
    c.cluster_mapping_counts = dict(Counter(h.cluster_mapping or "unknown" for h in members))

    if c.boundary is not None:
        cen = c.boundary.centroid
        c.center_lat, c.center_lng, c.center_method = round(cen.y, 7), round(cen.x, 7), "boundary_centroid"
        c.boundary_area_km2 = area_km2(c.boundary)
    elif located:
        c.center_lat = round(sum(h.latitude for h in located) / len(located), 7)
        c.center_lng = round(sum(h.longitude for h in located) / len(located), 7)
        c.center_method = "mean_of_hub_locations"

    pts = [(h.latitude, h.longitude) for h in located]
    if c.boundary is not None:
        minx, miny, maxx, maxy = c.boundary.bounds
        pts += [(miny, minx), (maxy, maxx)]
    if pts:
        c.bbox = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]

    if located and c.center_lat is not None:
        c.max_hub_distance_km = round(
            max(haversine_km(c.center_lat, c.center_lng, h.latitude, h.longitude) for h in located), 3
        )
    if len(located) > 1:
        nn = []
        for h in located:
            nn.append(min(haversine_km(h.latitude, h.longitude, o.latitude, o.longitude) for o in located if o is not h))
        c.mean_nearest_neighbor_km = round(sum(nn) / len(nn), 3)

    areas = [h.service_area for h in members if h.service_area is not None]
    if areas:
        from shapely.ops import unary_union

        c.service_area_union_km2 = area_km2(unary_union(areas))

    if c.boundary is not None:
        for h in located:
            if not c.boundary.covers(Point(h.longitude, h.latitude)):
                c.hubs_outside_boundary.append(h.hub_id or h.name or "?")


def quality_checks(
    hubs: list[HubRecord], clusters: list[ClusterRecord], cfg: dict[str, Any]
) -> dict[str, Any]:
    q = cfg.get("quality", {})
    dup_m = float(q.get("duplicate_location_threshold_m", 10))
    iso_km = float(q.get("isolation_threshold_km", 3.0))

    id_counts = Counter(h.hub_id for h in hubs if h.hub_id)
    name_counts = Counter((h.name or "").lower() for h in hubs if h.name)
    duplicate_ids = {k: v for k, v in id_counts.items() if v > 1}
    duplicate_names = {k: v for k, v in name_counts.items() if v > 1}

    located = [h for h in hubs if h.latitude is not None]
    duplicate_locations = []
    for i, a in enumerate(located):
        for b in located[i + 1 :]:
            d = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * 1000
            if d <= dup_m:
                duplicate_locations.append({"hub_a": a.hub_id, "hub_b": b.hub_id, "distance_m": round(d, 2)})

    isolated = []
    by_cluster: dict[str | None, list[HubRecord]] = defaultdict(list)
    for h in located:
        by_cluster[h.cluster_id].append(h)
    for h in located:
        peers = [o for o in by_cluster[h.cluster_id] if o is not h]
        nearest_any = min(
            (haversine_km(h.latitude, h.longitude, o.latitude, o.longitude) for o in located if o is not h),
            default=None,
        )
        if not peers:
            isolated.append({
                "hub_id": h.hub_id, "name": h.name, "cluster": h.cluster_name,
                "reason": "only hub in its cluster",
                "nearest_same_cluster_km": None,
                "nearest_any_km": round(nearest_any, 3) if nearest_any is not None else None,
            })
            continue
        nearest_same = min(haversine_km(h.latitude, h.longitude, o.latitude, o.longitude) for o in peers)
        if nearest_same > iso_km:
            isolated.append({
                "hub_id": h.hub_id, "name": h.name, "cluster": h.cluster_name,
                "reason": f"nearest hub in same cluster is {nearest_same:.2f} km away (> {iso_km} km)",
                "nearest_same_cluster_km": round(nearest_same, 3),
                "nearest_any_km": round(nearest_any, 3) if nearest_any is not None else None,
            })

    # Overlapping service areas (pairs whose overlap exceeds 1% of the smaller polygon).
    overlaps = []
    with_area = [h for h in hubs if h.service_area is not None]
    if with_area:
        tree = STRtree([h.service_area for h in with_area])
        for i, h in enumerate(with_area):
            for j in tree.query(h.service_area, predicate="intersects"):
                if j <= i:
                    continue
                o = with_area[j]
                inter = h.service_area.intersection(o.service_area)
                if inter.is_empty:
                    continue
                smaller = min(h.service_area.area, o.service_area.area)
                frac = inter.area / smaller if smaller else 0
                if frac > 0.01:
                    overlaps.append({
                        "hub_a": h.hub_id, "name_a": h.name, "hub_b": o.hub_id, "name_b": o.name,
                        "overlap_km2": round(to_local_km(inter, h.latitude, h.longitude).area, 4),
                        "overlap_pct_of_smaller": round(frac * 100, 1),
                    })

    mismatches = []
    boundary_clusters = [c for c in clusters if c.boundary is not None]
    for c in clusters:
        for hid in c.hubs_outside_boundary:
            h = next((x for x in hubs if (x.hub_id or x.name) == hid), None)
            if h is None or h.latitude is None:
                continue
            p = Point(h.longitude, h.latitude)
            inside = [bc.name for bc in boundary_clusters if bc.boundary.covers(p)]
            dist_km = round(to_local_km(c.boundary, h.latitude, h.longitude).distance(
                to_local_km(p, h.latitude, h.longitude)), 3)
            mismatches.append({
                "hub_id": h.hub_id, "name": h.name, "assigned_cluster": c.name,
                "location_inside_cluster_boundaries": inside,
                "distance_outside_assigned_boundary_km": dist_km,
            })

    return {
        "duplicate_hub_ids": duplicate_ids,
        "duplicate_hub_names": duplicate_names,
        "duplicate_locations": duplicate_locations,
        "duplicate_location_threshold_m": dup_m,
        "missing_hub_ids": [h.name for h in hubs if not h.hub_id],
        "missing_hub_names": [h.hub_id for h in hubs if not h.name],
        "invalid_locations": [{"hub_id": h.hub_id, "name": h.name, "issues": h.issues} for h in hubs if not h.valid],
        "unassigned_hubs": [{"hub_id": h.hub_id, "name": h.name} for h in hubs if not h.cluster_id],
        "isolated_hubs": isolated,
        "isolation_threshold_km": iso_km,
        "cluster_boundary_mismatches": mismatches,
        "overlapping_service_areas": overlaps,
        "hubs_with_issues": [
            {"hub_id": h.hub_id, "name": h.name, "source_line": h.source_line, "issues": h.issues}
            for h in hubs if h.issues
        ],
        "inactive_hubs": [
            {"hub_id": h.hub_id, "name": h.name, "status": h.status, "cluster": h.cluster_name}
            for h in hubs if h.is_active is False
        ],
        "cluster_name_variants": {c.name: c.name_variants for c in clusters if len(c.name_variants) > 1},
    }
