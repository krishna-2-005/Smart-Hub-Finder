"""Validate KML files against the official OGC KML 2.2 XML Schema.

The schema and its two imports (Atom, OASIS xAL) are downloaded once into
``data/schemas`` and the import locations are rewritten to the local copies.

Usage (from ``backend``)::

    .venv/Scripts/python -m scripts.validate_kml ../exports/*.kml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings  # noqa: E402

SCHEMAS = {
    "ogckml22.xsd": "https://schemas.opengis.net/kml/2.2.0/ogckml22.xsd",
    "atom-author-link.xsd": "https://schemas.opengis.net/kml/2.2.0/atom-author-link.xsd",
    "xAL.xsd": "https://docs.oasis-open.org/election/external/xAL.xsd",
}


def load_schema(cache: Path) -> etree.XMLSchema:
    cache.mkdir(parents=True, exist_ok=True)
    for name, url in SCHEMAS.items():
        target = cache / name
        if not target.exists():
            r = httpx.get(url, timeout=60, follow_redirects=True)
            r.raise_for_status()
            target.write_bytes(r.content)
    main = (cache / "ogckml22.xsd").read_text(encoding="utf-8")
    main = main.replace(
        'schemaLocation="http://schemas.opengis.net/kml/2.2.0/atom-author-link.xsd"', 'schemaLocation="atom-author-link.xsd"'
    ).replace('schemaLocation="http://docs.oasis-open.org/election/external/xAL.xsd"', 'schemaLocation="xAL.xsd"')
    local = cache / "ogckml22.local.xsd"
    local.write_text(main, encoding="utf-8")
    return etree.XMLSchema(etree.parse(str(local)))


def validate(schema: etree.XMLSchema, path: Path) -> list[str]:
    doc = etree.parse(str(path), etree.XMLParser(huge_tree=True))
    if schema.validate(doc):
        return []
    return [f"line {e.line}: {e.message}" for e in schema.error_log][:20]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    schema = load_schema(get_settings().data_dir / "schemas")
    failed = 0
    for f in args.files:
        errors = validate(schema, f)
        if errors:
            failed += 1
            print(f"INVALID  {f}")
            for e in errors:
                print(f"         {e}")
        else:
            print(f"VALID    {f}  (OGC KML 2.2 schema)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
