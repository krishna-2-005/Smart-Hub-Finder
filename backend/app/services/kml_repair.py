"""Safe, auditable repair of malformed KML/XML text.

Only two classes of defect are repaired automatically, because both have a
single unambiguous fix that cannot alter geographic meaning:

* bare ``&`` characters that do not start a valid XML entity -> ``&amp;``
  (CDATA sections and comments are left untouched, since ``&`` is legal there)
* characters that are illegal in XML 1.0 (C0 control characters) -> removed

Every change is recorded with its line/column so it can be reported. After
repair the ``<coordinates>`` blocks are compared byte-for-byte with the
original to prove that no geographic coordinate was modified.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import asdict, dataclass, field

from lxml import etree

BARE_AMP_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-fA-F]+);)")
INVALID_XML_CHAR_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
PROTECTED_RE = re.compile(r"<!\[CDATA\[.*?\]\]>|<!--.*?-->", re.DOTALL)
COORDINATES_RE = re.compile(r"<(?:\w+:)?coordinates>(.*?)</(?:\w+:)?coordinates>", re.DOTALL)


@dataclass
class RepairChange:
    line: int
    column: int
    kind: str
    original: str
    replacement: str
    context: str


@dataclass
class RepairResult:
    text: str
    encoding: str
    had_bom: bool
    valid_before: bool
    parse_error_before: str | None
    valid_after: bool
    parse_error_after: str | None
    coordinates_unchanged: bool
    coordinate_blocks: int
    changes: list[RepairChange] = field(default_factory=list)

    def summary(self) -> dict:
        kinds: dict[str, int] = {}
        for c in self.changes:
            kinds[c.kind] = kinds.get(c.kind, 0) + 1
        distinct_contexts: dict[str, int] = {}
        for c in self.changes:
            distinct_contexts[c.context] = distinct_contexts.get(c.context, 0) + 1
        return {
            "encoding": self.encoding,
            "had_bom": self.had_bom,
            "valid_before": self.valid_before,
            "parse_error_before": self.parse_error_before,
            "valid_after": self.valid_after,
            "parse_error_after": self.parse_error_after,
            "coordinates_unchanged": self.coordinates_unchanged,
            "coordinate_blocks": self.coordinate_blocks,
            "total_changes": len(self.changes),
            "changes_by_kind": kinds,
            "first_change": asdict(self.changes[0]) if self.changes else None,
            "distinct_contexts": [
                {"context": k, "occurrences": v}
                for k, v in sorted(distinct_contexts.items(), key=lambda kv: -kv[1])[:20]
            ],
            "sample_changes": [asdict(c) for c in self.changes[:10]],
        }


def safe_parser(**kw) -> etree.XMLParser:
    """XML parser for untrusted uploads: no entity expansion, DTD loading or network access (XXE / billion laughs).

    ``huge_tree`` is needed for multi-megabyte KML text nodes; it is only safe because entities are not resolved.
    """
    return etree.XMLParser(huge_tree=True, resolve_entities=False, load_dtd=False, no_network=True, **kw)


def _parse_error(text: str) -> str | None:
    try:
        etree.fromstring(text.encode("utf-8"), parser=safe_parser())
        return None
    except etree.XMLSyntaxError as exc:
        return str(exc)


def _decode(data: bytes) -> tuple[str, str, bool]:
    had_bom = data.startswith(b"\xef\xbb\xbf")
    if had_bom:
        data = data[3:]
    try:
        return data.decode("utf-8"), "utf-8", had_bom
    except UnicodeDecodeError:
        # Fall back to a lossless single-byte decoding and report it.
        return data.decode("cp1252", errors="replace"), "cp1252 (fallback)", had_bom


def _line_col(line_starts: list[int], pos: int) -> tuple[int, int]:
    i = bisect.bisect_right(line_starts, pos) - 1
    return i + 1, pos - line_starts[i] + 1


def _context(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()[:160]


def repair_kml_bytes(data: bytes) -> RepairResult:
    text, encoding, had_bom = _decode(data)
    error_before = _parse_error(text)

    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    changes: list[RepairChange] = []
    out: list[str] = []
    cursor = 0

    def fix_segment(seg_start: int, seg_end: int) -> None:
        segment = text[seg_start:seg_end]
        pieces: list[str] = []
        last = 0
        for m in re.finditer(f"{BARE_AMP_RE.pattern}|{INVALID_XML_CHAR_RE.pattern}", segment):
            abs_pos = seg_start + m.start()
            line, col = _line_col(line_starts, abs_pos)
            ch = m.group(0)
            if ch == "&":
                kind, repl = "unescaped_ampersand", "&amp;"
            else:
                kind, repl = "illegal_control_character", ""
            changes.append(
                RepairChange(
                    line=line,
                    column=col,
                    kind=kind,
                    original=repr(ch) if kind != "unescaped_ampersand" else "&",
                    replacement=repl,
                    context=_context(text, abs_pos, abs_pos + 1),
                )
            )
            pieces.append(segment[last : m.start()])
            pieces.append(repl)
            last = m.end()
        pieces.append(segment[last:])
        out.append("".join(pieces))

    for m in PROTECTED_RE.finditer(text):
        fix_segment(cursor, m.start())
        out.append(m.group(0))  # CDATA / comment copied verbatim
        cursor = m.end()
    fix_segment(cursor, len(text))
    fixed = "".join(out)

    before_coords = COORDINATES_RE.findall(text)
    after_coords = COORDINATES_RE.findall(fixed)
    error_after = _parse_error(fixed)

    return RepairResult(
        text=fixed,
        encoding=encoding,
        had_bom=had_bom,
        valid_before=error_before is None,
        parse_error_before=error_before,
        valid_after=error_after is None,
        parse_error_after=error_after,
        coordinates_unchanged=before_coords == after_coords,
        coordinate_blocks=len(after_coords),
        changes=changes,
    )
