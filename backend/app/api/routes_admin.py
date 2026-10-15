"""Settings, routing status, route history and KML import endpoints."""

from __future__ import annotations

import io
import logging
import re
import shutil
import zipfile
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..database import Database
from ..models import HistoryListResponse, ImportResponse, PreferencesUpdate
from ..services.data_store import DataStore
from ..services.nearest_hub_service import ResultCache
from ..services.pipeline import KmlProcessingError, process_kml
from ..services.report_service import render_markdown_report
from ..services.routing_service import TRAVEL_MODES, RoutingService
from .deps import get_cache, get_db, get_routing, get_store_any

router = APIRouter(prefix="/api", tags=["admin"])
log = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 60 * 1024 * 1024


# -- settings ------------------------------------------------------------------

@router.get("/settings")
def get_preferences(db: Database = Depends(get_db), routing: RoutingService = Depends(get_routing)):
    prefs = db.get_preferences()
    return {"preferences": prefs, "routing": routing.status(prefs["routing_provider"]),
            "travel_modes": list(TRAVEL_MODES)}


@router.put("/settings")
def update_preferences(update: PreferencesUpdate, db: Database = Depends(get_db),
                       routing: RoutingService = Depends(get_routing)):
    prefs = db.update_preferences(update.model_dump(exclude_none=True))
    return {"preferences": prefs, "routing": routing.status(prefs["routing_provider"]),
            "travel_modes": list(TRAVEL_MODES)}


@router.delete("/settings")
def reset_preferences(db: Database = Depends(get_db), routing: RoutingService = Depends(get_routing)):
    prefs = db.reset_preferences()
    return {"preferences": prefs, "routing": routing.status(prefs["routing_provider"]),
            "travel_modes": list(TRAVEL_MODES)}


@router.get("/routing/status")
def routing_status(db: Database = Depends(get_db), routing: RoutingService = Depends(get_routing)):
    return routing.status(db.get_preferences()["routing_provider"])


@router.post("/routing/test")
async def routing_test(provider: Optional[str] = None, mode: str = "driving",
                       db: Database = Depends(get_db), routing: RoutingService = Depends(get_routing)):
    if mode not in TRAVEL_MODES:
        raise HTTPException(422, f"mode must be one of {TRAVEL_MODES}")
    return await routing.self_test(provider or db.get_preferences()["routing_provider"], mode)


# -- history -------------------------------------------------------------------

@router.get("/history", response_model=HistoryListResponse)
def list_history(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
                 db: Database = Depends(get_db)):
    rows, total = db.list_history(limit, offset)
    return {"total": total, "records": rows}


@router.get("/history/{record_id}")
def get_history(record_id: int, db: Database = Depends(get_db), cache: ResultCache = Depends(get_cache)):
    rec = db.get_history(record_id)
    if rec is None:
        raise HTTPException(404, "History record not found")
    cache.put(rec["result"])  # make it exportable again
    return rec


@router.delete("/history/{record_id}")
def delete_history(record_id: int, db: Database = Depends(get_db)):
    if not db.delete_history(record_id):
        raise HTTPException(404, "History record not found")
    return {"deleted": 1}


@router.delete("/history")
def clear_history(db: Database = Depends(get_db), cache: ResultCache = Depends(get_cache)):
    n = db.clear_history()
    cache.clear()
    return {"deleted": n}


# -- import --------------------------------------------------------------------

def _summary(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "placemarks": a["placemark_count"],
        "hubs": a["hubs"]["total"],
        "clusters": a["clusters"]["total"],
        "cluster_method": a["clusters"]["method"],
        "repairs": a["repair"]["total_changes"],
        "valid_before_repair": a["repair"]["valid_before"],
        "parse_error_before": a["repair"]["parse_error_before"],
        "coordinates_unchanged": a["repair"]["coordinates_unchanged"],
        "categories": a["category_counts"],
        "status_counts": a["hubs"]["status_counts"],
        "duplicate_hub_ids": len(a["quality"]["duplicate_hub_ids"]),
        "unassigned_hubs": len(a["quality"]["unassigned_hubs"]),
        "coordinate_issues": len(a["coordinate_issues"]),
    }


@router.post("/import-kml", response_model=ImportResponse)
async def import_kml(
    request: Request,
    file: UploadFile = File(...),
    activate: bool = Form(False, description="Replace the active dataset with this file"),
    store: DataStore = Depends(get_store_any),
    cache: ResultCache = Depends(get_cache),
):
    settings = request.app.state.settings
    if activate and settings.dataset_read_only:
        raise HTTPException(403, "This deployment serves a read-only dataset, so imports can be analysed but not "
                                 "activated. To change the live data, process the new KML locally and push data/processed "
                                 "to the repository.")
    raw = await file.read()
    max_bytes = int(min(MAX_UPLOAD_BYTES, settings.max_upload_mb * 1024 * 1024))
    if len(raw) > max_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb:g} MB here). A .kmz (zipped KML) is "
                                 f"usually ~10x smaller.")
    name = file.filename or "upload.kml"
    if name.lower().endswith(".kmz"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                kml_names = [n for n in z.namelist() if n.lower().endswith(".kml")]
                if not kml_names:
                    raise HTTPException(422, "KMZ archive contains no .kml file")
                raw = z.read("doc.kml" if "doc.kml" in kml_names else kml_names[0])
        except zipfile.BadZipFile as exc:
            raise HTTPException(422, "Invalid KMZ (not a zip archive)") from exc
    elif not name.lower().endswith(".kml"):
        raise HTTPException(422, "Upload a .kml or .kmz file")
    if b"<kml" not in raw[:5000] and b"<Document" not in raw[:20000]:
        raise HTTPException(422, "File does not look like KML (no <kml> root element)")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    uploads = settings.writable_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    src = uploads / f"{stamp}_{safe}"
    src.write_bytes(raw)  # the untouched original is the backup
    staging = settings.writable_dir / "staging" / stamp

    try:
        analysis = await run_in_threadpool(process_kml, src, staging, settings.classification_config, None, name)
    except KmlProcessingError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(422, detail={"message": str(exc), **exc.details}) from exc
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(staging, ignore_errors=True)
        log.exception("KML import failed")
        raise HTTPException(422, detail={"message": f"Could not process KML: {exc}"}) from exc

    report = render_markdown_report(analysis)
    if not activate:
        shutil.rmtree(staging, ignore_errors=True)
        return {"activated": False, "file_name": name, "summary": _summary(analysis), "report_markdown": report}

    if analysis["hubs"]["total"] == 0:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(422, "No hubs were identified in this KML; the active dataset was not replaced. "
                                 "Adjust backend/config/classification.json if hubs use different attributes.")

    processed = settings.processed_dir
    archive = settings.writable_dir / "archive" / stamp
    if processed.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(processed), str(archive))
    shutil.move(str(staging), str(processed))
    store.load()
    cache.clear()
    return {"activated": True, "file_name": name, "summary": _summary(analysis), "report_markdown": report}
