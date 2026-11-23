"""Accuracy checks on an analysis: does the result hold together physically?

These checks need no expected answer, so they work on any file, including real
workshop jobs that have never been seen before:

- material balance: parts, remnants and kerf never add up to more than the sheet
- every remnant lies inside the sheet
- no remnant overlaps a part or another remnant
- every remnant meets the shorter-side minimum
- weights follow from area, thickness and density

`compare_expected` adds a regression comparison when a reviewed baseline exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely.ops import unary_union

from revalo.engine.pipeline import AnalysisResult

AREA_TOLERANCE = 0.002
"""Share of the sheet area allowed as rounding or polygon-cleaning noise."""
OVERLAP_MM2 = 25.0
"""Overlap below this area (5 x 5 mm) is drawing noise, not a real overlap."""
DIM_TOLERANCE_MM = 2.0


@dataclass
class Finding:
    sheet: int
    check: str
    message: str


@dataclass
class Audit:
    sheets: int = 0
    parts: int = 0
    remnants: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings


def audit(result: AnalysisResult) -> Audit:
    report = Audit(sheets=len(result.sheets))
    for sheet in result.sheets:
        lo = sheet.leftover
        n = sheet.index + 1
        report.parts += sheet.part_count
        report.remnants += len(lo.remnants)

        used = lo.parts_area + lo.remnant_area + lo.kerf_area
        if used - lo.sheet_area > AREA_TOLERANCE * lo.sheet_area:
            report.findings.append(
                Finding(
                    n,
                    "balance",
                    f"parts, remnants and kerf exceed the sheet by {used - lo.sheet_area:,.0f} mm2",
                )
            )

        outline = sheet.outline.buffer(DIM_TOLERANCE_MM)
        parts = unary_union(lo.part_geometry) if lo.part_geometry else None
        for i, r in enumerate(lo.remnants):
            label = f"R{i + 1}"
            if not outline.contains(r.polygon):
                report.findings.append(Finding(n, "inside", f"{label} leaves the sheet"))
            if parts is not None:
                overlap = r.polygon.intersection(parts).area
                if overlap > OVERLAP_MM2:
                    report.findings.append(
                        Finding(n, "overlap", f"{label} covers {overlap:,.0f} mm2 of parts")
                    )
            for j, other in enumerate(lo.remnants[i + 1 :], start=i + 2):
                shared = r.polygon.intersection(other.polygon).area
                if shared > OVERLAP_MM2:
                    report.findings.append(Finding(n, "overlap", f"{label} and R{j} overlap"))
            if r.short_side + 1e-6 < result.min_side_mm - DIM_TOLERANCE_MM:
                report.findings.append(
                    Finding(
                        n,
                        "min_side",
                        f"{label} is {r.short_side:.0f} mm, "
                        f"under the {result.min_side_mm:.0f} mm minimum",
                    )
                )
            if result.material is not None and result.thickness_mm:
                expected = result.material.weight_kg(r.area, result.thickness_mm)
                got = result.weight(r.area)
                if got is not None and abs(got - expected) > max(0.005 * expected, 0.002):
                    report.findings.append(
                        Finding(n, "weight", f"{label} weight {got} kg, expected {expected:.3f} kg")
                    )
    return report


def summarize(result: AnalysisResult) -> dict[str, Any]:
    """The shape of a reviewed baseline in samples/expected."""
    data = result.to_dict(include_geometry=False)
    return {
        "format": data["source"]["format"],
        "material": data["material"]["code"] if data["material"] else None,
        "thickness_mm": data["thickness_mm"],
        "process": data["process"],
        "kerf_mm": data["kerf_mm"],
        "sheets": [
            {
                "size": [s["width"], s["height"]],
                "sheet_detected": s["sheet_detected"],
                "part_count": s["part_count"],
                "remnants": [[r["width"], r["height"]] for r in s["remnants"]],
            }
            for s in data["sheets"]
        ],
    }


def compare_expected(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Differences from a reviewed baseline, in plain words. Empty means it matches."""
    diffs = []
    for key in ("format", "material", "thickness_mm", "process", "kerf_mm"):
        if actual[key] != expected[key]:
            diffs.append(f"{key}: {expected[key]} became {actual[key]}")
    if len(actual["sheets"]) != len(expected["sheets"]):
        diffs.append(f"sheets: {len(expected['sheets'])} became {len(actual['sheets'])}")
        return diffs
    for n, (got, want) in enumerate(
        zip(actual["sheets"], expected["sheets"], strict=True), start=1
    ):
        if got["part_count"] != want["part_count"]:
            diffs.append(f"sheet {n} parts: {want['part_count']} became {got['part_count']}")
        if len(got["remnants"]) != len(want["remnants"]):
            diffs.append(
                f"sheet {n} remnants: {len(want['remnants'])} became {len(got['remnants'])}"
            )
            continue
        for i, ((gw, gh), (ww, wh)) in enumerate(
            zip(got["remnants"], want["remnants"], strict=True), start=1
        ):
            if abs(gw - ww) > DIM_TOLERANCE_MM or abs(gh - wh) > DIM_TOLERANCE_MM:
                diffs.append(f"sheet {n} R{i}: {ww:.0f} x {wh:.0f} became {gw:.0f} x {gh:.0f}")
    return diffs
