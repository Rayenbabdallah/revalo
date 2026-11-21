"""Command line entry point: `revalo analyze <file>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from revalo.engine.materials import materials, processes
from revalo.engine.model import JobImportError
from revalo.engine.pipeline import AnalysisOptions, AnalysisResult, analyze
from revalo.engine.render import render_svg


def _sheet_size(text: str) -> tuple[float, float]:
    try:
        a, b = (float(v) for v in text.lower().replace("*", "x").split("x"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use WIDTHxHEIGHT, for example 3000x1500") from exc
    return a, b


def _summary(result: AnalysisResult) -> str:
    data = result.to_dict(include_geometry=False)
    mat = data["material"]
    material = f"{mat['name']['en']} [{mat['source']}]" if mat else "unknown"
    lines = [
        f"File       {data['source']['name']} ({data['source']['format']})",
        f"Material   {material}",
        f"Thickness  {data['thickness_mm'] or 'unknown'} mm   Kerf {data['kerf_mm']} mm   "
        f"Min remnant side {data['min_side_mm']:.0f} mm",
    ]
    for s in data["sheets"]:
        lines.append("")
        lines.append(
            f"Sheet {s['index'] + 1}: {s['width']:.0f} x {s['height']:.0f} mm, "
            f"{s['part_count']} parts, utilization {s['utilization']:.1%}"
            + ("" if s["sheet_detected"] else " (sheet outline assumed)")
        )
        for r in s["remnants"]:
            weight = f"{r['weight_kg']:.2f} kg" if r["weight_kg"] is not None else "-"
            lines.append(
                f"  {r['id']:<7} {r['width']:>6.0f} x {r['height']:<6.0f} mm  "
                f"{r['area_m2']:.3f} m2  {weight}"
            )
        scrap = s["scrap_weight_kg"]
        lines.append(
            f"  scrap    {s['scrap_area_m2']:.3f} m2  "
            + (f"{scrap:.2f} kg" if scrap is not None else "-")
        )
    totals = data["totals"]
    lines.append("")
    lines.append(
        f"Total: {totals['remnant_count']} remnant(s), {totals['remnant_area_m2']:.3f} m2"
        + (
            f", {totals['remnant_weight_kg']:.1f} kg reusable, "
            f"{totals['scrap_weight_kg']:.1f} kg scrap"
            if totals["remnant_weight_kg"] is not None
            else ""
        )
    )
    for warning in data["warnings"]:
        lines.append(f"! {warning}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="revalo", description="Revalo leftover engine")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="find remnants and scrap in a CNC job file")
    a.add_argument("file", type=Path)
    a.add_argument("--material", choices=sorted(materials()), help="material code")
    a.add_argument("--thickness", type=float, help="thickness in mm")
    a.add_argument("--kerf", type=float, help="cut width in mm (tool diameter for G-code)")
    a.add_argument("--process", choices=sorted(processes()), help="cutting process")
    a.add_argument("--sheet", type=_sheet_size, help="sheet size, e.g. 3000x1500")
    a.add_argument("--min-side", type=float, help="shortest useful remnant side in mm")
    a.add_argument("--trim", type=float, default=0.0, help="panel edge trim for cut lists")
    a.add_argument("--no-rotation", action="store_true", help="cut lists: keep grain direction")
    a.add_argument("--svg", type=Path, help="write an SVG preview to this path")
    a.add_argument("--json", action="store_true", help="print the full JSON result")

    sub.add_parser("materials", help="list known materials")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "materials":
        for m in materials().values():
            print(f"{m.code:<18} {m.family:<8} {m.density_kg_m3:>6.0f} kg/m3  {m.name_en}")
        return 0

    options = AnalysisOptions(
        material_code=args.material,
        thickness_mm=args.thickness,
        kerf_mm=args.kerf,
        process=args.process,
        sheet_width_mm=args.sheet[0] if args.sheet else None,
        sheet_height_mm=args.sheet[1] if args.sheet else None,
        min_side_mm=args.min_side,
        trim_mm=args.trim,
        allow_rotation=not args.no_rotation,
    )
    try:
        result = analyze(args.file.read_bytes(), args.file.name, options)
    except (JobImportError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(_summary(result))
    if args.svg:
        args.svg.write_text(render_svg(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
