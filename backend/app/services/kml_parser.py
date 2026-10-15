"""Namespace-agnostic KML parser.

Produces one :class:`ParsedPlacemark` per ``<Placemark>`` with its folder path,
attributes (``ExtendedData``), geometry and any coordinate problems found.

KML coordinate order is ``longitude,latitude[,altitude]``; shapely geometries
built here keep that (x=lon, y=lat) convention.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from lxml import etree
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

from .kml_repair import safe_parser

GEOMETRY_TAGS = {"Point", "LineString", "LinearRing", "Polygon", "MultiGeometry", "Track", "MultiTrack", "Model"}
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _child(el: etree._Element, name: str) -> etree._Element | None:
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el: etree._Element, name: str) -> list[etree._Element]:
    return [c for c in el if _local(c.tag) == name]


def _text(el: etree._Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    t = el.text.strip()
    return t or None


@dataclass
class ParsedPlacemark:
    index: int
    source_line: int | None
    folder_path: list[str]
    name: str | None
    description: str | None
    style_url: str | None
    extended_data: dict[str, str]
    geometry_type: str | None
    geometry: BaseGeometry | None
    coordinate_count: int
    issues: list[str] = field(default_factory=list)
    geometry_repaired: BaseGeometry | None = None  # make_valid() result, analysis only

    @property
    def folder(self) -> str | None:
        return self.folder_path[-1] if self.folder_path else None

    @property
    def has_valid_geometry(self) -> bool:
        return self.geometry is not None and not self.geometry.is_empty

    def analysis_geometry(self) -> BaseGeometry | None:
        """Geometry to use for spatial computations (repaired copy if the original is invalid)."""
        return self.geometry_repaired if self.geometry_repaired is not None else self.geometry


@dataclass
class ParsedFolder:
    path: list[str]
    name: str
    placemark_count: int
    source_line: int | None


@dataclass
class ParsedKml:
    document_name: str | None
    folders: list[ParsedFolder]
    placemarks: list[ParsedPlacemark]
    style_ids: list[str]


def parse_coordinates(raw: str | None, issues: list[str]) -> list[tuple[float, float, float | None]]:
    """Parse a KML ``<coordinates>`` string into ``[(lon, lat, alt|None)]``.

    Invalid tuples are dropped and described in ``issues``.
    """
    out: list[tuple[float, float, float | None]] = []
    if not raw:
        issues.append("empty <coordinates> element")
        return out
    for token in raw.split():
        parts = token.split(",")
        if len(parts) < 2:
            issues.append(f"coordinate tuple '{token[:40]}' has fewer than 2 values")
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
            alt = float(parts[2]) if len(parts) > 2 and parts[2] != "" else None
        except ValueError:
            issues.append(f"non-numeric coordinate '{token[:40]}'")
            continue
        if any(math.isnan(v) or math.isinf(v) for v in (lon, lat)):
            issues.append(f"non-finite coordinate '{token[:40]}'")
            continue
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            if -180 <= lat <= 180 and -90 <= lon <= 90:
                issues.append(f"coordinate out of range, looks like swapped lat/lon '{token[:40]}'")
            else:
                issues.append(f"coordinate out of range '{token[:40]}'")
            continue
        out.append((lon, lat, alt))
    return out


def _ring(el: etree._Element | None, issues: list[str]) -> list[tuple[float, float]] | None:
    if el is None:
        return None
    lr = _child(el, "LinearRing")
    coords_el = _child(lr, "coordinates") if lr is not None else None
    pts = [(c[0], c[1]) for c in parse_coordinates(_text(coords_el), issues)]
    if len(pts) >= 3 and pts[0] != pts[-1]:
        issues.append("polygon ring not closed in source (closed automatically for analysis)")
        pts.append(pts[0])
    if len(pts) < 4:
        issues.append(f"polygon ring has only {len(pts)} valid points")
        return None
    return pts


def _geometry(el: etree._Element, issues: list[str]) -> tuple[BaseGeometry | None, int]:
    """Build a shapely geometry from a KML geometry element. Returns (geometry, coord_count)."""
    tag = _local(el.tag)
    if tag == "Point":
        pts = parse_coordinates(_text(_child(el, "coordinates")), issues)
        if not pts:
            return None, 0
        if len(pts) > 1:
            issues.append("Point has more than one coordinate; first one used")
        return Point(pts[0][0], pts[0][1]), 1
    if tag in ("LineString", "LinearRing"):
        pts = parse_coordinates(_text(_child(el, "coordinates")), issues)
        if len(pts) < 2:
            issues.append(f"{tag} has only {len(pts)} valid points")
            return None, len(pts)
        return LineString([(p[0], p[1]) for p in pts]), len(pts)
    if tag == "Polygon":
        outer = _ring(_child(el, "outerBoundaryIs"), issues)
        if outer is None:
            return None, 0
        holes = [h for h in (_ring(ib, issues) for ib in _children(el, "innerBoundaryIs")) if h]
        return Polygon(outer, holes), len(outer) + sum(len(h) for h in holes)
    if tag == "MultiGeometry":
        parts: list[BaseGeometry] = []
        total = 0
        for c in el:
            if _local(c.tag) in GEOMETRY_TAGS:
                g, n = _geometry(c, issues)
                total += n
                if g is not None:
                    parts.append(g)
        if not parts:
            return None, total
        kinds = {p.geom_type for p in parts}
        if kinds == {"Polygon"}:
            return MultiPolygon(parts), total
        if kinds == {"Point"}:
            return MultiPoint(parts), total
        if kinds == {"LineString"}:
            return MultiLineString(parts), total
        return GeometryCollection(parts), total
    issues.append(f"unsupported geometry type <{tag}>")
    return None, 0


def _extended_data(pm: etree._Element) -> dict[str, str]:
    data: dict[str, str] = {}
    ed = _child(pm, "ExtendedData")
    if ed is None:
        return data
    for d in ed.iter():
        lt = _local(d.tag)
        if lt == "Data":
            key = d.get("name") or ""
            data[key] = (_text(_child(d, "value")) or "")
        elif lt == "SimpleData":
            data[d.get("name") or ""] = (d.text or "").strip()
    return data


def parse_kml_text(text: str) -> ParsedKml:
    root = etree.fromstring(text.encode("utf-8"), parser=safe_parser())
    doc = _child(root, "Document")
    if doc is None:  # lxml elements are falsy when childless, so no `or` shortcut
        doc = root
    placemarks: list[ParsedPlacemark] = []
    folders: list[ParsedFolder] = []
    style_ids = [s.get("id") for s in doc.iter() if _local(s.tag) in ("Style", "StyleMap") and s.get("id")]

    def walk(container: etree._Element, path: list[str]) -> int:
        count = 0
        for el in container:
            lt = _local(el.tag)
            if lt in ("Folder", "Document"):
                name = _text(_child(el, "name")) or "(unnamed folder)"
                folder = ParsedFolder(path=path + [name], name=name, placemark_count=0, source_line=el.sourceline)
                folders.append(folder)
                folder.placemark_count = walk(el, path + [name])
                count += folder.placemark_count
            elif lt == "Placemark":
                placemarks.append(_parse_placemark(el, len(placemarks), path))
                count += 1
        return count

    walk(doc, [])
    return ParsedKml(
        document_name=_text(_child(doc, "name")),
        folders=folders,
        placemarks=placemarks,
        style_ids=style_ids,
    )


def _parse_placemark(pm: etree._Element, index: int, path: list[str]) -> ParsedPlacemark:
    issues: list[str] = []
    geom_el = next((c for c in pm if _local(c.tag) in GEOMETRY_TAGS), None)
    geometry: BaseGeometry | None = None
    count = 0
    gtype: str | None = None
    if geom_el is None:
        issues.append("placemark has no geometry")
    else:
        gtype = _local(geom_el.tag)
        geometry, count = _geometry(geom_el, issues)
        if geometry is None:
            issues.append("geometry could not be built from valid coordinates")

    repaired = None
    if geometry is not None and not geometry.is_valid:
        issues.append(f"invalid geometry: {explain_validity(geometry)}")
        from shapely.validation import make_valid

        repaired = make_valid(geometry)

    return ParsedPlacemark(
        index=index,
        source_line=pm.sourceline,
        folder_path=list(path),
        name=_text(_child(pm, "name")),
        description=_text(_child(pm, "description")),
        style_url=_text(_child(pm, "styleUrl")),
        extended_data=_extended_data(pm),
        geometry_type=gtype,
        geometry=geometry,
        coordinate_count=count,
        issues=issues,
        geometry_repaired=repaired,
    )


def strip_html(text: str | None) -> str | None:
    if not text:
        return text
    return HTML_TAG_RE.sub(" ", text).strip()
