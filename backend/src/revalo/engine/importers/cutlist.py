"""Cut list importer for panel saws.

Panel saw workshops often have no drawing at all, only a list of part sizes
(exported from OptiCut, CutList Plus, a spreadsheet, or typed by hand). A cut
list has no positions, so parts are laid out with a guillotine packer: every cut
runs edge to edge, the way a panel saw works. The layout is flagged as
estimated and the manager confirms the result.
"""

from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass

from shapely.geometry import box

from revalo.engine.importers.common import ImportOptions
from revalo.engine.materials import default_kerf
from revalo.engine.model import Job, JobImportError, KerfSide, SheetLayout, SourceFormat
from revalo.engine.units import parse_number

DEFAULT_PANEL = (2440.0, 1220.0)
MAX_PARTS = 5000

_HEADERS = {
    "length": {"length", "longueur", "long", "len", "l", "hauteur", "height", "h"},
    "width": {"width", "largeur", "larg", "w"},
    "qty": {"qty", "quantity", "quantite", "qte", "nb", "nombre", "count", "pcs", "q", "n"},
    "label": {
        "label",
        "name",
        "nom",
        "designation",
        "ref",
        "reference",
        "part",
        "piece",
        "description",
        "id",
    },
    "grain": {"grain", "fil", "rotation", "rotate", "rot", "sens"},
    "material": {"material", "matiere", "materiau", "mat"},
    "thickness": {"thickness", "epaisseur", "ep", "thk", "t", "e"},
}
_SHEET_LABELS = {"sheet", "panneau", "panel", "stock", "plaque", "tole", "board", "brut"}
_NO = {"no", "non", "n", "0", "false", "faux", "fixed", "fixe"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.strip().lower().replace(".", "").replace("_", " ").strip()


@dataclass
class CutPart:
    label: str
    length: float
    width: float
    rotatable: bool


@dataclass
class _Rect:
    x: float
    y: float
    w: float
    h: float


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _map_header(row: list[str]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        key = _norm(cell)
        for field, names in _HEADERS.items():
            if key in names and field not in mapping:
                mapping[field] = idx
    return mapping if {"length", "width"} <= mapping.keys() else None


def parse_cutlist(data: bytes, default_rotatable: bool = True):
    """Read parts, an optional sheet row, and metadata text from a CSV cut list."""
    text = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if text.count(";") > text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise JobImportError("The cut list is empty.")

    mapping = _map_header(rows[0])
    body = rows[1:] if mapping else rows
    mapping = mapping or {"length": 0, "width": 1, "qty": 2, "label": 3}

    parts: list[CutPart] = []
    sheet: tuple[float, float] | None = None
    meta: list[str] = []
    skipped = 0

    def cell(row: list[str], field: str) -> str:
        idx = mapping.get(field)
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    for row in body:
        try:
            length = parse_number(cell(row, "length"))
            width = parse_number(cell(row, "width"))
        except ValueError:
            skipped += 1
            continue
        if length <= 0 or width <= 0:
            skipped += 1
            continue
        label = cell(row, "label")
        for field in ("material", "thickness"):
            if cell(row, field):
                meta.append(cell(row, field) + (" mm" if field == "thickness" else ""))
        if _norm(label) in _SHEET_LABELS:
            sheet = (max(length, width), min(length, width))
            continue
        qty_text = cell(row, "qty")
        try:
            qty = int(parse_number(qty_text)) if qty_text else 1
        except ValueError:
            qty = 1
        grain = cell(row, "grain")
        rotatable = default_rotatable and _norm(grain) not in _NO if grain else default_rotatable
        if len(parts) + max(qty, 0) > MAX_PARTS:
            raise JobImportError(f"Cut list has more than {MAX_PARTS} parts.")
        parts.extend(
            CutPart(label or f"P{len(parts) + 1}", length, width, rotatable) for _ in range(qty)
        )
    return parts, sheet, " ".join(meta), skipped


def _best_fit(free: list[_Rect], sizes: list[tuple[float, float]], kerf: float):
    """Free rectangle and orientation with the least wasted area, or None."""
    best = None
    for fi, rect in enumerate(free):
        for w, h in sizes:
            cw, ch = w + kerf, h + kerf
            if cw <= rect.w + 1e-9 and ch <= rect.h + 1e-9:
                score = (rect.w * rect.h - cw * ch, min(rect.w - cw, rect.h - ch))
                if best is None or score < best[0]:
                    best = (score, fi, w, h)
    return None if best is None else best[1:]


def _split(rect: _Rect, cw: float, ch: float) -> list[_Rect]:
    """Guillotine split of `rect` after placing a cw x ch cell in its corner.

    The cut runs along the shorter leftover axis so the larger offcut stays whole.
    """
    right_w, top_h = rect.w - cw, rect.h - ch
    if right_w < top_h:
        new = [_Rect(rect.x + cw, rect.y, right_w, ch), _Rect(rect.x, rect.y + ch, rect.w, top_h)]
    else:
        new = [_Rect(rect.x + cw, rect.y, right_w, rect.h), _Rect(rect.x, rect.y + ch, cw, top_h)]
    return [r for r in new if r.w > 1e-6 and r.h > 1e-6]


def guillotine_pack(
    parts: list[CutPart], sheet_w: float, sheet_h: float, kerf: float, trim: float
) -> tuple[list[list[tuple[CutPart, _Rect]]], list[CutPart]]:
    """Place parts on as many sheets as needed with guillotine cuts.

    Parts go largest first into the best-fitting free rectangle. Every part
    reserves one kerf on its right and top edge; the usable panel grows by one
    kerf to compensate, so parts can still touch the trimmed edge.
    """
    usable_w = sheet_w - 2 * trim + kerf
    usable_h = sheet_h - 2 * trim + kerf
    order = sorted(parts, key=lambda p: (p.length * p.width, max(p.length, p.width)), reverse=True)
    sheets: list[list[tuple[CutPart, _Rect]]] = []
    free_by_sheet: list[list[_Rect]] = []
    too_big: list[CutPart] = []

    for part in order:
        sizes = [(part.length, part.width)]
        if part.rotatable and part.length != part.width:
            sizes.append((part.width, part.length))
        if _best_fit([_Rect(0.0, 0.0, usable_w, usable_h)], sizes, kerf) is None:
            too_big.append(part)
            continue
        target = None
        for sheet_idx, free in enumerate(free_by_sheet):
            fit = _best_fit(free, sizes, kerf)
            if fit is not None:
                target = (sheet_idx, fit)
                break
        if target is None:
            sheets.append([])
            free_by_sheet.append([_Rect(0.0, 0.0, usable_w, usable_h)])
            target = (len(sheets) - 1, _best_fit(free_by_sheet[-1], sizes, kerf))
        sheet_idx, (fi, w, h) = target
        rect = free_by_sheet[sheet_idx].pop(fi)
        sheets[sheet_idx].append((part, _Rect(rect.x + trim, rect.y + trim, w, h)))
        free_by_sheet[sheet_idx].extend(_split(rect, w + kerf, h + kerf))

    return sheets, too_big


def import_cutlist(data: bytes, source_name: str, options: ImportOptions | None = None) -> Job:
    options = options or ImportOptions()
    parts, sheet_row, meta, skipped = parse_cutlist(data, options.allow_rotation)
    if not parts:
        raise JobImportError("No valid parts (length and width) found in the cut list.")

    warnings = [
        "Part positions were laid out by Revalo (guillotine cuts); "
        "check them against the real cutting plan."
    ]
    size = options.sheet_size or sheet_row
    if size is None:
        size = DEFAULT_PANEL
        warnings.append(f"No panel size given; assumed {size[0]:.0f} x {size[1]:.0f} mm.")
    if skipped:
        warnings.append(f"{skipped} row(s) without a valid length and width were skipped.")

    kerf = options.kerf_mm
    if kerf is None:
        kerf = default_kerf("panel_saw", options.material_code)
    packed, too_big = guillotine_pack(parts, size[0], size[1], kerf, options.trim_mm)
    if too_big:
        warnings.append(f"{len(too_big)} part(s) are larger than the panel and were left out.")

    sheets = [
        SheetLayout(
            outline=box(0, 0, size[0], size[1]),
            parts=[box(r.x, r.y, r.x + r.w, r.y + r.h) for _, r in placements],
        )
        for placements in packed
    ]
    if not sheets:
        raise JobImportError("No part fits on the panel.")

    return Job(
        source_format=SourceFormat.CUTLIST,
        source_name=source_name,
        sheets=sheets,
        kerf_side=KerfSide.OUTSIDE,
        material_code=options.material_code,
        thickness_mm=options.thickness_mm,
        layout_estimated=True,
        warnings=warnings,
        metadata_text=meta,
    )
