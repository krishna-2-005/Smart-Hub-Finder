# Company Demonstration Guide

A 15-minute live walkthrough of the Smart Hub Location & Routing System. Numbers quoted below come from real runs of
the app against `Akhil Copy.kml` with OSRM routing. Live road distances can shift slightly if OpenStreetMap data
changes.

---

## Before the meeting (10 minutes)

1. Start both servers (two terminals) from the project folder:
   ```powershell
   .\start-backend.ps1
   .\start-frontend.ps1
   ```
2. Open **http://localhost:5173**. The top bar should show a green **Routing: OSRM** pill (or *Google Maps Routes API*
   if a key is configured).
3. **Settings → Test live routing** must report *OK* with a road point count. If it fails, check the internet
   connection; the app will never fake a route.
4. In a second browser tab, open **https://earth.google.com/web/** (Chrome or Edge). Keep it ready.
5. Optional backup: the five KML files are already in the `exports/` folder in case the network is slow during the
   meeting.
6. For the GPS scenario on a laptop, either allow the browser's location prompt, or simulate a location:
   Chrome/Edge DevTools → ⋮ → *More tools → Sensors* → Location → custom **17.4849, 78.4138**.

---

## Scenario 1 – Cluster overview (Dashboard)

**Show:** open **Dashboard**.

- KPI cards: **361 hubs** (348 live, 13 inactive), **26 clusters**, **361 valid locations**, **0 unassigned hubs**.
- Map: 26 colour-coded cluster boundaries with every hub. Click a cluster to focus it.
- *Hubs per cluster* chart: Kondapur is the largest (28), Rajendra Nagar the smallest (1). Orange segments are hubs not
  yet live. Clicking a bar selects the cluster, and the *Selected cluster* card updates.

**Talking point:** "The KML was malformed (an unescaped `&` on line 102,639, repeated 361 times). We repaired only that
character, proved all 2,211 coordinate blocks are unchanged, and kept the original as a backup."

## Scenario 2 – Coordinate search with real road distance (Find Nearest Hub)

**Do:** open **Find Nearest Hub**, paste `17.47418, 78.28887` into the Latitude box (both boxes fill), then press
**Find nearest hub**.

**Expected:**
- *Inside the Nallagandla cluster boundary*. All 20 live Nallagandla hubs are evaluated by road (exhaustive, guaranteed).
- Nearest hub: **Fortune Greenhomes – 1.72 km by road, ~3 min**.
- The blue road route follows the streets (60 geometry points), with turn-by-turn directions below.

**Talking point (the key message):** look at **#5 Mig Phase2**. It is the closest hub as the crow flies (**0.56 km**),
but **2.77 km by road**. A straight-line tool would send the user to the wrong hub; this system ranks by the actual road
network.

Also show **Navigate in Google Maps** (opens turn-by-turn navigation on a phone) and the **Guaranteed nearest** badge,
which explains how many hubs were checked.

## Scenario 3 – Live GPS location

**Do:** press **Use my current location** and accept the browser permission prompt.

**Expected:** coordinates fill in automatically and the nearest hub and route appear. With the simulated location
17.4849, 78.4138: **Kukatpally Lake – 0.91 km, ~2 min** (Kukatpally cluster).

**Talking points:**
- The location is used for this search only. It is stored in route history only if the user ticks the consent box.
- **Track** follows the user and re-runs the search after they move 150 m. The green banner shows tracking is on, and
  **Stop** ends it.
- If permission is denied, GPS is unavailable or it times out, the app explains why and the manual form keeps working.

## Scenario 4 – Alternative hubs

**Show:** the *Top 5 reachable hubs* list under the result.

- Each card shows road distance, travel time and comparison bars. The straight-line distance is shown small and labelled
  *pre-filter only*.
- Click **#3**: its road route is calculated and drawn (orange pin), with new directions. **Selected route KML** exports
  that alternative.
- Any hub on the map can be clicked → *Show road route from search location*.

## Scenario 5 – Google Earth Web

**Do:** on the result press **Export route KML** (or go to **Export to Google Earth** → `company_demo.kml`).

In the Google Earth Web tab: **Projects → New project → Import KML file from computer** → choose the downloaded file.
(If Earth asks, enable *KML file import* in its Settings.)

**Show:** Earth flies to the search area. Folders: *Nearest hub search* (your location, nearest hub, the road route as
an orange line, alternatives) and *Hub network (by cluster)*. Click any hub for its ID, cluster, coordinates and
attributes.

**Talking point:** Earth Web is the visualisation layer. Searching, GPS and routing happen in our app, and results move
to Earth through standard KML. Every export validates against the official OGC KML 2.2 schema.

## Scenario 6 – Cluster analytics

**Show:** **Cluster Analysis**.

- Choose *Kondapur* in the map selector: the map zooms to its extent and shows 28 hubs, ~20.3 km² boundary area,
  ~10.2 km² hub service-area coverage, and mean hub spacing.
- The cluster summary table is sortable by hubs, area, density, coverage and spread.
- Breakdowns by service line (South 139 / North 122 / East 100), competitive vs non-competitive, operational status.
- *Missing-data indicators*: every core field is complete; *Hub type* is 0% because the KML has no such field, and the
  app does not invent one.

**Optional, Data Import page:** the data-quality findings worth raising with the data owners:
9 hubs lie outside their own cluster boundary (e.g. `hyderabad_centroid_hub` is assigned to LB Nagar but is 9.2 km away
inside Shaikpet), 3 isolated hubs, 29 hubs whose *New polygon* attribute disagrees with the drawn polygon.

---

## Extra: outside coverage

Search **17.2403, 78.4294** (near the airport, outside every cluster). The app says *Outside all cluster boundaries*,
switches to an all-cluster fallback, and finds **Provident Kenworth (Rajendra Nagar) – 15.1 km, ~20 min by road**,
using a 333-point route.

## If something goes wrong

| Symptom | Fix |
|---|---|
| Red "Data could not be loaded" banner | The backend isn't running. Start `.\start-backend.ps1`, then press Refresh. |
| "Road routing unavailable" | No internet, or the public OSRM server is busy. Retry, or configure a Google/ORS key in `backend/.env`. The app shows straight-line candidates only as a clearly labelled pre-filter. |
| GPS button shows "permission denied" | Allow location for `localhost` in the browser's site settings, or use DevTools → Sensors. |
| Two-wheeler mode is greyed out | Only the Google Routes API supports it; add `GOOGLE_MAPS_API_KEY`. |
| Earth Web import option missing | Use the Projects panel (left menu). The UI can differ by account/region; the KML files can also be opened in Google Earth Pro. |
