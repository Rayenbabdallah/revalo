"""Command line entry point: `revalo analyze <file>`, `revalo users add ...`."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
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

    u = sub.add_parser("users", help="list or add workshop accounts")
    usub = u.add_subparsers(dest="users_command", required=True)
    usub.add_parser("list", help="list accounts")
    add = usub.add_parser("add", help="add an account (asks for the password)")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--role", choices=["operator", "manager", "owner"], default="operator")

    acc = sub.add_parser(
        "accuracy",
        help="check the engine on job files: physical checks, plus reviewed baselines if any",
    )
    acc.add_argument("paths", nargs="*", type=Path, help="files or folders (default: samples)")
    acc.add_argument("--expected", type=Path, help="folder of reviewed baselines")

    sub.add_parser(
        "demo",
        help="fill an empty database with a demo workshop (password: REVALO_DEMO_PASSWORD)",
    )
    return parser


JOB_SUFFIXES = {".dxf", ".nc", ".gcode", ".ngc", ".tap", ".cnc", ".csv"}


def _accuracy(args: argparse.Namespace) -> int:
    """One line per file: what was found, the physical checks, drift from the baseline."""
    from revalo.api.samples import samples_dir
    from revalo.engine.audit import audit, compare_expected, summarize

    root = samples_dir()
    paths = args.paths or [root / "synthetic", root / "public"]
    expected_dir = args.expected or (root / "expected" if not args.paths else None)
    files = sorted(
        f
        for p in paths
        for f in ([p] if p.is_file() else (p.iterdir() if p.is_dir() else []))
        if f.suffix.lower() in JOB_SUFFIXES
    )
    if not files:
        print("error: no job files found", file=sys.stderr)
        return 1

    failed = 0
    print(f"{'file':<44} {'sheets':>6} {'parts':>6} {'rem.':>5}  result")
    for f in files:
        try:
            result = analyze(f.read_bytes(), f.name)
        except JobImportError as exc:
            failed += 1
            print(f"{f.name:<44} {'-':>6} {'-':>6} {'-':>5}  cannot read: {exc}")
            continue
        report = audit(result)
        problems = [f"sheet {x.sheet} {x.check}: {x.message}" for x in report.findings]
        baseline = expected_dir / f"{f.name}.json" if expected_dir else None
        if baseline and baseline.is_file():
            problems += compare_expected(summarize(result), json.loads(baseline.read_text("utf-8")))
            status = "ok, matches baseline" if not problems else "CHECK"
        else:
            status = "ok, no baseline" if not problems else "CHECK"
        failed += bool(problems)
        print(f"{f.name:<44} {report.sheets:>6} {report.parts:>6} {report.remnants:>5}  {status}")
        for problem in problems:
            print(f"    - {problem}")
    print()
    print(f"{len(files) - failed} of {len(files)} files pass.")
    return 1 if failed else 0


def _demo() -> int:
    from revalo.api.samples import samples_dir
    from revalo.db.migrate import upgrade
    from revalo.db.session import _session_factory
    from revalo.services.demo import DemoError, seed_demo
    from revalo.storage import get_storage

    upgrade()
    password = os.getenv("REVALO_DEMO_PASSWORD") or secrets.token_urlsafe(9)
    with _session_factory()() as session:
        try:
            summary = seed_demo(session, get_storage(), samples_dir(), password)
        except DemoError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    print(
        f"Demo workshop ready: {summary.jobs} jobs, {summary.in_stock} pieces in stock, "
        f"{summary.listings} listings, {summary.buyers} buyers, {summary.offers} offers to buy."
    )
    for role, email, name in summary.accounts:
        print(f"  {role:<9} {email:<28} {name}")
    if not os.getenv("REVALO_DEMO_PASSWORD"):
        print(f"Password for all three: {password}")
    return 0


def _users(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from revalo.db.migrate import upgrade
    from revalo.db.models import Role, User
    from revalo.db.session import _session_factory
    from revalo.services.auth import AuthError, create_user
    from revalo.services.jobs import default_workshop

    upgrade()
    with _session_factory()() as session:
        if args.users_command == "list":
            for user in session.scalars(select(User).order_by(User.created_at)):
                state = "" if user.active else "  (removed)"
                print(f"{user.role:<9} {user.email:<32} {user.name}{state}")
            return 0
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Again: "):
            print("error: the passwords differ", file=sys.stderr)
            return 1
        try:
            user = create_user(
                session, default_workshop(session), args.email, args.name, Role(args.role), password
            )
        except AuthError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Added {user.name} <{user.email}> as {user.role}.")
        return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "users":
        return _users(args)
    if args.command == "demo":
        return _demo()
    if args.command == "accuracy":
        return _accuracy(args)
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
