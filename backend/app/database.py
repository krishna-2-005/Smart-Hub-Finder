"""SQLite persistence for route history and user preferences.

Search locations are written here only when the user opted in for that search
(``save_history``); GPS searches default to *not* saved in the UI. History can
be deleted per record or cleared entirely.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DEFAULT_PREFERENCES: dict[str, Any] = {
    "routing_provider": "auto",
    "travel_mode": "driving",
    "ranking": "distance",
    "search_radius_km": 15.0,
    "max_candidates": 60,
    "exhaustive_threshold": 50,
    "top_n": 5,
    "live_only": True,
    "max_snap_distance_m": 1000.0,
    "save_manual_searches": True,
    "save_gps_searches": False,
    "tracking_min_move_m": 150.0,
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    cluster_id TEXT,
    cluster_name TEXT,
    travel_mode TEXT,
    ranking TEXT,
    status TEXT,
    nearest_hub_id TEXT,
    nearest_hub_name TEXT,
    road_distance_m REAL,
    duration_s REAL,
    provider TEXT,
    candidates_evaluated INTEGER,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created ON search_history(created_at DESC);
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

HISTORY_COLUMNS = (
    "id", "result_id", "created_at", "source", "latitude", "longitude", "cluster_id", "cluster_name",
    "travel_mode", "ranking", "status", "nearest_hub_id", "nearest_hub_name", "road_distance_m",
    "duration_s", "provider", "candidates_evaluated",
)


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            con = sqlite3.connect(self.path)
            con.row_factory = sqlite3.Row
            try:
                yield con
                con.commit()
            finally:
                con.close()

    # -- preferences -----------------------------------------------------------
    def get_preferences(self) -> dict[str, Any]:
        prefs = dict(DEFAULT_PREFERENCES)
        with self.conn() as c:
            for row in c.execute("SELECT key, value FROM preferences"):
                if row["key"] in prefs:
                    prefs[row["key"]] = json.loads(row["value"])
        return prefs

    def update_preferences(self, values: dict[str, Any]) -> dict[str, Any]:
        with self.conn() as c:
            for k, v in values.items():
                if k in DEFAULT_PREFERENCES and v is not None:
                    c.execute(
                        "INSERT INTO preferences(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (k, json.dumps(v)),
                    )
        return self.get_preferences()

    def reset_preferences(self) -> dict[str, Any]:
        with self.conn() as c:
            c.execute("DELETE FROM preferences")
        return self.get_preferences()

    # -- history ---------------------------------------------------------------
    def add_history(self, result: dict[str, Any]) -> int:
        q = result["query"]
        n = result.get("nearest") or {}
        loc = result.get("location") or {}
        with self.conn() as c:
            cur = c.execute(
                "INSERT OR REPLACE INTO search_history(result_id, created_at, source, latitude, longitude, "
                "cluster_id, cluster_name, travel_mode, ranking, status, nearest_hub_id, nearest_hub_name, "
                "road_distance_m, duration_s, provider, candidates_evaluated, result_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    result["result_id"], result["created_at"], q.get("source", "manual"), q["latitude"],
                    q["longitude"], n.get("cluster_id") or loc.get("cluster_id"),
                    n.get("cluster_name") or loc.get("cluster_name"), q.get("travel_mode"), q.get("ranking"),
                    result.get("status"), n.get("hub_id"), n.get("display_name") or n.get("name"),
                    n.get("road_distance_m"), n.get("duration_s"), (result.get("provider") or {}).get("name"),
                    (result.get("evaluation") or {}).get("candidates_evaluated"),
                    json.dumps(result, default=str),
                ),
            )
            return int(cur.lastrowid or 0)

    def list_history(self, limit: int = 100, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        with self.conn() as c:
            total = c.execute("SELECT COUNT(*) FROM search_history").fetchone()[0]
            rows = c.execute(
                f"SELECT {', '.join(HISTORY_COLUMNS)} FROM search_history ORDER BY created_at DESC, id DESC "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows], total

    def get_history(self, record_id: int) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM search_history WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json"))
        return d

    def get_history_by_result(self, result_id: str) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT result_json FROM search_history WHERE result_id = ?", (result_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None

    def delete_history(self, record_id: int) -> bool:
        with self.conn() as c:
            return c.execute("DELETE FROM search_history WHERE id = ?", (record_id,)).rowcount > 0

    def clear_history(self) -> int:
        with self.conn() as c:
            return c.execute("DELETE FROM search_history").rowcount
