"""Repair, analyse and convert the source KML into the processed dataset.

Usage (from the ``backend`` directory)::

    .venv/Scripts/python -m scripts.process_kml               # uses SOURCE_KML / "Akhil Copy.kml"
    .venv/Scripts/python -m scripts.process_kml path/to/file.kml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.pipeline import KmlProcessingError, process_kml  # noqa: E402


def main() -> int:
    settings = get_settings()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kml", nargs="?", type=Path, default=settings.source_kml)
    ap.add_argument("--out", type=Path, default=settings.processed_dir)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.kml.exists():
        print(f"KML not found: {args.kml}", file=sys.stderr)
        return 1
    try:
        a = process_kml(
            args.kml,
            args.out,
            settings.classification_config,
            backup_path=settings.source_dir / "original_backup.kml",
        )
    except KmlProcessingError as exc:
        print(f"FAILED: {exc}\n{json.dumps(exc.details, indent=2)}", file=sys.stderr)
        return 2

    print(json.dumps({
        "placemarks": a["placemark_count"],
        "hubs": a["hubs"]["total"],
        "clusters": a["clusters"]["total"],
        "repairs": a["repair"]["total_changes"],
        "coordinates_unchanged": a["repair"]["coordinates_unchanged"],
        "categories": a["category_counts"],
        "output_dir": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
