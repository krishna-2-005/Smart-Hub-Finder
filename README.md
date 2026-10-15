# Smart Hub Location & Routing System

A web application that turns the `Akhil Copy.kml` hub network into a working tool: it repairs and analyses the KML,
organises hubs into clusters, finds the **nearest hub by real road distance** from typed coordinates or the user's live
GPS location, draws the **road-following route** with turn-by-turn directions, and exports everything as
**Google Earth–compatible KML**.

- **Backend:** Python 3.10+, FastAPI, Shapely, lxml, SQLite
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, React-Leaflet, Recharts, Lucide icons
- **Routing:** Google Maps Routes API, OSRM or OpenRouteService behind one provider interface. OSRM works without a key.

---

## Quick start (Windows)

Prerequisites: Python 3.10+ and Node.js 18+.

```powershell
# one-time setup: venv + packages, KML repair/analysis, npm install
powershell -ExecutionPolicy Bypass -File .\setup.ps1

# terminal 1 – API on http://127.0.0.1:8000  (interactive docs: /docs)
.\start-backend.ps1

# terminal 2 – dashboard on http://localhost:5173
.\start-frontend.ps1
```

Open **http://localhost:5173**. Manual equivalent of the scripts:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m scripts.process_kml            # repair + analyse the KML -> data/processed
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ..\frontend
npm install
npm run dev
```

Road routing works immediately through the public OSRM servers. To use Google instead, copy `backend/.env.example` to
`backend/.env`, set `GOOGLE_MAPS_API_KEY`, and restart the backend (see [Routing](#routing-providers)).

**Phone / GPS over the network:** browsers only allow geolocation on HTTPS or `localhost`. Run
`.\start-frontend.ps1 -Https`, open `https://<your-PC-IP>:5173` on the phone and accept the self-signed certificate. The
dev server proxies `/api` to the backend on this PC, so the backend can stay on `127.0.0.1`. (Allow port 5173 through the
Windows firewall if the phone cannot connect.)

---

## What the KML actually contains

These numbers come from `data/processed/kml_analysis_report.md`, which is generated and contains no hand-entered figures.

| Item | Count |
|---|---|
| Placemarks | 2,209 in 9 folders |
| **Hubs** | **361** (unique Hub IDs, 0 duplicates, 0 invalid coordinates) |
| **Clusters** | **26** (all with boundary polygons; 0 unassigned hubs) |
| Hub status | 348 Live · 10 Not Live · 3 To be made live |
| Demand hotspots (PMF plus-code cells) | 1,773 |
| Competitor locations (Snabbit) | 9 |
| Screening records (personal names, excluded) | 25 |
| Service-line regions (South/East/North) | 3 |
| Drawn route lines / waypoints | 9 / 2 |
| Unclassified | 1 (`Point 28` in `Cluster_layer`) |

**XML repair.** The file is not well-formed: `xmlParseEntityRef: no name, line 102639`. The cause is an unescaped `&`
in the attribute `<Data name="Competiton OB Hotspots & remarks">`, repeated 361 times. Only those `&` characters were
escaped to `&amp;` (CDATA and comments untouched). All 2,211 `<coordinates>` blocks were compared byte-for-byte before and
after: none changed. The original is kept as `data/source/original_backup.kml`, which has an identical SHA-256.

**How hubs and clusters were identified.** Rules live in `backend/config/classification.json`:

- A placemark is a hub only if it has a `Hub ID` attribute (or both `Hub` and `Cluster`). All 361 come from the
  folder *IH Hyd – Competition Intelligence – Sheet44.csv*. Other folders are classified separately and never treated as
  hubs.
- **Hub locations are inferred (labelled as such everywhere).** Each hub is stored as a *service-area polygon*, with no hub
  point. The location used for search and routing is the polygon centroid (360 hubs), or an interior point where the
  centroid falls outside a concave polygon (1 hub).
- **Clusters** come from the explicit `Cluster` attribute. There are 34 raw spellings that collapse to 26 after
  case-insensitive normalisation, e.g. `Hitech_City`/`hitech_city`. These are matched to the 26 polygons in
  `Cluster_layer`, e.g. `Rajendranagar_cluster` = `Rajendra_Nagar`. A DBSCAN (haversine) fallback exists for KMLs without
  cluster data but is not needed here.

**Data-quality findings worth reviewing** (full lists are in the report and on the *Data Import* page):

- 9 hubs lie outside their own cluster's boundary polygon. `hyderabad_centroid_hub` is assigned to LB_Nagar but sits
  9.2 km away, inside Shaikpet.
- 3 isolated hubs: `provident_kenworth` is the only hub in Rajendra_Nagar; `anandbagh`; `hyderabad_centroid_hub`.
- In 29 hubs, the `New polygon` WKT attribute differs from the drawn polygon (up to ~950 m). The drawn polygon is used.
- 3 pairs of overlapping service areas, and 16 values with garbled encoding (e.g. hub `sangeetha_nagarã¢`, kept as-is,
  cleaned only in its display name).
- No hub type/category field exists, so `hub_type` is `null`. Not invented.

---

## Using the application

| Page | What it does |
|---|---|
| **Dashboard** | KPI cards (hubs, clusters, valid locations, unassigned, selected cluster, nearest-hub distance), network map, quick nearest-hub search, hubs-per-cluster chart, cluster table |
| **Live Map** | All layers with multi-cluster filters, hub search, base maps (light / streets / satellite), optional overlays (service areas, demand hotspots, competitors, service lines) |
| **Find Nearest Hub** | Coordinates, map click or GPS (one-shot or live tracking) → nearest eligible hub by road, route, directions, top 5 alternatives with route comparison |
| **Cluster Analysis** | Hubs per cluster, geographic distribution, coverage areas, cluster detail with zoom-to-extent, attribute breakdowns, missing-data indicators |
| **Hub Directory** | Searchable, sortable, filterable table of all hubs with a details drawer showing every KML attribute |
| **Route History** | Saved searches in SQLite; open, delete, clear all |
| **Data Import** | Upload KML/KMZ (analyse or activate), XML repair summary, full data-quality dashboard, classification rules |
| **Export to Google Earth** | The five KML files, CSV/GeoJSON reports, and the Google Earth Web import guide |
| **Settings** | Routing provider (with live connection test), travel mode, ranking, radius, candidate limits, privacy defaults |

---

## How the nearest hub is chosen

1. **Cluster detection.** Is the point inside a cluster boundary? If not, inside a hub's service area? If neither, it
   is *outside coverage*: the fallback searches all clusters and the UI says so explicitly. A specific cluster or "all
   clusters" can also be chosen.
2. **Eligible hubs.** Hubs in scope, optionally excluding inactive ones using the KML `Hub status` attribute.
3. **Haversine pre-filter.** Drops hubs beyond the search radius. Straight-line distance is never shown as road distance.
4. **Road evaluation** via the provider's matrix endpoint:
   - **Exhaustive** when there are ≤ 50 candidates. Every cluster in this dataset qualifies (largest: 28 hubs), so
     auto-detected searches always check every hub by road.
   - **Progressive with proof** for larger scopes. Candidates are evaluated in straight-line order. A road route cannot be
     shorter than the great-circle distance between its road-snapped ends, so once the next candidate's lower bound
     exceeds the current 5th-best road distance, no remaining hub can rank higher.
   - If the candidate cap is hit first, the result is labelled **"not guaranteed"**.
5. **Ranking** by road distance (default) or road travel time. Hubs with no route, or more than 1 km from any road, are
   listed as unreachable.
6. **Route.** Full geometry from the provider (35 points for a 0.9 km route, hundreds for longer ones), turn-by-turn
   steps, alternative routes, and an *Open in Google Maps* link.

*Road distance* means the length of the routing engine's recommended route. If routing fails, the app shows an error.
It never draws or exports a straight line as a route. Where the search point is off-road (e.g. inside a park), a thin
dotted connector shows the gap to the nearest road, labelled as not part of the road distance.

---

## Routing providers

| Provider | Key | Modes | Notes |
|---|---|---|---|
| **OSRM** (default without a key) | none | driving, cycling, walking | Public OpenStreetMap demo servers: fair use, no SLA. For production, self-host OSRM and set `OSRM_DRIVING_URL`. |
| **Google Routes API** | `GOOGLE_MAPS_API_KEY` | driving, two-wheeler, cycling, walking | Traffic-aware times; two-wheeler mode suits India. Enable *Routes API* and billing in Google Cloud. |
| **OpenRouteService** | `ORS_API_KEY` | driving, cycling, walking | Free tier available. |

`ROUTING_PROVIDER=auto` uses Google when its key is set, otherwise OSRM. Keys are only read on the server, from
`backend/.env`, and never reach the browser. **Settings → Test live routing** checks the active provider with a real
request.

---

## Google Earth Web

Google Earth Web (https://earth.google.com/web/) displays KML. It cannot run this app's search, GPS or routing, and it
does not sync with the app. The workflow is export → import:

1. Run a search in the app, then go to **Export to Google Earth** (or use the *Export route KML* button on the result).
2. Download `company_demo.kml` (everything) or a specific file.
3. In Earth Web: **Projects → New project → Import KML file from computer** (if prompted, enable *KML file import*
   under Settings). Choose the file.
4. Earth flies to the data. Folders are organised per cluster; click a hub for its ID, cluster, coordinates and metadata.

| File | Contents |
|---|---|
| `all_hubs.kml` | 361 hubs in one folder per cluster, cluster-coloured, with balloons and ExtendedData; service areas (hidden by default) |
| `all_clusters.kml` | 26 coloured boundary polygons, labelled centres with hub counts, hubs per cluster |
| `selected_cluster.kml` | One cluster: boundary, centre, hubs, service areas |
| `nearest_hub_route.kml` | Search location, nearest hub, the full road route LineString (`tessellate`, `clampToGround`), alternatives, unreachable hubs |
| `company_demo.kml` | The whole network plus the latest search and route, and the service-line regions |

Pre-generated copies (from a real OSRM search at 17.4849, 78.4138) are in **`exports/`**. Regenerate them with
`backend\.venv\Scripts\python -m scripts.generate_exports --lat <lat> --lng <lng>`, or with the *Write all 5 files*
button. All exports validate against the **official OGC KML 2.2 XML Schema** (`python -m scripts.validate_kml <files>`).

---

## API

Interactive docs: **http://127.0.0.1:8000/docs**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, dataset counts, routing provider status |
| GET | `/api/hubs` | Hubs. Filters: `q`, `cluster_id`, `status`, `active`, `region`, `has_issues`; paging |
| GET | `/api/hubs/{hub_id}` | One hub |
| GET | `/api/clusters` | Clusters with boundaries and statistics |
| GET | `/api/clusters/{cluster_id}` | Cluster and its hubs |
| GET | `/api/clusters/{cluster_id}/hubs` | Hubs of a cluster |
| POST | `/api/nearest-hub` | Nearest hub by road: ranking, route, evaluation details |
| POST | `/api/route` | Road route from a point to any hub (alternatives) |
| GET | `/api/locate?lat=&lng=` | Cluster detection only |
| POST | `/api/import-kml` | Upload KML/KMZ (`activate=false` previews only) |
| GET | `/api/analytics/overview` | Dashboard analytics |
| GET | `/api/data-quality` · `/api/report` | Quality findings · markdown analysis report |
| GET | `/api/export/kml?type=all_hubs\|all_clusters\|selected_cluster\|route\|company_demo\|cleaned` | KML downloads |
| GET | `/api/export/csv?type=hubs\|clusters\|search` | CSV reports |
| GET | `/api/export/geojson?type=hubs\|clusters\|service_areas\|route` | GeoJSON |
| GET/PUT/DELETE | `/api/settings` | Preferences |
| GET/DELETE | `/api/history`, `/api/history/{id}` | Route history |
| GET / POST | `/api/routing/status` · `/api/routing/test` | Provider status · live test |

---

## Project layout

```
Akhil Copy.kml                 original source (never modified)
data/source/original_backup.kml  byte-identical backup
data/processed/                hubs.json, hubs.geojson, clusters.json, cleaned_hubs.kml, repaired_full.kml,
                               kml_analysis_report.md, analysis.json, layers/*.geojson
exports/                       the five Google Earth KML files
backend/
  app/main.py                  FastAPI app, error handling, lifespan
  app/api/                     routes_data, routes_search, routes_export, routes_admin
  app/services/                kml_repair, kml_parser, hub_classifier, cluster_service, pipeline, report_service,
                               routing_service, nearest_hub_service, location_service, export_service, data_store
  app/models.py, database.py   Pydantic schemas, SQLite (history + preferences)
  config/classification.json   configurable hub/cluster classification rules
  scripts/                     process_kml, generate_exports, validate_kml
  tests/                       pytest suite (data, geo, routing, API, KML schema)
frontend/src/                  pages/, components/ (layout, map, search, results, analytics, ui), context/, hooks/
e2e/ui_checks.py               Playwright browser checks
docs/DEMO_GUIDE.md             live demonstration script
```

---

## Testing

```powershell
cd backend;  .venv\Scripts\python -m pytest            # 76 tests: real KML, mock + live OSRM, API, OGC schema
cd frontend; npm test                                   # coordinate validation & formatting
# browser end-to-end (backend + frontend running; uses installed Microsoft Edge):
backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python e2e\ui_checks.py
```

Tests marked `live` call the real OSRM server and skip automatically when offline (`SKIP_LIVE=1` forces a skip). The
browser suite covers search, alternatives, reload persistence, validation, GPS granted/denied, live tracking, map
picking, outside-coverage fallback, every page, the mobile layout, and KML downloads.

---

## Privacy

- GPS locations are used for the search only. They are saved to route history **only** when the user ticks the consent
  box (default off). Coordinate searches are saved by default; both defaults can be changed in Settings.
- History lives in `data/app.db`, with per-record delete and *Clear all*. Server logs record request paths only, never
  coordinates.
- The routing provider receives the coordinates needed to compute the route.
- The 25 screening records with personal names are excluded from all maps and exports.

## Limitations

- Hub coordinates are inferred from service-area polygons; the KML has no explicit hub points.
- Public OSRM servers are rate-limited, best-effort, and have no live traffic. Use Google (with a key) or self-hosted
  OSRM for production; two-wheeler routing needs Google.
- Google Earth Web import is manual (no supported API for pushing KML into a user's Earth Web session). KML exports were
  validated against the OGC schema; the in-browser import itself must be confirmed by hand.
- Base map tiles come from Esri and OpenStreetMap public tile services, which require attribution (shown on the map) and
  fair use.
