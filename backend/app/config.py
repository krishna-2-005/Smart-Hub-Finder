"""Application configuration.

Static configuration (paths, API keys, provider URLs) comes from environment
variables / ``backend/.env``. User-adjustable runtime preferences (default
travel mode, search radius, ...) live in SQLite and are managed by
``app.database``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Data locations -------------------------------------------------
    data_dir: Path = PROJECT_ROOT / "data"
    exports_dir: Path = PROJECT_ROOT / "exports"
    source_kml: Path = PROJECT_ROOT / "Akhil Copy.kml"
    classification_config: Path = BACKEND_DIR / "config" / "classification.json"
    database_path: Path = PROJECT_ROOT / "data" / "app.db"

    # --- Routing ----------------------------------------------------------
    # auto -> Google Routes API when GOOGLE_MAPS_API_KEY is set, otherwise OSRM.
    routing_provider: str = "auto"
    google_maps_api_key: str | None = None
    ors_api_key: str | None = None
    osrm_driving_url: str = "https://router.project-osrm.org"
    osrm_cycling_url: str = "https://routing.openstreetmap.de/routed-bike"
    osrm_walking_url: str = "https://routing.openstreetmap.de/routed-foot"
    routing_timeout_s: float = 25.0
    routing_user_agent: str = "SmartHubFinder/1.0 (hub-routing demo)"

    # --- API ----------------------------------------------------------------
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "https://localhost:5173,https://127.0.0.1:5173"
    )
    log_level: str = "INFO"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def source_dir(self) -> Path:
        return self.data_dir / "source"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
