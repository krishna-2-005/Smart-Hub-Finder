"""Google Earth compatible KML, CSV and GeoJSON exports.

All builders work on the JSON-serialisable dictionaries held by the data store
(the same shapes as ``hubs.json`` / ``clusters.json`` / search results), so the
exports always reflect exactly what the API serves.

KML conventions used:
* colours are ``aabbggrr`` hex
* every route is a ``LineString`` with ``tessellate=1`` and ``clampToGround``
  containing the full decoded road geometry (never just the two end points)
"""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone
from typing import Any, Iterable

from lxml import etree

KML_NS = "http://www.opengis.net/kml/2.2"
ICON_CIRCLE = "https://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"
ICON_USER = "https://maps.google.com/mapfiles/kml/shapes/man.png"
ICON_NEAREST = "https://maps.google.com/mapfiles/kml/paddle/grn-stars.png"
ICON_ALT = "https://maps.google.com/mapfiles/kml/paddle/blu-circle.png"
ICON_CENTER = "https://maps.google.com/mapfiles/kml/shapes/target.png"
ICON_UNREACHABLE = "https://maps.google.com/mapfiles/kml/shapes/forbidden.png"

HUB_FIELDS = [
    ("Hub ID", "hub_id"), ("Hub name", "name"), ("Hub code", "hub_code"), ("Cluster", "cluster_name"),
    ("Region / Line", "region"), ("Status", "status"), ("Cluster mapping", "cluster_mapping"),
    ("Priority", "priority"), ("Demand level", "demand_level"), ("Latitude", "latitude"),
    ("Longitude", "longitude"), ("Location method", "location_method"),
    ("Service area (km²)", "service_area_km2"), ("Original KML folder", "original_folder"),
]


def kml_color(hex_rgb: str, alpha: float = 1.0) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = f"{max(0, min(255, round(alpha * 255))):02x}"
    return f"{a}{b}{g}{r}".lower()


def _sub(parent: etree._Element, tag: str, text: Any = None, **attrs: str) -> etree._Element:
    el = etree.SubElement(parent, f"{{{KML_NS}}}{tag}", **attrs)
    if text is not None:
        el.text = str(text)
    return el


class KmlBuilder:
    def __init__(self, name: str, description: str | None = None):
        self.root = etree.Element(f"{{{KML_NS}}}kml", nsmap={None: KML_NS})
        self.doc = _sub(self.root, "Document")
        _sub(self.doc, "name", name)
        _sub(self.doc, "open", 1)
        if description:
            d = _sub(self.doc, "description")
            d.text = etree.CDATA(description)
        self._styles: set[str] = set()

    # -- styles --------------------------------------------------------------
    def icon_style(self, style_id: str, color: str, icon: str = ICON_CIRCLE, scale: float = 0.9,
                   label_scale: float = 0.0, alpha: float = 1.0) -> str:
        if style_id in self._styles:
            return f"#{style_id}"
        for suffix, ls in (("n", label_scale), ("h", max(label_scale, 0.9))):
            s = _sub(self.doc, "Style", id=f"{style_id}-{suffix}")
            ist = _sub(s, "IconStyle")
            _sub(ist, "color", kml_color(color, alpha))
            _sub(ist, "scale", scale if suffix == "n" else scale * 1.25)
            ic = _sub(ist, "Icon")
            _sub(ic, "href", icon)
            lab = _sub(s, "LabelStyle")
            _sub(lab, "scale", ls)
            bs = _sub(s, "BalloonStyle")
            _sub(bs, "text", "$[description]")
        sm = _sub(self.doc, "StyleMap", id=style_id)
        for key, suffix in (("normal", "n"), ("highlight", "h")):
            p = _sub(sm, "Pair")
            _sub(p, "key", key)
            _sub(p, "styleUrl", f"#{style_id}-{suffix}")
        self._styles.add(style_id)
        return f"#{style_id}"

    def poly_style(self, style_id: str, color: str, fill_alpha: float = 0.22, line_width: float = 2.0,
                   line_alpha: float = 0.95) -> str:
        if style_id in self._styles:
            return f"#{style_id}"
        s = _sub(self.doc, "Style", id=style_id)
        ls = _sub(s, "LineStyle")
        _sub(ls, "color", kml_color(color, line_alpha))
        _sub(ls, "width", line_width)
        ps = _sub(s, "PolyStyle")
        _sub(ps, "color", kml_color(color, fill_alpha))
        bs = _sub(s, "BalloonStyle")
        _sub(bs, "text", "$[description]")
        self._styles.add(style_id)
        return f"#{style_id}"

    def line_style(self, style_id: str, color: str, width: float = 6.0, alpha: float = 1.0) -> str:
        if style_id in self._styles:
            return f"#{style_id}"
        s = _sub(self.doc, "Style", id=style_id)
        ls = _sub(s, "LineStyle")
        _sub(ls, "color", kml_color(color, alpha))
        _sub(ls, "width", width)
        bs = _sub(s, "BalloonStyle")
        _sub(bs, "text", "$[description]")
        self._styles.add(style_id)
        return f"#{style_id}"

    # -- structure -------------------------------------------------------------
    def folder(self, name: str, parent: etree._Element | None = None, open_: bool = False,
               visible: bool = True, description: str | None = None) -> etree._Element:
        f = _sub(parent if parent is not None else self.doc, "Folder")
        _sub(f, "name", name)
        _sub(f, "visibility", int(visible))  # schema order: name, visibility, open
        _sub(f, "open", int(open_))
        if description:
            _sub(f, "description").text = etree.CDATA(description)
        return f

    def look_at(self, lat: float, lng: float, range_m: float) -> None:
        la = _sub(self.doc, "LookAt")
        _sub(la, "longitude", f"{lng:.6f}")
        _sub(la, "latitude", f"{lat:.6f}")
        _sub(la, "altitude", 0)
        _sub(la, "heading", 0)
        _sub(la, "tilt", 0)
        _sub(la, "range", f"{range_m:.0f}")
        _sub(la, "altitudeMode", "relativeToGround")

    def placemark(self, parent: etree._Element, name: str | None, style_url: str | None,
                  description: str | None = None, extended: dict[str, Any] | None = None,
                  visible: bool = True, snippet: str | None = None) -> etree._Element:
        pm = _sub(parent, "Placemark")
        _sub(pm, "name", name or "")
        _sub(pm, "visibility", int(visible))
        if snippet is not None:
            _sub(pm, "Snippet", snippet, maxLines="1")
        if description:
            _sub(pm, "description").text = etree.CDATA(description)
        if style_url:
            _sub(pm, "styleUrl", style_url)
        if extended:
            ed = _sub(pm, "ExtendedData")
            for k, v in extended.items():
                if v is None or v == "":
                    continue
                d = _sub(ed, "Data", name=str(k))
                _sub(d, "value", v)
        return pm

    @staticmethod
    def point(pm: etree._Element, lat: float, lng: float) -> None:
        p = _sub(pm, "Point")
        _sub(p, "coordinates", f"{lng:.7f},{lat:.7f},0")

    @staticmethod
    def linestring(pm: etree._Element, latlngs: Iterable[Iterable[float]]) -> int:
        ls = _sub(pm, "LineString")
        _sub(ls, "tessellate", 1)
        _sub(ls, "altitudeMode", "clampToGround")
        pts = [f"{lng:.6f},{lat:.6f},0" for lat, lng in latlngs]
        _sub(ls, "coordinates", "\n".join(pts))
        return len(pts)

    @staticmethod
    def geojson_geometry(pm: etree._Element, geom: dict[str, Any]) -> None:
        """Write a GeoJSON Polygon/MultiPolygon/Point/LineString as KML geometry."""
        def ring(coords: list[list[float]]) -> str:
            return "\n".join(f"{c[0]:.7f},{c[1]:.7f},0" for c in coords)

        def polygon(parent: etree._Element, rings: list[list[list[float]]]) -> None:
            poly = _sub(parent, "Polygon")
            _sub(poly, "tessellate", 1)
            ob = _sub(poly, "outerBoundaryIs")
            _sub(_sub(ob, "LinearRing"), "coordinates", ring(rings[0]))
            for hole in rings[1:]:
                ib = _sub(poly, "innerBoundaryIs")
                _sub(_sub(ib, "LinearRing"), "coordinates", ring(hole))

        t = geom.get("type")
        if t == "Polygon":
            polygon(pm, geom["coordinates"])
        elif t == "MultiPolygon":
            mg = _sub(pm, "MultiGeometry")
            for rings in geom["coordinates"]:
                polygon(mg, rings)
        elif t == "Point":
            KmlBuilder.point(pm, geom["coordinates"][1], geom["coordinates"][0])
        elif t == "LineString":
            KmlBuilder.linestring(pm, [(c[1], c[0]) for c in geom["coordinates"]])
        elif t == "GeometryCollection":
            mg = _sub(pm, "MultiGeometry")
            for g in geom.get("geometries", []):
                if g.get("type") == "Polygon":
                    polygon(mg, g["coordinates"])

    # KML 2.2 fixes the order of a Document's children: feature header, view, styles, then features.
    _DOC_ORDER = {"name": 0, "visibility": 1, "open": 2, "Snippet": 3, "description": 4,
                  "LookAt": 5, "Camera": 5, "Style": 6, "StyleMap": 6}

    def to_bytes(self) -> bytes:
        children = list(self.doc)
        rank = lambda el: self._DOC_ORDER.get(etree.QName(el).localname, 9)  # noqa: E731
        ordered = sorted(children, key=rank)  # stable: keeps relative order within each group
        for el in children:
            self.doc.remove(el)
        self.doc.extend(ordered)
        return etree.tostring(self.root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


# ---------------------------------------------------------------------------
# Description helpers
# ---------------------------------------------------------------------------

def _table(rows: Iterable[tuple[str, Any]], title: str | None = None, accent: str = "#1e3a8a") -> str:
    body = "".join(
        f"<tr><td style='padding:2px 8px 2px 0;color:#475569;white-space:nowrap'><b>{html.escape(str(k))}</b></td>"
        f"<td style='padding:2px 0'>{html.escape(str(v))}</td></tr>"
        for k, v in rows
        if v not in (None, "")
    )
    head = f"<h3 style='margin:0 0 6px;color:{accent}'>{html.escape(title)}</h3>" if title else ""
    return f"<div style='font-family:Arial,sans-serif;font-size:12px;min-width:240px'>{head}<table>{body}</table></div>"


def hub_description(h: dict[str, Any], extra: list[tuple[str, Any]] | None = None) -> str:
    rows = [(label, h.get(key)) for label, key in HUB_FIELDS]
    if h.get("location_method", "").startswith("service_area"):
        rows.append(("Note", "Hub point inferred from its service-area polygon (no explicit hub point in source KML)"))
    if extra:
        rows = extra + rows
    return _table(rows, h.get("display_name") or h.get("name"))


def hub_extended(h: dict[str, Any]) -> dict[str, Any]:
    return {label: h.get(key) for label, key in HUB_FIELDS}


def _range_for_bbox(bbox: list[float] | None, minimum: float = 1500) -> float:
    if not bbox:
        return 30000
    from .geo_utils import haversine_km

    diag = haversine_km(bbox[0], bbox[1], bbox[2], bbox[3]) * 1000
    return max(minimum, diag * 1.6)


def _bbox_of_points(points: list[tuple[float, float]]) -> list[float] | None:
    if not points:
        return None
    return [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _add_clusters_with_hubs(
    kb: KmlBuilder,
    parent: etree._Element,
    hubs: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    include_boundaries: bool = True,
    include_service_areas: bool = True,
    service_areas: dict[str, dict[str, Any]] | None = None,
    open_folders: bool = False,
) -> None:
    by_cluster: dict[str | None, list[dict[str, Any]]] = {}
    for h in hubs:
        by_cluster.setdefault(h.get("cluster_id"), []).append(h)

    for c in clusters:
        members = sorted(by_cluster.get(c["cluster_id"], []), key=lambda h: h.get("name") or "")
        cf = kb.folder(f"{c['display_name']} ({len(members)} hubs)", parent, open_=open_folders,
                       description=cluster_description(c))
        if include_boundaries and c.get("boundary"):
            style = kb.poly_style(f"cluster-{c['cluster_id']}", c["color"], fill_alpha=0.18, line_width=2.5)
            pm = kb.placemark(cf, f"{c['display_name']} boundary", style, cluster_description(c),
                              {"Cluster ID": c["cluster_id"], "Hub count": c["hub_count"]})
            kb.geojson_geometry(pm, c["boundary"])
        if c.get("center_lat") is not None:
            style = kb.icon_style(f"center-{c['cluster_id']}", c["color"], ICON_CENTER, scale=1.1, label_scale=0.9)
            pm = kb.placemark(cf, f"{c['display_name']} ({c['hub_count']})", style, cluster_description(c),
                              {"Cluster ID": c["cluster_id"], "Hub count": c["hub_count"],
                               "Center method": c.get("center_method")})
            kb.point(pm, c["center_lat"], c["center_lng"])
        hf = kb.folder("Hubs", cf)
        hub_style = kb.icon_style(f"hub-{c['cluster_id']}", c["color"], ICON_CIRCLE, scale=0.85, label_scale=0.0)
        for h in members:
            if h.get("latitude") is None:
                continue
            pm = kb.placemark(hf, h.get("display_name") or h.get("name"), hub_style, hub_description(h),
                              hub_extended(h), snippet=f"{h.get('hub_id')} · {h.get('status') or 'status unknown'}")
            kb.point(pm, h["latitude"], h["longitude"])
        if include_service_areas and service_areas:
            sf = kb.folder("Hub service areas", cf, visible=False)
            sa_style = kb.poly_style(f"sa-{c['cluster_id']}", c["color"], fill_alpha=0.10, line_width=1.0,
                                     line_alpha=0.7)
            for h in members:
                geom = service_areas.get(h.get("hub_id"))
                if not geom:
                    continue
                pm = kb.placemark(sf, f"{h.get('display_name')} service area", sa_style, hub_description(h),
                                  visible=False)
                kb.geojson_geometry(pm, geom)

    unassigned = by_cluster.get(None, [])
    if unassigned:
        uf = kb.folder(f"Unassigned hubs ({len(unassigned)})", parent)
        st = kb.icon_style("hub-unassigned", "#64748b")
        for h in unassigned:
            if h.get("latitude") is None:
                continue
            pm = kb.placemark(uf, h.get("display_name") or h.get("name"), st, hub_description(h), hub_extended(h))
            kb.point(pm, h["latitude"], h["longitude"])


def cluster_description(c: dict[str, Any]) -> str:
    rows = [
        ("Cluster ID", c.get("cluster_id")),
        ("Hubs", c.get("hub_count")),
        ("Live hubs", c.get("active_hub_count")),
        ("Center", f"{c.get('center_lat')}, {c.get('center_lng')}" if c.get("center_lat") is not None else None),
        ("Center method", c.get("center_method")),
        ("Boundary area (km²)", c.get("boundary_area_km2")),
        ("Service-area coverage (km²)", c.get("service_area_union_km2")),
        ("Max hub distance from center (km, straight-line)", c.get("max_hub_distance_km")),
        ("Source", c.get("source")),
    ]
    return _table(rows, c.get("display_name"), accent=c.get("color", "#1e3a8a"))


def build_hubs_kml(hubs, clusters, service_areas=None, title="All Hubs") -> bytes:
    kb = KmlBuilder(title, f"Smart Hub Finder export · {len(hubs)} hubs in {len(clusters)} clusters · "
                           f"generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}")
    pts = [(h["latitude"], h["longitude"]) for h in hubs if h.get("latitude") is not None]
    bb = _bbox_of_points(pts)
    if bb:
        kb.look_at((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, _range_for_bbox(bb))
    root = kb.folder("Hubs by cluster", open_=True)
    _add_clusters_with_hubs(kb, root, hubs, clusters, include_boundaries=False,
                            include_service_areas=service_areas is not None, service_areas=service_areas)
    return kb.to_bytes()


def build_clusters_kml(hubs, clusters, title="All Clusters") -> bytes:
    kb = KmlBuilder(title, f"{len(clusters)} clusters with boundaries, centers and hubs")
    bb = _bbox_of_points([(c["center_lat"], c["center_lng"]) for c in clusters if c.get("center_lat")])
    if bb:
        kb.look_at((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, _range_for_bbox(bb))
    root = kb.folder("Clusters", open_=True)
    _add_clusters_with_hubs(kb, root, hubs, clusters, include_boundaries=True, include_service_areas=False)
    return kb.to_bytes()


def build_selected_cluster_kml(cluster, hubs, service_areas=None) -> bytes:
    kb = KmlBuilder(f"Cluster - {cluster['display_name']}", cluster_description(cluster))
    if cluster.get("bbox"):
        b = cluster["bbox"]
        kb.look_at((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, _range_for_bbox(b))
    members = [h for h in hubs if h.get("cluster_id") == cluster["cluster_id"]]
    _add_clusters_with_hubs(kb, kb.doc, members, [cluster], include_boundaries=True,
                            include_service_areas=service_areas is not None, service_areas=service_areas,
                            open_folders=True)
    return kb.to_bytes()


def _add_search_result(kb: KmlBuilder, parent: etree._Element, result: dict[str, Any],
                       hubs_by_id: dict[str, dict[str, Any]]) -> None:
    q = result["query"]
    nearest = result.get("nearest")
    route = result.get("route")
    rf = kb.folder("Nearest hub search", parent, open_=True)

    user_style = kb.icon_style("user-location", "#2563eb", ICON_USER, scale=1.3, label_scale=1.0)
    pm = kb.placemark(rf, "Search location", user_style, _table([
        ("Latitude", q["latitude"]), ("Longitude", q["longitude"]),
        ("Detected cluster", (result.get("location") or {}).get("cluster_name")),
        ("Cluster detection", (result.get("location") or {}).get("detection")),
        ("Travel mode", q.get("travel_mode")), ("Ranking", q.get("ranking")),
        ("Searched at", result.get("created_at")),
    ], "Search location", "#2563eb"))
    kb.point(pm, q["latitude"], q["longitude"])

    if nearest:
        h = hubs_by_id.get(nearest["hub_id"], nearest)
        style = kb.icon_style("nearest-hub", "#16a34a", ICON_NEAREST, scale=1.4, label_scale=1.0)
        pm = kb.placemark(rf, f"Nearest hub: {nearest.get('display_name') or nearest.get('name')}", style,
                          hub_description(h, [
                              ("Road distance (km)", nearest.get("road_distance_km")),
                              ("Estimated travel time (min)", nearest.get("duration_min")),
                              ("Routing provider", (result.get("provider") or {}).get("label")),
                          ]), hub_extended(h))
        kb.point(pm, nearest["latitude"], nearest["longitude"])

    if route and route.get("geometry"):
        style = kb.line_style("road-route", "#f97316", width=7)
        desc = _table([
            ("From", f"{q['latitude']:.6f}, {q['longitude']:.6f}"),
            ("To", nearest.get("display_name") if nearest else None),
            ("Road distance (km)", round(route["distance_m"] / 1000, 2)),
            ("Estimated travel time (min)", round(route["duration_s"] / 60, 1)),
            ("Travel mode", route.get("travel_mode")),
            ("Routing provider", route.get("provider_label") or route.get("provider")),
            ("Route geometry points", len(route["geometry"])),
            ("Note", "Road-following geometry returned by the routing engine"),
        ], "Road route", "#c2410c")
        pm = kb.placemark(rf, f"Road route ({route['distance_m'] / 1000:.2f} km, {route['duration_s'] / 60:.0f} min)",
                          style, desc)
        kb.linestring(pm, route["geometry"])
        for i, alt in enumerate(route.get("alternatives") or [], start=1):
            st = kb.line_style("road-route-alt", "#64748b", width=4, alpha=0.8)
            pm = kb.placemark(rf, f"Alternative route {i} ({alt['distance_m'] / 1000:.2f} km)", st, _table([
                ("Road distance (km)", round(alt["distance_m"] / 1000, 2)),
                ("Estimated travel time (min)", round(alt["duration_s"] / 60, 1)),
            ], f"Alternative route {i}"), visible=False)
            kb.linestring(pm, alt["geometry"])

    ranking = result.get("ranking") or []
    if len(ranking) > 1:
        af = kb.folder(f"Alternative hubs (top {len(ranking)})", rf)
        st = kb.icon_style("alt-hub", "#0284c7", ICON_ALT, scale=1.0, label_scale=0.8)
        for r in ranking[1:]:
            h = hubs_by_id.get(r["hub_id"], r)
            pm = kb.placemark(af, f"#{r['rank']} {r.get('display_name') or r.get('name')}", st, hub_description(h, [
                ("Rank", r["rank"]),
                ("Road distance (km)", r.get("road_distance_km")),
                ("Estimated travel time (min)", r.get("duration_min")),
            ]))
            kb.point(pm, r["latitude"], r["longitude"])

    if result.get("unreachable"):
        uf = kb.folder("Unreachable hubs", rf, visible=False)
        st = kb.icon_style("unreachable-hub", "#dc2626", ICON_UNREACHABLE, scale=0.9)
        for u in result["unreachable"]:
            pm = kb.placemark(uf, u.get("display_name") or u.get("name"), st,
                              _table([("Hub ID", u.get("hub_id")), ("Reason", u.get("reason"))], "Unreachable hub"),
                              visible=False)
            kb.point(pm, u["latitude"], u["longitude"])


def _result_bbox(result: dict[str, Any]) -> list[float] | None:
    pts = [(result["query"]["latitude"], result["query"]["longitude"])]
    route = result.get("route")
    if route and route.get("geometry"):
        pts += [tuple(p) for p in route["geometry"]]
    for r in result.get("ranking") or []:
        pts.append((r["latitude"], r["longitude"]))
    return _bbox_of_points(pts)


def build_route_kml(result: dict[str, Any], hubs_by_id: dict[str, dict[str, Any]]) -> bytes:
    nearest = result.get("nearest") or {}
    kb = KmlBuilder(
        f"Route to {nearest.get('display_name') or 'nearest hub'}",
        f"Search at {result.get('created_at')} · provider {(result.get('provider') or {}).get('label')}",
    )
    bb = _result_bbox(result)
    if bb:
        kb.look_at((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, _range_for_bbox(bb, 1200))
    _add_search_result(kb, kb.doc, result, hubs_by_id)
    return kb.to_bytes()


def build_company_demo_kml(hubs, clusters, regions=None, result=None, service_areas=None,
                           title="Smart Hub Network - Company Demo") -> bytes:
    kb = KmlBuilder(
        title,
        f"{len(hubs)} hubs · {len(clusters)} clusters"
        + (" · includes nearest-hub road route" if result and result.get("route") else ""),
    )
    if result:
        bb = _result_bbox(result)
        if bb:
            kb.look_at((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, _range_for_bbox(bb, 2500))
    else:
        bb = _bbox_of_points([(h["latitude"], h["longitude"]) for h in hubs if h.get("latitude")])
        if bb:
            kb.look_at((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2, _range_for_bbox(bb))
    if result:
        hubs_by_id = {h["hub_id"]: h for h in hubs if h.get("hub_id")}
        _add_search_result(kb, kb.doc, result, hubs_by_id)
    nf = kb.folder("Hub network (by cluster)", open_=True)
    _add_clusters_with_hubs(kb, nf, hubs, clusters, include_boundaries=True,
                            include_service_areas=service_areas is not None, service_areas=service_areas)
    if regions:
        rf = kb.folder("Service lines / regions", visible=False)
        for r in regions:
            st = kb.poly_style(f"region-{r['id']}", r.get("color", "#475569"), fill_alpha=0.05, line_width=3)
            pm = kb.placemark(rf, r["name"], st, _table([
                ("Region", r["name"]), ("Mapped hub line", r.get("hub_line")), ("Note", r.get("note"))
            ], r["name"]), visible=False)
            kb.geojson_geometry(pm, r["geometry"])
    return kb.to_bytes()


# ---------------------------------------------------------------------------
# CSV / GeoJSON
# ---------------------------------------------------------------------------

def to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in columns})
    return "﻿" + buf.getvalue()  # BOM so Excel opens UTF-8 correctly


HUB_CSV_COLUMNS = [
    "hub_id", "name", "display_name", "hub_code", "cluster_id", "cluster_name", "region", "status",
    "is_active", "cluster_mapping", "priority", "demand_level", "latitude", "longitude",
    "location_method", "service_area_km2", "original_folder", "source_line", "issues",
]
CLUSTER_CSV_COLUMNS = [
    "cluster_id", "name", "hub_count", "active_hub_count", "center_lat", "center_lng", "center_method",
    "boundary_area_km2", "service_area_union_km2", "max_hub_distance_km", "mean_nearest_neighbor_km",
    "bbox_min_lat", "bbox_min_lng", "bbox_max_lat", "bbox_max_lng", "source", "name_variants",
    "hubs_outside_boundary",
]
SEARCH_CSV_COLUMNS = [
    "rank", "hub_id", "name", "cluster_name", "latitude", "longitude", "road_distance_km",
    "duration_min", "straight_line_km", "status", "reachable", "reason",
]


def hubs_csv(hubs: list[dict[str, Any]]) -> str:
    rows = [{**h, "issues": "; ".join(h.get("issues") or [])} for h in hubs]
    return to_csv(rows, HUB_CSV_COLUMNS)


def clusters_csv(clusters: list[dict[str, Any]]) -> str:
    rows = []
    for c in clusters:
        bb = c.get("bbox") or [None] * 4
        rows.append({
            **c,
            "bbox_min_lat": bb[0], "bbox_min_lng": bb[1], "bbox_max_lat": bb[2], "bbox_max_lng": bb[3],
            "name_variants": "; ".join(c.get("name_variants") or []),
            "hubs_outside_boundary": "; ".join(c.get("hubs_outside_boundary") or []),
        })
    return to_csv(rows, CLUSTER_CSV_COLUMNS)


def search_csv(result: dict[str, Any]) -> str:
    rows = [{**r, "reachable": True} for r in result.get("ranking") or []]
    rows += [{**u, "reachable": False} for u in result.get("unreachable") or []]
    meta = result["query"]
    header = (
        f"# Nearest hub search {result.get('created_at')} at {meta['latitude']},{meta['longitude']} "
        f"mode={meta.get('travel_mode')} ranking={meta.get('ranking')} provider="
        f"{(result.get('provider') or {}).get('name')} | road_distance_km and duration_min come from the "
        f"routing engine; straight_line_km is the pre-filter distance only\n"
    )
    return "﻿" + header + to_csv(rows, SEARCH_CSV_COLUMNS).lstrip("﻿")


def hubs_geojson(hubs: list[dict[str, Any]]) -> dict[str, Any]:
    feats = []
    for h in hubs:
        if h.get("latitude") is None:
            continue
        props = {k: v for k, v in h.items() if k not in ("metadata",)}
        props["metadata"] = h.get("metadata")
        feats.append({
            "type": "Feature",
            "id": h.get("hub_id"),
            "geometry": {"type": "Point", "coordinates": [h["longitude"], h["latitude"]]},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": feats}


def clusters_geojson(clusters: list[dict[str, Any]]) -> dict[str, Any]:
    feats = []
    for c in clusters:
        geom = c.get("boundary")
        if not geom:
            continue
        props = {k: v for k, v in c.items() if k != "boundary"}
        feats.append({"type": "Feature", "id": c["cluster_id"], "geometry": geom, "properties": props})
    return {"type": "FeatureCollection", "features": feats}
