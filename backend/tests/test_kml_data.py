"""Data tests against the real KML: repair, counts, classification, clusters, coordinates."""

from __future__ import annotations

import re

from lxml import etree

from app.services.kml_parser import parse_coordinates, parse_kml_text
from app.services.kml_repair import repair_kml_bytes

from .conftest import SOURCE_KML


def test_original_is_invalid_and_repair_is_minimal():
    data = SOURCE_KML.read_bytes()
    r = repair_kml_bytes(data)
    assert not r.valid_before, "the source KML is known to be malformed"
    assert "102639" in (r.parse_error_before or "")
    assert r.valid_after
    assert r.coordinates_unchanged
    assert {c.kind for c in r.changes} == {"unescaped_ampersand"}
    assert all(c.context == '<Data name="Competiton OB Hotspots & remarks">' for c in r.changes)
    # The repaired text differs from the original only by '&' -> '&amp;'
    assert r.text.replace("&amp;", "&") == data.decode("utf-8").replace("&amp;", "&")


def test_repair_leaves_cdata_untouched():
    kml = b"""<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
      <Placemark><name>A & B</name><description><![CDATA[x & y]]></description>
      <Point><coordinates>78.1,17.2,0</coordinates></Point></Placemark></Document></kml>"""
    r = repair_kml_bytes(kml)
    assert r.valid_after and len(r.changes) == 1
    assert "<![CDATA[x & y]]>" in r.text
    assert "<name>A &amp; B</name>" in r.text


def test_placemark_and_folder_counts(analysis):
    raw = SOURCE_KML.read_text(encoding="utf-8")
    assert analysis["placemark_count"] == raw.count("<Placemark>") == 2209
    assert len(analysis["folders"]) == raw.count("<Folder>") == 9
    assert sum(analysis["category_counts"].values()) == analysis["placemark_count"]


def test_hub_classification(analysis, hubs):
    assert analysis["category_counts"]["hub"] == 361
    assert len(hubs) == 361
    # Every hub comes from the competition-intelligence folder and carries a Hub ID
    assert {h["original_folder"] for h in hubs} == {"IH Hyd - Competition Intelligence - Sheet44.csv"}
    assert all(h["hub_id"] and re.fullmatch(r"[0-9a-f]{24}", h["hub_id"]) for h in hubs)
    # Non-hub layers are not hubs
    assert analysis["category_counts"]["demand_point"] == 1773
    assert analysis["category_counts"]["cluster_boundary"] == 26
    assert analysis["category_counts"]["screening_record"] == 25


def test_status_counts(analysis):
    assert analysis["hubs"]["status_counts"] == {"Live": 348, "Not Live": 10, "To be made live": 3}


def test_duplicate_detection(analysis, hubs):
    q = analysis["quality"]
    assert q["duplicate_hub_ids"] == {}
    assert len({h["hub_id"] for h in hubs}) == len(hubs)
    assert q["duplicate_locations"] == []


def test_cluster_normalisation_and_counts(clusters, hubs):
    assert len(clusters) == 26
    by_name = {c["name"]: c for c in clusters}
    assert by_name["Kondapur"]["hub_count"] == 28
    # Case variants merged: 'Hitech_City' (16) + 'hitech_city' (2)
    assert by_name["Hitech_City"]["hub_count"] == 18
    assert set(by_name["Hitech_City"]["name_variants"]) >= {"Hitech_City", "hitech_city"}
    # Boundary name 'Rajendranagar_cluster' matched to attribute 'Rajendra_Nagar'
    assert by_name["Rajendra_Nagar"]["boundary"] is not None
    assert sum(c["hub_count"] for c in clusters) == len(hubs)
    assert all(c["boundary"] for c in clusters)
    assert all(h["cluster_id"] for h in hubs)


def test_cluster_assignment_matches_attribute(hubs):
    from app.services.cluster_service import cluster_key

    for h in hubs:
        assert cluster_key(h["cluster_raw"]) == cluster_key(h["cluster_name"])


def test_coordinate_order_is_lon_lat(hubs, clusters):
    # Hyderabad: latitude ~17.x, longitude ~78.x. A swap would put latitude near 78.
    for h in hubs:
        assert 17.0 < h["latitude"] < 18.0 and 78.0 < h["longitude"] < 79.0
    for c in clusters:
        assert 17.0 < c["center_lat"] < 18.0 and 78.0 < c["center_lng"] < 79.0


def test_hub_location_lies_inside_its_service_area(store):
    from shapely.geometry import Point, shape

    for h in store.hubs:
        poly = shape(store.service_areas[h["hub_id"]])
        assert poly.covers(Point(h["longitude"], h["latitude"])), h["name"]


def test_parse_coordinates_validation():
    issues: list[str] = []
    pts = parse_coordinates("78.1,17.2,0 abc,1 200,10 17.2,95 78.3,17.4", issues)
    assert pts == [(78.1, 17.2, 0.0), (78.3, 17.4, None)]
    assert any("non-numeric" in i for i in issues)
    assert any("swapped" in i for i in issues)


def test_parser_handles_multigeometry_and_no_namespace():
    kml = """<kml><Document><Folder><name>F</name>
      <Placemark><name>mp</name><MultiGeometry>
        <Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,0</coordinates></LinearRing></outerBoundaryIs></Polygon>
        <Polygon><outerBoundaryIs><LinearRing><coordinates>2,2 3,2 3,3 2,2</coordinates></LinearRing></outerBoundaryIs></Polygon>
      </MultiGeometry></Placemark></Folder></Document></kml>"""
    parsed = parse_kml_text(kml)
    assert parsed.placemarks[0].geometry.geom_type == "MultiPolygon"
    assert parsed.placemarks[0].folder == "F"


def test_outputs_written(processed_dir):
    for name in ("hubs.json", "hubs.geojson", "clusters.json", "kml_analysis_report.md", "cleaned_hubs.kml",
                 "repaired_full.kml", "analysis.json"):
        assert (processed_dir / name).exists(), name
    etree.parse(str(processed_dir / "cleaned_hubs.kml"))  # well-formed
    report = (processed_dir / "kml_analysis_report.md").read_text(encoding="utf-8")
    assert "| Hubs identified | 361 |" in report
    assert "| Clusters | 26 |" in report


def test_personal_names_not_exported(processed_dir):
    """Screening records carry personal names; none may leak into layers, hubs or KML."""
    text = (processed_dir / "repaired_full.kml").read_text(encoding="utf-8")
    parsed = parse_kml_text(text)
    people = {pm.extended_data["Name"] for pm in parsed.placemarks
              if "Screening hubs" in pm.extended_data and pm.extended_data.get("Name")}
    assert len(people) > 0
    outputs = [processed_dir / "cleaned_hubs.kml", processed_dir / "hubs.json", processed_dir / "clusters.json",
               *(processed_dir / "layers").glob("*.geojson")]
    for f in outputs:
        content = f.read_text(encoding="utf-8")
        leaked = [p for p in people if p in content]
        assert not leaked, f"{f.name} contains {len(leaked)} personal names"


def test_untrusted_xml_entities_are_not_expanded():
    """XXE / billion-laughs payloads must not be expanded by the parser used for uploads."""
    evil = b"""<?xml version="1.0"?>
<!DOCTYPE kml [<!ENTITY a "AAAAAAAAAA"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
 <!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>&b;&xxe;</name>
<Point><coordinates>78.1,17.2,0</coordinates></Point></Placemark></Document></kml>"""
    r = repair_kml_bytes(evil)
    parsed = parse_kml_text(r.text)
    name = parsed.placemarks[0].name or ""
    assert "AAAAAAAAAA" not in name and "fonts" not in name.lower()
