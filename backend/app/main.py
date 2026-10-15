"""FastAPI application entry point.

Run from the ``backend`` directory::

    .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .api import routes_admin, routes_data, routes_export, routes_search
from .config import get_settings
from .database import Database
from .services.data_store import DataStore, DatasetNotReady
from .services.nearest_hub_service import ResultCache
from .services.pipeline import KmlProcessingError, process_kml
from .services.routing_service import RoutingError, RoutingService

log = logging.getLogger("smart_hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Uvicorn's access log prints query strings (e.g. /api/locate?lat=..&lng=..). The access_log middleware below
    # logs paths only, so user coordinates never reach the logs.
    logging.getLogger("uvicorn.access").disabled = True
    app.state.settings = settings
    app.state.db = Database(settings.database_path)
    store = DataStore(settings.processed_dir)

    if not (settings.processed_dir / "hubs.json").exists() and settings.source_kml.exists():
        log.info("No processed dataset found - processing %s", settings.source_kml.name)
        try:
            process_kml(settings.source_kml, settings.processed_dir, settings.classification_config,
                        backup_path=settings.source_dir / "original_backup.kml")
        except KmlProcessingError as exc:
            log.error("KML processing failed: %s %s", exc, exc.details)
    store.load()
    app.state.store = store
    app.state.routing = RoutingService(settings)
    app.state.results = ResultCache()
    status = app.state.routing.status(app.state.db.get_preferences()["routing_provider"])
    log.info("Routing provider: %s", status["active"] or status["error"])
    yield
    await app.state.routing.aclose()


app = FastAPI(
    title="Smart Hub Location & Routing API",
    version=__version__,
    description="Hub/cluster analytics, nearest hub by real road distance, road routes and Google Earth KML export.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    # Path only: query strings may contain coordinates, which are not logged.
    log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code,
             (time.perf_counter() - t0) * 1000)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query"))
        errors.append({"field": loc, "message": e.get("msg")})
    summary = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
    return JSONResponse(status_code=422, content={"detail": f"Invalid request - {summary}", "errors": errors})


@app.exception_handler(DatasetNotReady)
async def dataset_not_ready(_: Request, exc: DatasetNotReady):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(RoutingError)
async def routing_error(_: Request, exc: RoutingError):
    return JSONResponse(status_code=502, content={"detail": exc.to_dict()})


app.include_router(routes_data.router)
app.include_router(routes_search.router)
app.include_router(routes_export.router)
app.include_router(routes_admin.router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": "Smart Hub Location & Routing API", "docs": "/docs", "health": "/api/health"}
