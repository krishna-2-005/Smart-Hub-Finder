# KML Analysis Report

*Generated 2026-10-15T05:05:13+00:00 from `Akhil Copy.kml`.*

## 1. Summary

| Metric | Value |
|---|---|
| Source file size | 6,236,892 bytes (163,449 lines) |
| SHA-256 of original | `e78c8ed5e549e3ea07b4f0d787f91dbaa4a4533782ac0da6ee730120cbfd82a9` |
| Folders | 9 |
| Placemarks (all) | 2209 |
| Hubs identified | 361 |
| Hubs with valid location | 361 |
| Hubs with invalid/missing location | 0 |
| Unique hub IDs | 361 |
| Clusters | 26 |
| Clusters with boundary polygon | 26 |
| Live hubs / inactive hubs | 348 / 13 |
| Unassigned hubs | 0 |
| Duplicate hub IDs | 0 |
| Duplicate hub names | 0 |
| Duplicate hub locations (≤ 10 m apart) | 0 |
| Isolated hubs (> 3 km from nearest same-cluster hub) | 3 |
| Hubs located outside their cluster's boundary polygon | 9 |
| Placemarks with coordinate/geometry issues | 0 |
| Unclassified placemarks | 1 |

## 2. XML repair

* Well-formed before repair: **no**
* Parser error before repair: `xmlParseEntityRef: no name, line 102639, column 47 (<string>, line 102639)`
* Total automatic fixes: **361** (unescaped_ampersand: 361)
* Well-formed after repair: **yes**
* `<coordinates>` blocks compared before/after: 2,211 — **identical (no coordinate modified)**
* Encoding: utf-8
* First fix at line 102639, column 46: `<Data name="Competiton OB Hotspots & remarks">`

Distinct locations of the fixes (by source text):

| Source text | Occurrences |
|---|---|
| `<Data name="Competiton OB Hotspots & remarks">` | 361 |

Only unescaped `&` characters outside CDATA/comments are escaped to `&amp;`, and characters illegal in XML 1.0 are removed. No other content is changed. The original is preserved as `data/source/original_backup.kml` and the repaired full document as `data/processed/repaired_full.kml`.

## 3. Folder inventory

| Folder | Line | Placemarks | Geometry | Classified as |
|---|---|---|---|---|
| Directions from 1-284/1, Sri Aurobindo Colony, Hyderabad, Miyapur, Telangana 500049, India to | 517 | 1421 | Point: 1413, LineString: 8 | demand_point: 1413, route_line: 8 |
| PMF - high.csv | 81418 | 360 | Point: 360 | demand_point: 360 |
| Cluster_layer | 100867 | 27 | Polygon: 24, MultiGeometry: 2, Point: 1 | cluster_boundary: 26, unclassified: 1 |
| Lines | 101537 | 3 | Polygon: 3 | region: 3 |
| Snabbit live pluscodes - Hyderabad.csv | 101640 | 9 | Point: 9 | competitor_location: 9 |
| Rough View - Sheet10.csv | 101940 | 25 | Point: 25 | screening_record: 25 |
| IH Hyd - Competition Intelligence - Sheet44.csv | 102543 | 361 | Polygon: 361 | hub: 361 |
| Directions from 17.412498, 78.411452 to CC6C+9J5, Lane Number 3, MLA Colony, Banjara Hills, Hyderabad, Telangana 500096, India | 163310 | 3 | LineString: 1, Point: 2 | route_line: 1, route_waypoint: 2 |
| Untitled layer | 163445 | 0 |  |  |

Geometry totals: Point: 1810, LineString: 9, Polygon: 388, MultiGeometry: 2

## 4. Placemark classification

| Category | Count | Rule | Inferred? | Personal data? |
|---|---|---|---|---|
| Demand hotspot (PMF plus-code cell) | 1773 | matched attributes ['PLUS_CODE_280', 'DELS'], geometry ['Point'] | yes | no |
| Hub | 361 | has attribute(s) ['Hub ID'] | no | no |
| Cluster boundary | 26 | polygon whose name matches /(?i)[ _-]?cluster$/ | no | no |
| Screening record (contains personal names - excluded from maps and exports) | 25 | matched attributes ['Screening hubs'] | no | yes |
| Drawn route / direction line | 9 | matched geometry ['LineString', 'MultiLineString'] | no | no |
| Competitor live location (Snabbit) | 9 | matched folder /(?i)snabbit/ | yes | no |
| Service line / region | 3 | polygon in folder matching /^Lines$/ | no | no |
| Directions waypoint | 2 | matched folder /^Directions from/, geometry ['Point'] | no | no |
| Unclassified | 1 | no rule matched | no | no |

> 25 screening records contain personal names. They are counted here but excluded from the map layers and all exports.

## 5. Hubs

| Hub status | Hubs |
|---|---|
| Live | 348 |
| Not Live | 10 |
| To be made live | 3 |

| Hub location method | Hubs |
|---|---|
| service_area_centroid | 360 |
| service_area_interior_point | 1 |

| Region / Line attribute | Hubs |
|---|---|
| eastern_hyd | 100 |
| northern_hyd | 122 |
| southern_hyd | 139 |

## 6. Clusters

* Cluster method: **explicit cluster attribute + cluster boundary polygons**
* Distinct raw cluster attribute values: 34 → 26 clusters after normalisation
* Cluster boundary polygons in source: 26

| Cluster | Spellings merged |
|---|---|
| Borabanda | Borabanda, borabanda |
| Kukatpally | Kukatpally, kukatpally |
| Miyapur | Miyapur, miyapur |
| Nallagandla | Nallagandla, nallagandla |
| Kompally | Kompally, kompally |
| Hitech_City | Hitech_City, hitech_city |
| Bachupally | Bachupally, bachupally |
| Kali_Mandir | Kali_Mandir, Kali_mandir |
| Moula_Ali | Moula_Ali, Moula_ali |
| Kokapet | Kokapet, kokapet |
| Rajendra_Nagar | Rajendra_Nagar, Rajendranagar |

| Cluster | Hubs |
|---|---|
| Kondapur | 28 |
| Borabanda | 25 |
| Kukatpally | 24 |
| Miyapur | 22 |
| Nallagandla | 22 |
| LB_Nagar | 21 |
| Kompally | 20 |
| Madhura_Nagar | 19 |
| Hitech_City | 18 |
| Bachupally | 16 |
| Kachiguda | 16 |
| Ramchandrapuram | 16 |
| Bowenpally | 15 |
| Mehdipatnam | 13 |
| Sainikpuri | 12 |
| Shaikpet | 12 |
| Tarnaka | 9 |
| Attapur | 7 |
| Kali_Mandir | 7 |
| Moula_Ali | 7 |
| Puppalguda | 7 |
| Wipro_Circle | 7 |
| Manikonda | 6 |
| Nanakramguda | 6 |
| Kokapet | 5 |
| Rajendra_Nagar | 1 |

## 7. Service lines / regions

| Region polygon | Label | Mapped hub line | Hubs inside polygon | Hubs with that line | …of which inside polygon |
|---|---|---|---|---|---|
| South | Line 2 | southern_hyd | 139 | 139 | 137 |
| East | Line 3 | eastern_hyd | 99 | 100 | 99 |
| North |  | northern_hyd | 120 | 122 | 118 |

## 8. Data quality

### Duplicate hub IDs (0)

None found.

### Duplicate hub names (0)

None found.

### Duplicate hub locations (0)

None found.

### Invalid or missing hub locations (0)

None found. Every hub has a geometry whose coordinates are within valid latitude/longitude ranges.

### Missing hub names / IDs

Missing names: 0. Missing IDs: 0.

### Unassigned hubs (0)

None.

### Inactive hubs (13)

| Hub ID | Name | Status | Cluster |
|---|---|---|---|
| 68efcc5d579bc90024349880 | bolarum_railway_crossing | Not Live | Kompally |
| 68efcc5d579bc90024349886 | hmt_nagar | Not Live | Tarnaka |
| 68efcc5d579bc900243498ad | nacharam_rd | Not Live | Tarnaka |
| 68efcc5d579bc900243498b0 | anandbagh | Not Live | Sainikpuri |
| 68efcc5d579bc900243498c3 | bowrampet_rd | Not Live | Bachupally |
| 68efcc5d579bc900243498d4 | myhome_avali | Not Live | Nallagandla |
| 68efcc5d579bc900243498d5 | myhome_akrida | Not Live | Nallagandla |
| 68efcc5d579bc900243498d8 | prakruthik_vihar | Not Live | Sainikpuri |
| 68efcc5d579bc900243498f3 | neredmet | Not Live | Moula_Ali |
| 6a036c3a20c29a0025e7cc46 | jayabheri_the_nirvana | To be made live | Wipro_Circle |
| 6a036c3a20c29a0025e7cc47 | mystic_hills | Not Live | Borabanda |
| 6a2ba19548d99f00249dc0e9 | aparna_serenity | To be made live | Kompally |
| 6a2ba19548d99f00249dc0ea | indraprastha_apartements | To be made live | Kompally |

### Isolated hubs (3)

| Hub ID | Name | Cluster | Reason | Nearest hub, any cluster (km) |
|---|---|---|---|---|
| 68efcc5d579bc9002434981d | provident_kenworth | Rajendra_Nagar | only hub in its cluster | 2.556 |
| 68efcc5d579bc900243498b0 | anandbagh | Sainikpuri | nearest hub in same cluster is 3.23 km away (> 3.0 km) | 1.045 |
| 6980e9ccbaa1520023db03a5 | hyderabad_centroid_hub | LB_Nagar | nearest hub in same cluster is 10.06 km away (> 3.0 km) | 0.649 |

### Hubs outside their assigned cluster boundary (9)

The cluster attribute is kept as the authoritative assignment; this list is for review.

| Hub ID | Name | Assigned cluster | Distance outside (km) | Location falls inside |
|---|---|---|---|---|
| 68efcc5d579bc90024349826 | jubilee_enclave_rd | Kondapur | 0.114 | no cluster boundary |
| 68efcc5d579bc9002434980d | divine_allura | Miyapur | 0.074 | no cluster boundary |
| 68efcc5d579bc90024349834 | lingampally_rd | Miyapur | 0.213 | no cluster boundary |
| 69c41f70bf901e002450b2bc | hillside_highrise | Miyapur | 0.511 | no cluster boundary |
| 6980e9ccbaa1520023db03a5 | hyderabad_centroid_hub | LB_Nagar | 9.184 | Shaikpet |
| 68efcc5d579bc90024349825 | anjaiah_nagar | Hitech_City | 0.024 | no cluster boundary |
| 68efcc5d579bc900243498cc | cluster_serilingampally | Ramchandrapuram | 0.305 | no cluster boundary |
| 68efcc5d579bc900243498cd | sridham_hills | Ramchandrapuram | 0.048 | no cluster boundary |
| 68efcc5d579bc900243498b0 | anandbagh | Sainikpuri | 2.397 | Moula_Ali |

### Overlapping hub service areas (3 pairs, overlap > 1% of the smaller polygon)

| Hub A | Hub B | Overlap (km²) | % of smaller |
|---|---|---|---|
| sln_phase3 | sln_phase1 | 0.0093 | 1.5 |
| svs_gardenia | aparna_serenity | 0.0046 | 1.3 |
| surya_towers | auro_realty | 0.0031 | 1.1 |

### Hub records with issues (30)

| Hub ID | Name | KML line | Issues |
|---|---|---|---|
| 68efcc5d579bc900243497cf | radha_krishna_rd | 104645 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈12 m, 95% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243497d5 | himagiri_heights | 105672 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈21 m, 92% area overlap); the drawn polygon is used |
| 69bc37716c4e72002539e0a6 | acz_block | 108747 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈333 m, 58% area overlap); the drawn polygon is used |
| 69c41f70bf901e002450b2b5 | brigade_citadel | 109650 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈1 m, 99% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243497ee | vitial_rao_nagar | 110013 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈521 m, 45% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434980e | botanical_garden_2 | 115529 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈2 m, 99% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434982a | auro_realty | 120217 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈52 m, 86% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434982e | prism_mall | 120897 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈708 m, 40% area overlap); the drawn polygon is used |
| 68efcc5d579bc90024349839 | sln_phase1 | 122727 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈69 m, 84% area overlap); the drawn polygon is used |
| 69cc1478095ac20024cc2d26 | indis_prospera | 123899 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈528 m, 76% area overlap); the drawn polygon is used |
| 68efcc5d579bc90024349846 | kailash_apartments | 124925 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈96 m, 97% area overlap); the drawn polygon is used |
| 68efcc5d579bc90024349858 | kukatpally_lake | 127942 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈702 m, 39% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434985a | sangeetha_nagarã¢ | 128273 | hub name contains garbled encoding characters ['ã¢']; kept unchanged in 'name', removed from 'display_name' |
| 68efcc5d579bc9002434985f | nestila_apartment | 129112 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈170 m, 88% area overlap); the drawn polygon is used |
| 68efcc5d579bc90024349865 | kousalya_colony | 130126 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈324 m, 90% area overlap); the drawn polygon is used |
| 6a036c3a20c29a0025e7cc2e | gunrock_enclave_rd | 131455 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈328 m, 56% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434987e | patel_green_park | 134316 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈89 m, 94% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434988c | prakash_nagar | 136675 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈10 m, 96% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434988e | banjarahills_rd3 | 137007 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈337 m, 71% area overlap); the drawn polygon is used |
| 68efcc5d579bc9002434988f | yousufguda | 137175 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈2 m, 99% area overlap); the drawn polygon is used |
| 68efcc5d579bc90024349890 | gs_nagar | 137342 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈245 m, 60% area overlap); the drawn polygon is used |
| 6a036c3a20c29a0025e7cc26 | om_towers | 139333 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈17 m, 95% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243498ab | saraswathi_nagar | 141769 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈5 m, 99% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243498c2 | king_koti | 145355 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈81 m, 79% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243498c7 | nsk_platina | 146198 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈482 m, 59% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243498f0 | my_home_tridasa | 153034 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈956 m, 23% area overlap); the drawn polygon is used |
| 68efcc5d579bc900243498f2 | niloufer_rd | 153392 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈3 m, 99% area overlap); the drawn polygon is used |
| 69497ec5ced32d0027560422 | aparna_zenith | 154561 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈207 m, 74% area overlap); the drawn polygon is used |
| 69cc1478095ac20024cc2d27 | kendriya_vihar | 157073 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈175 m, 93% area overlap); the drawn polygon is used |
| 6a036c3a20c29a0025e7cc46 | jayabheri_the_nirvana | 161319 | 'New polygon' WKT attribute differs from the drawn polygon (max deviation ≈2 m, 99% area overlap); the drawn polygon is used |

### All placemarks with coordinate or geometry issues (0)

None.

### Unclassified placemarks (1)

| KML line | Name | Folder | Geometry |
|---|---|---|---|
| 101502 | Point 28 | Cluster_layer | Point |

### Text encoding anomalies (16)

Values containing garbled encoding sequences (UTF-8 text mis-decoded as Latin-1, e.g. `ã¢`), left unchanged in the data: line 31960 `INSTA_HUB` (demand_point), line 37306 `INSTA_HUB` (demand_point), line 51509 `INSTA_HUB` (demand_point), line 51941 `INSTA_HUB` (demand_point), line 54425 `INSTA_HUB` (demand_point), line 55181 `INSTA_HUB` (demand_point), line 65279 `INSTA_HUB` (demand_point), line 70194 `INSTA_HUB` (demand_point), line 73434 `INSTA_HUB` (demand_point), line 101942 `Screening hubs` (screening_record), line 102086 `Screening hubs` (screening_record), line 102182 `Screening hubs` (screening_record), line 128273 `<name>` (hub), line 128273 `Hub` (hub), line 128273 `unnamed (2)` (hub), line 128273 `unnamed (3)` (hub)

## 9. Other layers

| Layer | Features |
|---|---|
| Demand hotspots (PMF plus-code cells) | 1773 |
| …plus codes present in more than one demand folder | 0 |
| Competitor locations | 9 |
| Drawn route lines from source | 9 |
| Screening records (excluded, personal data) | 25 |

## 10. Assumptions and inferred classifications

| Topic | Assumption | Inferred? |
|---|---|---|
| Hub identification | A placemark is treated as a hub only if it carries a 'Hub ID' attribute (or both 'Hub' and 'Cluster'). Demand points, competitor points, screening records, cluster/region polygons and drawn lines are classified separately and are never treated as hubs. | no |
| Hub coordinates | Hubs are stored in the KML as service-area polygons without an explicit hub point. The hub location used for search and routing is the polygon centroid (360 hubs) or, where the centroid falls outside a concave polygon, an interior point guaranteed to lie inside it (1 hubs). Original polygon coordinates are preserved unchanged. | yes |
| Cluster names | Cluster attribute values are matched case- and punctuation-insensitively, and a trailing 'Cluster' is ignored when matching boundary polygons, so variants such as Borabanda = ['Borabanda', 'borabanda'], Kukatpally = ['Kukatpally', 'kukatpally'], Miyapur = ['Miyapur', 'miyapur'], Nallagandla = ['Nallagandla', 'nallagandla'] are one cluster. | yes |
| Operational status | The 'Hub status' attribute is used as given. Only 'Live' counts as active; 'Not Live' and 'To be made live' are inactive and can be excluded from nearest-hub searches. | no |
| Regions | Inferred: region polygons named South/East/North are matched to the hub 'Line' attribute values southern_hyd/eastern_hyd/northern_hyd by compass direction. | yes |
| Demand hotspot (PMF plus-code cell) | Points carrying USERS/DELS/DEL_BUCKET demand metrics per Plus Code cell. | yes |
| Competitor live location (Snabbit) | Folder name 'Snabbit live pluscodes'; Snabbit is listed as a competitor in the hub Competition Intelligence attributes. | yes |
| Hub type | The KML has no explicit hub type/category field, so hub_type is stored as null. 'Cluster Mapping' (competitive / non-competitive) and the PMF demand level are exposed as separate attributes. | no |
