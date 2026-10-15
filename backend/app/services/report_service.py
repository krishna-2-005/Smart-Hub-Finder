"""Render the KML analysis dictionary as a markdown report.

Every number in the report is read from the analysis produced by the pipeline;
nothing is hard-coded.
"""

from __future__ import annotations

from typing import Any


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(v: Any) -> str:
        s = "" if v is None else str(v)
        return s.replace("|", "\\|").replace("\n", " ")

    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def render_markdown_report(a: dict[str, Any]) -> str:
    s, r, h, c, q = a["source"], a["repair"], a["hubs"], a["clusters"], a["quality"]
    L: list[str] = []
    L.append("# KML Analysis Report")
    L.append("")
    L.append(f"*Generated {s['processed_at']} from `{s['file_name']}`.*")
    L.append("")
    L.append("## 1. Summary")
    L.append("")
    L.append(_md_table(["Metric", "Value"], [
        ["Source file size", f"{s['size_bytes']:,} bytes ({s['line_count']:,} lines)"],
        ["SHA-256 of original", f"`{s['sha256']}`"],
        ["Folders", len(a["folders"])],
        ["Placemarks (all)", a["placemark_count"]],
        ["Hubs identified", h["total"]],
        ["Hubs with valid location", h["valid_location"]],
        ["Hubs with invalid/missing location", h["invalid_location"]],
        ["Unique hub IDs", h["unique_hub_ids"]],
        ["Clusters", c["total"]],
        ["Clusters with boundary polygon", c["with_boundary"]],
        ["Live hubs / inactive hubs", f"{h['active']} / {h['inactive']}"],
        ["Unassigned hubs", len(q["unassigned_hubs"])],
        ["Duplicate hub IDs", len(q["duplicate_hub_ids"])],
        ["Duplicate hub names", len(q["duplicate_hub_names"])],
        [f"Duplicate hub locations (≤ {q['duplicate_location_threshold_m']:g} m apart)", len(q["duplicate_locations"])],
        [f"Isolated hubs (> {q['isolation_threshold_km']:g} km from nearest same-cluster hub)", len(q["isolated_hubs"])],
        ["Hubs located outside their cluster's boundary polygon", len(q["cluster_boundary_mismatches"])],
        ["Placemarks with coordinate/geometry issues", len(a["coordinate_issues"])],
        ["Unclassified placemarks", len(a["unclassified"])],
    ]))
    L.append("")

    L.append("## 2. XML repair")
    L.append("")
    L.append(f"* Well-formed before repair: **{'yes' if r['valid_before'] else 'no'}**")
    if r["parse_error_before"]:
        L.append(f"* Parser error before repair: `{r['parse_error_before']}`")
    L.append(f"* Total automatic fixes: **{r['total_changes']}** ({', '.join(f'{k}: {v}' for k, v in r['changes_by_kind'].items()) or 'none'})")
    L.append(f"* Well-formed after repair: **{'yes' if r['valid_after'] else 'no'}**")
    L.append(f"* `<coordinates>` blocks compared before/after: {r['coordinate_blocks']:,} — "
             f"**{'identical (no coordinate modified)' if r['coordinates_unchanged'] else 'DIFFERENT'}**")
    L.append(f"* Encoding: {r['encoding']}{' (BOM removed)' if r['had_bom'] else ''}")
    if r["first_change"]:
        fc = r["first_change"]
        L.append(f"* First fix at line {fc['line']}, column {fc['column']}: `{fc['context']}`")
    if r["distinct_contexts"]:
        L.append("")
        L.append("Distinct locations of the fixes (by source text):")
        L.append("")
        L.append(_md_table(["Source text", "Occurrences"],
                           [[f"`{d['context']}`", d["occurrences"]] for d in r["distinct_contexts"]]))
    L.append("")
    L.append("Only unescaped `&` characters outside CDATA/comments are escaped to `&amp;`, and characters "
             "illegal in XML 1.0 are removed. No other content is changed. The original is preserved as "
             "`data/source/original_backup.kml` and the repaired full document as `data/processed/repaired_full.kml`.")
    L.append("")

    L.append("## 3. Folder inventory")
    L.append("")
    L.append(_md_table(
        ["Folder", "Line", "Placemarks", "Geometry", "Classified as"],
        [[f["name"], f["source_line"], f["placemark_count"],
          ", ".join(f"{k}: {v}" for k, v in f["geometry_counts"].items()),
          ", ".join(f"{k}: {v}" for k, v in f["categories"].items())] for f in a["folders"]],
    ))
    L.append("")
    L.append("Geometry totals: " + ", ".join(f"{k}: {v}" for k, v in a["geometry_counts"].items()))
    L.append("")

    L.append("## 4. Placemark classification")
    L.append("")
    L.append(_md_table(
        ["Category", "Count", "Rule", "Inferred?", "Personal data?"],
        [[d["label"], d["count"], d["rule"], "yes" if d["inferred"] else "no", "yes" if d["pii"] else "no"]
         for d in sorted(a["categories"], key=lambda d: -d["count"])],
    ))
    L.append("")
    if a["layers"]["screening_records_excluded_pii"]:
        L.append(f"> {a['layers']['screening_records_excluded_pii']} screening records contain personal names. "
                 "They are counted here but excluded from the map layers and all exports.")
        L.append("")

    L.append("## 5. Hubs")
    L.append("")
    L.append(_md_table(["Hub status", "Hubs"], [[k, v] for k, v in sorted(h["status_counts"].items(), key=lambda kv: -kv[1])]))
    L.append("")
    L.append(_md_table(["Hub location method", "Hubs"], [[k, v] for k, v in h["location_methods"].items()]))
    L.append("")
    L.append(_md_table(["Region / Line attribute", "Hubs"], [[k, v] for k, v in sorted(h["region_counts"].items())]))
    L.append("")

    L.append("## 6. Clusters")
    L.append("")
    L.append(f"* Cluster method: **{c['method']}**")
    L.append(f"* Distinct raw cluster attribute values: {c['raw_cluster_values']} → {c['with_hubs']} clusters after normalisation")
    L.append(f"* Cluster boundary polygons in source: {c['boundary_polygons_in_source']}")
    if c["clusters_without_boundary"]:
        L.append(f"* Clusters with hubs but no boundary polygon: {', '.join(c['clusters_without_boundary'])}")
    if c["boundaries_without_hubs"]:
        L.append(f"* Boundary polygons with no hubs: {', '.join(c['boundaries_without_hubs'])}")
    if q["cluster_name_variants"]:
        L.append("")
        L.append(_md_table(["Cluster", "Spellings merged"],
                           [[k, ", ".join(v)] for k, v in q["cluster_name_variants"].items()]))
    L.append("")
    L.append(_md_table(["Cluster", "Hubs"], [[k, v] for k, v in c["hub_counts"].items()]))
    L.append("")

    if a["regions"]:
        L.append("## 7. Service lines / regions")
        L.append("")
        L.append(_md_table(
            ["Region polygon", "Label", "Mapped hub line", "Hubs inside polygon", "Hubs with that line",
             "…of which inside polygon"],
            [[x["name"], x["label"], x["hub_line"], x["hubs_inside_polygon"], x["hubs_with_line_attribute"],
              x["line_hubs_inside_polygon"]] for x in a["regions"]],
        ))
        L.append("")

    L.append("## 8. Data quality")
    L.append("")
    L.append(f"### Duplicate hub IDs ({len(q['duplicate_hub_ids'])})")
    L.append("")
    L.append(", ".join(f"`{k}` ×{v}" for k, v in q["duplicate_hub_ids"].items()) or "None found.")
    L.append("")
    L.append(f"### Duplicate hub names ({len(q['duplicate_hub_names'])})")
    L.append("")
    L.append(", ".join(f"`{k}` ×{v}" for k, v in q["duplicate_hub_names"].items()) or "None found.")
    L.append("")
    L.append(f"### Duplicate hub locations ({len(q['duplicate_locations'])})")
    L.append("")
    if q["duplicate_locations"]:
        L.append(_md_table(["Hub A", "Hub B", "Distance (m)"],
                           [[d["hub_a"], d["hub_b"], d["distance_m"]] for d in q["duplicate_locations"]]))
    else:
        L.append("None found.")
    L.append("")
    L.append(f"### Invalid or missing hub locations ({len(q['invalid_locations'])})")
    L.append("")
    if q["invalid_locations"]:
        L.append(_md_table(["Hub ID", "Name", "Issues"],
                           [[d["hub_id"], d["name"], "; ".join(d["issues"])] for d in q["invalid_locations"]]))
    else:
        L.append("None found. Every hub has a geometry whose coordinates are within valid latitude/longitude ranges.")
    L.append("")
    L.append("### Missing hub names / IDs")
    L.append("")
    L.append(f"Missing names: {len(q['missing_hub_names'])}. Missing IDs: {len(q['missing_hub_ids'])}.")
    L.append("")
    L.append(f"### Unassigned hubs ({len(q['unassigned_hubs'])})")
    L.append("")
    L.append(", ".join(f"{d['name']} ({d['hub_id']})" for d in q["unassigned_hubs"]) or "None.")
    L.append("")
    L.append(f"### Inactive hubs ({len(q['inactive_hubs'])})")
    L.append("")
    if q["inactive_hubs"]:
        L.append(_md_table(["Hub ID", "Name", "Status", "Cluster"],
                           [[d["hub_id"], d["name"], d["status"], d["cluster"]] for d in q["inactive_hubs"]]))
    L.append("")
    L.append(f"### Isolated hubs ({len(q['isolated_hubs'])})")
    L.append("")
    if q["isolated_hubs"]:
        L.append(_md_table(["Hub ID", "Name", "Cluster", "Reason", "Nearest hub, any cluster (km)"],
                           [[d["hub_id"], d["name"], d["cluster"], d["reason"], d["nearest_any_km"]]
                            for d in q["isolated_hubs"]]))
    else:
        L.append("None.")
    L.append("")
    L.append(f"### Hubs outside their assigned cluster boundary ({len(q['cluster_boundary_mismatches'])})")
    L.append("")
    if q["cluster_boundary_mismatches"]:
        L.append("The cluster attribute is kept as the authoritative assignment; this list is for review.")
        L.append("")
        L.append(_md_table(["Hub ID", "Name", "Assigned cluster", "Distance outside (km)", "Location falls inside"],
                           [[d["hub_id"], d["name"], d["assigned_cluster"], d["distance_outside_assigned_boundary_km"],
                             ", ".join(d["location_inside_cluster_boundaries"]) or "no cluster boundary"]
                            for d in q["cluster_boundary_mismatches"]]))
    else:
        L.append("None.")
    L.append("")
    L.append(f"### Overlapping hub service areas ({len(q['overlapping_service_areas'])} pairs, overlap > 1% of the smaller polygon)")
    L.append("")
    if q["overlapping_service_areas"]:
        rows = sorted(q["overlapping_service_areas"], key=lambda d: -d["overlap_pct_of_smaller"])[:25]
        L.append(_md_table(["Hub A", "Hub B", "Overlap (km²)", "% of smaller"],
                           [[d["name_a"], d["name_b"], d["overlap_km2"], d["overlap_pct_of_smaller"]] for d in rows]))
        if len(q["overlapping_service_areas"]) > 25:
            L.append(f"\n…and {len(q['overlapping_service_areas']) - 25} more (see `analysis.json`).")
    L.append("")
    L.append(f"### Hub records with issues ({len(q['hubs_with_issues'])})")
    L.append("")
    if q["hubs_with_issues"]:
        L.append(_md_table(["Hub ID", "Name", "KML line", "Issues"],
                           [[d["hub_id"], d["name"], d["source_line"], "; ".join(d["issues"])]
                            for d in q["hubs_with_issues"][:60]]))
    L.append("")
    L.append(f"### All placemarks with coordinate or geometry issues ({len(a['coordinate_issues'])})")
    L.append("")
    if a["coordinate_issues"]:
        L.append(_md_table(["KML line", "Name", "Folder", "Category", "Issues"],
                           [[d["source_line"], d["name"], d["folder"], d["category"], "; ".join(d["issues"])]
                            for d in a["coordinate_issues"][:60]]))
    else:
        L.append("None.")
    L.append("")
    L.append(f"### Unclassified placemarks ({len(a['unclassified'])})")
    L.append("")
    if a["unclassified"]:
        L.append(_md_table(["KML line", "Name", "Folder", "Geometry"],
                           [[d["source_line"], d["name"], d["folder"], d["geometry"]] for d in a["unclassified"]]))
    L.append("")
    if a["encoding_anomalies"]:
        L.append(f"### Text encoding anomalies ({len(a['encoding_anomalies'])})")
        L.append("")
        L.append("Values containing garbled encoding sequences (UTF-8 text mis-decoded as Latin-1, e.g. `ã¢`), "
                 "left unchanged in the data: "
                 + ", ".join(f"line {d['source_line']} `{d['field']}` ({d.get('category', '')})"
                             for d in a["encoding_anomalies"][:30])
                 + (f" … and {len(a['encoding_anomalies']) - 30} more" if len(a["encoding_anomalies"]) > 30 else ""))
        L.append("")

    L.append("## 9. Other layers")
    L.append("")
    ly = a["layers"]
    L.append(_md_table(["Layer", "Features"], [
        ["Demand hotspots (PMF plus-code cells)", ly["demand_points"]],
        ["…plus codes present in more than one demand folder", ly["demand_points_shared_plus_codes"]],
        ["Competitor locations", ly["competitor_locations"]],
        ["Drawn route lines from source", ly["source_route_lines"]],
        ["Screening records (excluded, personal data)", ly["screening_records_excluded_pii"]],
    ]))
    L.append("")

    L.append("## 10. Assumptions and inferred classifications")
    L.append("")
    L.append(_md_table(["Topic", "Assumption", "Inferred?"],
                       [[x["topic"], x["text"], x["inferred"]] for x in a["assumptions"]]))
    L.append("")
    return "\n".join(L)
