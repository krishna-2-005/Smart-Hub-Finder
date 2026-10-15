"""Application configuration.

Static configuration (paths, API keys, provider URLs) comes from environment
variables / ``backend/.env``. User-adjustable runtime preferences (default
travel mode, search radius, ...) live in SQLite and are managed by
``app.database``.

On Vercel (``VERCEL=1`` is set by the platform) the deployment bundle is
read-only: the processed dataset is served as committed, and anything the app
writes (SQLite, uploads, generated files) goes to a temporary directory.
"""

from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Vercel rejects function request/response bodies above 4.5 MB.
SERVERLESS_MAX_UPLOAD_MB = 4.4
LOCAL_MAX_UPLOAD_MB = 60.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Data locations -------------------------------------------------
    data_dir: Path = PROJECT_ROOT / "data"
    source_kml: Path = PROJECT_ROOT / "Akhil Copy.kml"
    classification_config: Path = BACKEND_DIR / "config" / "classification.json"
    # Unset = <data_dir>/app.db locally, <temp>/smart-hub/app.db on Vercel.
    database_path: Path | None = None
    # Unset = <project>/exports locally, <temp>/smart-hub/exports on Vercel.
    exports_dir: Path | None = None
    # Writable scratch space for uploads/staging/archives. Unset = data_dir locally, temp dir on Vercel.
    work_dir: Path | None = None

    # --- Deployment -------------------------------------------------------
    vercel: bool = False  # set to "1" by the Vercel platform
    read_only_dataset: bool | None = None  # unset = True on Vercel

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
    def writable_dir(self) -> Path:
        if self.work_dir is not None:
            return self.work_dir
        return Path(tempfile.gettempdir()) / "smart-hub" if self.vercel else self.data_dir

    @property
    def db_path(self) -> Path:
        if self.database_path is not None:
            return self.database_path
        return self.writable_dir / "app.db"

    @property
    def exports_path(self) -> Path:
        if self.exports_dir is not None:
            return self.exports_dir
        return self.writable_dir / "exports" if self.vercel else PROJECT_ROOT / "exports"

    @property
    def dataset_read_only(self) -> bool:
        return self.vercel if self.read_only_dataset is None else self.read_only_dataset

    @property
    def platform(self) -> str:
        return "vercel" if self.vercel else "local"

    @property
    def persistent_storage(self) -> bool:
        """False when SQLite lives on an ephemeral serverless disk."""
        return not self.vercel or self.database_path is not None

    @property
    def max_upload_mb(self) -> float:
        return SERVERLESS_MAX_UPLOAD_MB if self.vercel else LOCAL_MAX_UPLOAD_MB

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def deployment_info(self) -> dict:
        return {
            "platform": self.platform,
            "read_only_dataset": self.dataset_read_only,
            "persistent_storage": self.persistent_storage,
            "max_upload_mb": self.max_upload_mb,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
