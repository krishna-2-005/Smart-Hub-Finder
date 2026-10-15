"""In-memory view of the processed dataset with spatial indexes.

Loaded from ``data/processed`` at startup and reloaded after a KML import.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

log = logging.getLogger(__name__)

LAYER_NAMES = (
    "cluster_boundaries", "hub_service_areas", "regions", "demand_points",
    "competitor_locations", "source_route_lines",
)


class DatasetNotReady(RuntimeError):
    pass


class DataStore:
    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir
        self._lock = threading.RLock()
        self.ready = False
        self.error: str | None = None
        self.hubs: list[dict[str, Any]] = []
        self.hubs_by_id: dict[str, dict[str, Any]] = {}
        self.clusters: list[dict[str, Any]] = []
        self.clusters_by_id: dict[str, dict[str, Any]] = {}
        self.analysis: dict[str, Any] = {}
        self.layers: dict[str, dict[str, Any]] = {}
        self.service_areas: dict[str, dict[str, Any]] = {}
        self.loaded_at: str | None = None
        self.cluster_shapes: list[tuple[str, BaseGeometry]] = []
        self.cluster_tree: STRtree | None = None
        self.service_area_shapes: list[tuple[str, BaseGeometry]] = []
        self.service_area_tree: STRtree | None = None

    def _read(self, name: str) -> Any:
        with open(self.processed_dir / name, encoding="utf-8") as fh:
            return json.load(fh)

    def load(self) -> None:
        with self._lock:
            try:
                hubs = self._read("hubs.json")["hubs"]
                clusters = self._read("clusters.json")["clusters"]
                analysis = self._read("analysis.json")
                layers = {}
                for name in LAYER_NAMES:
                    p = self.processed_dir / "layers" / f"{name}.geojson"
                    layers[name] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
                        "type": "FeatureCollection", "features": []}
            except FileNotFoundError as exc:
                self.ready = False
                self.error = f"Processed dataset not found ({exc.filename}). Run the KML processing step."
                log.warning(self.error)
                return

            self.hubs = hubs
            self.hubs_by_id = {h["hub_id"]: h for h in hubs if h.get("hub_id")}
            self.clusters = clusters
            self.clusters_by_id = {c["cluster_id"]: c for c in clusters}
            self.analysis = analysis
            self.layers = layers
            self.service_areas = {
                f["id"]: f["geometry"] for f in layers["hub_service_areas"]["features"] if f.get("id")
            }
            self.cluster_shapes = [(c["cluster_id"], shape(c["boundary"])) for c in clusters if c.get("boundary")]
            self.cluster_tree = STRtree([g for _, g in self.cluster_shapes]) if self.cluster_shapes else None
            self.service_area_shapes = [(hid, shape(g)) for hid, g in self.service_areas.items()]
            self.service_area_tree = (
                STRtree([g for _, g in self.service_area_shapes]) if self.service_area_shapes else None
            )
            self.loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.ready = True
            self.error = None
            log.info("Dataset loaded: %d hubs, %d clusters", len(hubs), len(clusters))

    def require(self) -> "DataStore":
        if not self.ready:
            raise DatasetNotReady(self.error or "Dataset not loaded")
        return self

    def cluster_public(self, c: dict[str, Any], include_boundary: bool = True) -> dict[str, Any]:
        if include_boundary:
            return c
        return {k: v for k, v in c.items() if k != "boundary"}
