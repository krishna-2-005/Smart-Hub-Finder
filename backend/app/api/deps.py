"""FastAPI dependency accessors for shared application state."""

from __future__ import annotations

from fastapi import HTTPException, Request

from ..config import Settings
from ..database import Database
from ..services.data_store import DataStore
from ..services.nearest_hub_service import ResultCache
from ..services.routing_service import RoutingService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_store(request: Request) -> DataStore:
    store: DataStore = request.app.state.store
    if not store.ready:
        raise HTTPException(status_code=503, detail=store.error or "Dataset not loaded")
    return store


def get_store_any(request: Request) -> DataStore:
    return request.app.state.store


def get_routing(request: Request) -> RoutingService:
    return request.app.state.routing


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_cache(request: Request) -> ResultCache:
    return request.app.state.results
