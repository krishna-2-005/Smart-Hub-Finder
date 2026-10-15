import L, { type LatLngBoundsExpression, type PathOptions } from "leaflet";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  Pane,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { api } from "../../api/client";
import type { Cluster, FeatureCollection, Hub, NearestHubResult, RankedHub, Route } from "../../api/types";
import { fmtCoord, fmtKm, fmtMinutes, locationMethodLabel } from "../../lib/format";
import { DEFAULT_LAYERS, LayerPanel, type BaseLayer, type LayerState } from "./LayerPanel";
import { MapLegend } from "./MapLegend";
import {
  clusterCenterIcon,
  nearestHubIcon,
  pickIcon,
  rankIcon,
  selectedHubIcon,
  unreachableIcon,
  userIcon,
} from "./mapIcons";

const HYDERABAD: [number, number] = [17.43, 78.43];

// Keyless tile services. (CARTO basemaps now require an API key, so they are not used.)
const TILES: Record<BaseLayer, { url: string; attribution: string; maxNativeZoom: number; labels?: string }> = {
  light: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labels: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors, and the GIS user community",
    maxNativeZoom: 16,
  },
  streets: {
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxNativeZoom: 19,
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: "Tiles &copy; Esri &mdash; Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    maxNativeZoom: 18,
  },
};

// Module-level cache so lazily loaded overlay layers are fetched once per session.
const layerCache = new Map<string, Promise<FeatureCollection>>();
function useLayer(name: string, enabled: boolean) {
  const [data, setData] = useState<FeatureCollection | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    if (!layerCache.has(name)) layerCache.set(name, api.layer(name));
    layerCache
      .get(name)!
      .then((d) => alive && setData(d))
      .catch(() => layerCache.delete(name));
    return () => {
      alive = false;
    };
  }, [name, enabled]);
  return enabled ? data : null;
}

export interface FitTarget {
  key: string;
  bounds: LatLngBoundsExpression;
  maxZoom?: number;
}

function FitController({ target }: { target: FitTarget | null | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (!target) return;
    map.fitBounds(target.bounds, { padding: [40, 40], maxZoom: target.maxZoom ?? 16, animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target?.key]);
  return null;
}

function ZoomWatcher({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({
    zoomend() {
      onZoom(map.getZoom());
    },
  });
  useEffect(() => onZoom(map.getZoom()), [map, onZoom]);
  return null;
}

function ClickHandler({ onClick }: { onClick?: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onClick?.(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function InvalidateOnResize() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [map]);
  return null;
}

export function bboxToBounds(b: [number, number, number, number] | null | undefined): LatLngBoundsExpression | null {
  if (!b) return null;
  return [
    [b[0], b[1]],
    [b[2], b[3]],
  ];
}

export interface SearchOverlay {
  origin: { lat: number; lng: number } | null;
  result: NearestHubResult | null;
  selectedHubId: string | null;
  route: Route | null;
  tracking?: boolean;
}

interface Props {
  clusters: Cluster[];
  hubs: Hub[];
  className?: string;
  visibleClusterIds?: Set<string> | null;
  highlightClusterId?: string | null;
  fitTarget?: FitTarget | null;
  search?: SearchOverlay | null;
  onHubAction?: (hub: Hub) => void;
  hubActionLabel?: string;
  onClusterClick?: (clusterId: string) => void;
  onMapClick?: (lat: number, lng: number) => void;
  pickedPoint?: { lat: number; lng: number } | null;
  initialLayers?: Partial<LayerState>;
  showLegend?: boolean;
  children?: ReactNode;
}

export function InteractiveMap({
  clusters,
  hubs,
  className,
  visibleClusterIds,
  highlightClusterId,
  fitTarget,
  search,
  onHubAction,
  hubActionLabel = "Route to this hub",
  onClusterClick,
  onMapClick,
  pickedPoint,
  initialLayers,
  showLegend = true,
  children,
}: Props) {
  const [layers, setLayers] = useState<LayerState>({ ...DEFAULT_LAYERS, ...initialLayers });
  const [zoom, setZoom] = useState(11);
  const clusterColor = useMemo(() => Object.fromEntries(clusters.map((c) => [c.cluster_id, c.color])), [clusters]);
  const visible = (cid: string | null) => !visibleClusterIds || (cid !== null && visibleClusterIds.has(cid));

  const serviceAreas = useLayer("hub_service_areas", layers.serviceAreas);
  const regions = useLayer("regions", layers.regions);
  const demand = useLayer("demand_points", layers.demand);
  const competitors = useLayer("competitor_locations", layers.competitors);

  const result = search?.result ?? null;
  const routeActive = Boolean(search?.route);
  const rankedIds = useMemo(() => new Set((result?.ranking ?? []).map((r) => r.hub_id)), [result]);
  const unreachableIds = useMemo(() => new Set((result?.unreachable ?? []).map((r) => r.hub_id)), [result]);
  const dimOthers = routeActive || Boolean(highlightClusterId);

  const clusterStyle = (c: Cluster): PathOptions => {
    const focused = highlightClusterId ? c.cluster_id === highlightClusterId : true;
    return {
      color: c.color,
      weight: focused && highlightClusterId ? 3 : 1.5,
      opacity: focused ? 0.9 : 0.35,
      fillColor: c.color,
      fillOpacity: routeActive ? 0.06 : focused ? (highlightClusterId ? 0.16 : 0.12) : 0.04,
    };
  };

  const hubPopup = (h: Hub, extra?: ReactNode) => (
    <Popup>
      <div className="min-w-[210px] space-y-1">
        <p className="text-sm font-semibold text-ink">{h.display_name}</p>
        <p className="text-[11px] text-slate-500">ID {h.hub_id}</p>
        {extra}
        <table className="mt-1 w-full text-[12px]">
          <tbody>
            <tr><td className="pr-2 text-slate-500">Cluster</td><td className="font-medium">{h.cluster_name ?? "Unassigned"}</td></tr>
            <tr><td className="pr-2 text-slate-500">Status</td><td className="font-medium">{h.status ?? "Unknown"}</td></tr>
            <tr><td className="pr-2 text-slate-500">Region</td><td>{h.region ?? "—"}</td></tr>
            <tr><td className="pr-2 text-slate-500">Lat, Lng</td><td className="tabular">{fmtCoord(h.latitude, 5)}, {fmtCoord(h.longitude, 5)}</td></tr>
            <tr><td className="pr-2 text-slate-500">Location</td><td>{locationMethodLabel[h.location_method ?? ""] ?? h.location_method}</td></tr>
          </tbody>
        </table>
        {onHubAction && (
          <button
            type="button"
            onClick={() => onHubAction(h)}
            className="mt-2 w-full rounded-md bg-brand-700 px-2 py-1.5 text-xs font-semibold text-white hover:bg-brand-800"
          >
            {hubActionLabel}
          </button>
        )}
      </div>
    </Popup>
  );

  const rankedPopup = (r: RankedHub, isNearest: boolean) => (
    <Popup>
      <div className="min-w-[200px] space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">{isNearest ? "Nearest hub" : `Rank #${r.rank}`}</p>
        <p className="text-sm font-semibold text-ink">{r.display_name}</p>
        <p className="text-[11px] text-slate-500">{r.cluster_name} · ID {r.hub_id}</p>
        <p className="text-[13px]">
          <b>{fmtKm(r.road_distance_km)}</b> by road · <b>{fmtMinutes(r.duration_min)}</b>
        </p>
        {onHubAction && search?.selectedHubId !== r.hub_id && (
          <button
            type="button"
            onClick={() => {
              const h = hubs.find((x) => x.hub_id === r.hub_id);
              if (h) onHubAction(h);
            }}
            className="mt-1 w-full rounded-md bg-brand-700 px-2 py-1.5 text-xs font-semibold text-white hover:bg-brand-800"
          >
            Show road route
          </button>
        )}
      </div>
    </Popup>
  );

  const tile = TILES[layers.base];

  return (
    <div className={`relative isolate overflow-hidden ${className ?? ""}`}>
      <MapContainer center={HYDERABAD} zoom={11} maxZoom={19} zoomSnap={0.25} zoomDelta={0.5} preferCanvas zoomControl={false} className="h-full w-full" scrollWheelZoom>
        <TileLayer key={layers.base} url={tile.url} attribution={tile.attribution} maxNativeZoom={tile.maxNativeZoom} maxZoom={19} />
        {tile.labels && <TileLayer key={`${layers.base}-labels`} url={tile.labels} maxNativeZoom={tile.maxNativeZoom} maxZoom={19} />}
        <ZoomControl position="bottomright" />
        <InvalidateOnResize />
        <ZoomWatcher onZoom={setZoom} />
        <FitController target={fitTarget} />
        {onMapClick && <ClickHandler onClick={onMapClick} />}

        <Pane name="areas" style={{ zIndex: 380 }}>
          {layers.regions &&
            regions?.features.map((f) => (
              <GeoJSON
                key={`region-${f.id}`}
                data={f as unknown as GeoJSON.Feature}
                interactive={false}
                style={{ color: String(f.properties.color ?? "#475569"), weight: 3, dashArray: "8 6", fillOpacity: 0.02 }}
              />
            ))}
          {layers.clusters &&
            clusters
              .filter((c) => c.boundary && visible(c.cluster_id))
              .map((c) => (
                <GeoJSON
                  key={`cl-${c.cluster_id}-${highlightClusterId ?? ""}-${routeActive}`}
                  data={{ type: "Feature", geometry: c.boundary, properties: {} } as unknown as GeoJSON.Feature}
                  style={clusterStyle(c)}
                  interactive={!onMapClick}
                  eventHandlers={onClusterClick ? { click: () => onClusterClick(c.cluster_id) } : undefined}
                >
                  {!onMapClick && (
                    <Tooltip sticky>
                      <b>{c.display_name}</b> · {c.hub_count} hubs
                    </Tooltip>
                  )}
                </GeoJSON>
              ))}
          {layers.serviceAreas &&
            serviceAreas?.features
              .filter((f) => visible((f.properties.cluster_id as string) ?? null))
              .map((f) => (
                <GeoJSON
                  key={`sa-${f.id}`}
                  data={f as unknown as GeoJSON.Feature}
                  interactive={false}
                  style={{ color: String(f.properties.color), weight: 1, opacity: 0.7, fillOpacity: 0.08 }}
                />
              ))}
        </Pane>

        {layers.demand &&
          demand?.features.map((f, i) => {
            const [lng, lat] = f.geometry.coordinates as [number, number];
            const dels = Number(f.properties.deliveries ?? 0);
            return (
              <CircleMarker
                key={`d${i}`}
                center={[lat, lng]}
                radius={Math.max(2, Math.min(7, Math.sqrt(dels) / 12))}
                pathOptions={{ color: "#b45309", weight: 0.5, fillColor: "#d97706", fillOpacity: 0.45 }}
              >
                <Popup>
                  <p className="font-semibold">Demand hotspot {String(f.properties.plus_code ?? "")}</p>
                  <p>Deliveries: {dels.toLocaleString("en-IN")} · Users: {String(f.properties.users ?? "—")}</p>
                  <p>{String(f.properties.bucket ?? "")}</p>
                  {f.properties.insta_hub ? <p className="text-slate-500">Mapped hub: {String(f.properties.insta_hub)}</p> : null}
                </Popup>
              </CircleMarker>
            );
          })}

        {layers.competitors &&
          competitors?.features.map((f, i) => {
            const [lng, lat] = f.geometry.coordinates as [number, number];
            return (
              <CircleMarker key={`c${i}`} center={[lat, lng]} radius={7} pathOptions={{ color: "#fff", weight: 2, fillColor: "#be123c", fillOpacity: 1 }}>
                <Popup>
                  <p className="font-semibold">Competitor location: {String(f.properties.name)}</p>
                  <p className="text-slate-500">Snabbit live plus code {String(f.properties.plus_code ?? "")}</p>
                </Popup>
              </CircleMarker>
            );
          })}

        {layers.hubs &&
          hubs
            .filter((h) => h.latitude !== null && visible(h.cluster_id))
            .filter((h) => !rankedIds.has(h.hub_id) && !unreachableIds.has(h.hub_id))
            .map((h) => {
              const color = clusterColor[h.cluster_id ?? ""] ?? "#64748b";
              const faded = dimOthers && (highlightClusterId ? h.cluster_id !== highlightClusterId : true);
              const inactive = h.is_active === false;
              return (
                <CircleMarker
                  key={h.hub_id ?? `${h.latitude},${h.longitude}`}
                  center={[h.latitude as number, h.longitude as number]}
                  radius={routeActive ? 4 : 5.5}
                  pathOptions={{
                    color: inactive ? color : "#ffffff",
                    weight: inactive ? 2 : 1.5,
                    fillColor: inactive ? "#ffffff" : color,
                    fillOpacity: faded ? 0.35 : 0.95,
                    opacity: faded ? 0.5 : 1,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -4]}>
                    {h.display_name}
                    {inactive ? ` (${h.status})` : ""}
                  </Tooltip>
                  {hubPopup(h)}
                </CircleMarker>
              );
            })}

        {layers.centers &&
          clusters
            .filter((c) => c.center_lat !== null && visible(c.cluster_id))
            .map((c) => (
              <Marker key={`ctr-${c.cluster_id}`} position={[c.center_lat as number, c.center_lng as number]} icon={clusterCenterIcon(c.color)}>
                <Tooltip direction="top" offset={[0, -8]}>
                  {c.display_name} center · {c.hub_count} hubs
                </Tooltip>
              </Marker>
            ))}

        {layers.labels &&
          clusters
            // Labels overlap at city scale: show them from zoom 12, or only for the focused cluster.
            .filter((c) => c.center_lat !== null && visible(c.cluster_id) && (zoom >= 12 || c.cluster_id === highlightClusterId))
            .map((c) => (
              <Marker key={`lbl-${c.cluster_id}`} position={[c.center_lat as number, c.center_lng as number]} icon={L.divIcon({ className: "", html: "", iconSize: [0, 0] })} interactive={false}>
                <Tooltip permanent direction="center" className="cluster-label">
                  {c.display_name} ({c.hub_count})
                </Tooltip>
              </Marker>
            ))}

        {/* ---- search result layers ---- */}
        {search?.route && (
          <>
            {search.route.alternatives.map((a, i) => (
              <Polyline key={`alt-${i}`} positions={a.geometry} pathOptions={{ color: "#475569", weight: 4, opacity: 0.75, dashArray: "6 7" }}>
                <Tooltip sticky>
                  Alternative road route: {fmtKm(a.distance_km)} · {fmtMinutes(a.duration_min)}
                </Tooltip>
              </Polyline>
            ))}
            {/* Off-road connectors: the routing engine measures from the nearest road point. These
                dotted hints show that gap; they are not part of the road distance. */}
            {search.origin && (search.route.origin_snap_m ?? 0) > 15 && search.route.geometry.length > 0 && (
              <Polyline
                positions={[[search.origin.lat, search.origin.lng], search.route.geometry[0]]}
                pathOptions={{ color: "#64748b", weight: 2.5, dashArray: "2 6", lineCap: "round" }}
              >
                <Tooltip sticky>
                  {Math.round(search.route.origin_snap_m ?? 0)} m to the nearest road (not included in the road distance)
                </Tooltip>
              </Polyline>
            )}
            {(search.route.destination_snap_m ?? 0) > 15 && search.route.geometry.length > 0 && (() => {
              const hub = result?.ranking.find((r) => r.hub_id === search.selectedHubId) ?? hubs.find((h) => h.hub_id === search.selectedHubId);
              if (!hub || hub.latitude === null || hub.longitude === null) return null;
              return (
                <Polyline
                  positions={[search.route.geometry[search.route.geometry.length - 1], [hub.latitude, hub.longitude]]}
                  pathOptions={{ color: "#64748b", weight: 2.5, dashArray: "2 6", lineCap: "round" }}
                >
                  <Tooltip sticky>
                    {Math.round(search.route.destination_snap_m ?? 0)} m from the road to the hub point (not included in the road distance)
                  </Tooltip>
                </Polyline>
              );
            })()}
            <Polyline positions={search.route.geometry} pathOptions={{ color: "#0f172a", weight: 11, opacity: 0.55, lineCap: "round", lineJoin: "round" }} interactive={false} />
            <Polyline positions={search.route.geometry} pathOptions={{ color: "#ffffff", weight: 8.5, opacity: 1, lineCap: "round", lineJoin: "round" }} interactive={false} />
            <Polyline positions={search.route.geometry} pathOptions={{ color: "#1a73e8", weight: 5.5, opacity: 1, lineCap: "round", lineJoin: "round" }}>
              <Tooltip sticky>
                Road route ({search.route.provider_label}): {fmtKm(search.route.distance_km)} · {fmtMinutes(search.route.duration_min)}
              </Tooltip>
            </Polyline>
          </>
        )}

        {result?.unreachable.map((u) => (
          <Marker key={`un-${u.hub_id}`} position={[u.latitude, u.longitude]} icon={unreachableIcon}>
            <Popup>
              <p className="font-semibold">{u.display_name}</p>
              <p className="text-red-700">Unreachable: {u.reason}</p>
            </Popup>
          </Marker>
        ))}

        {result?.ranking.map((r) => {
          const isNearest = r.rank === 1;
          const isSelected = search?.selectedHubId === r.hub_id;
          const icon = isNearest ? nearestHubIcon : isSelected ? selectedHubIcon : rankIcon(r.rank ?? 0);
          return (
            <Marker key={`rk-${r.hub_id}`} position={[r.latitude, r.longitude]} icon={icon} zIndexOffset={isNearest ? 900 : isSelected ? 800 : 500}>
              <Tooltip direction="top" offset={[0, isNearest || isSelected ? -36 : -12]}>
                #{r.rank} {r.display_name} · {fmtKm(r.road_distance_km)}
              </Tooltip>
              {rankedPopup(r, isNearest)}
            </Marker>
          );
        })}

        {search?.origin && (
          <Marker position={[search.origin.lat, search.origin.lng]} icon={userIcon(search.tracking)} zIndexOffset={1000}>
            <Tooltip direction="top" offset={[0, -10]}>
              {search.tracking ? "Your live location" : "Search location"} ({fmtCoord(search.origin.lat, 5)}, {fmtCoord(search.origin.lng, 5)})
            </Tooltip>
          </Marker>
        )}

        {pickedPoint && (!search?.origin || pickedPoint.lat !== search.origin.lat || pickedPoint.lng !== search.origin.lng) && (
          <Marker position={[pickedPoint.lat, pickedPoint.lng]} icon={pickIcon}>
            <Tooltip permanent direction="top" offset={[0, -8]}>
              Selected point – press “Find nearest hub”
            </Tooltip>
          </Marker>
        )}
        {children}
      </MapContainer>
      <LayerPanel value={layers} onChange={setLayers} />
      {showLegend && <MapLegend showSearch={Boolean(result)} />}
    </div>
  );
}
