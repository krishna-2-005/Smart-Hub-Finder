import L from "leaflet";

export const userIcon = (tracking = false) =>
  L.divIcon({
    className: "",
    html: `<div class="mk-user${tracking ? " tracking" : ""}"><span class="halo"></span><span class="dot"></span></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });

export const nearestHubIcon = L.divIcon({
  className: "",
  html: `<svg width="34" height="44" viewBox="0 0 34 44" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M17 1C8.2 1 1 8 1 16.7 1 28.4 17 43 17 43s16-14.6 16-26.3C33 8 25.8 1 17 1Z" fill="#15803d" stroke="#fff" stroke-width="2"/>
    <path d="m17 8.6 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.6-4.8 2.6.9-5.4-3.9-3.8 5.4-.8Z" fill="#fff"/>
  </svg>`,
  iconSize: [34, 44],
  iconAnchor: [17, 43],
  popupAnchor: [0, -38],
});

export const selectedHubIcon = L.divIcon({
  className: "",
  html: `<svg width="30" height="40" viewBox="0 0 34 44" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M17 1C8.2 1 1 8 1 16.7 1 28.4 17 43 17 43s16-14.6 16-26.3C33 8 25.8 1 17 1Z" fill="#c2410c" stroke="#fff" stroke-width="2"/>
    <circle cx="17" cy="16" r="5.5" fill="#fff"/>
  </svg>`,
  iconSize: [30, 40],
  iconAnchor: [15, 39],
  popupAnchor: [0, -34],
});

export const rankIcon = (rank: number, selected = false) =>
  L.divIcon({
    className: "",
    html: `<div class="mk-rank${selected ? " selected" : ""}">${rank}</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });

export const clusterCenterIcon = (color: string) =>
  L.divIcon({
    className: "",
    html: `<div class="mk-center" style="background:${color}"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });

export const unreachableIcon = L.divIcon({
  className: "",
  html: `<div class="mk-unreachable" title="Unreachable by road">×</div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

export const pickIcon = L.divIcon({
  className: "",
  html: `<div class="mk-pick"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});
