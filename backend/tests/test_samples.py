"""Regression tests over every sample job in samples/.

Each sample has an expected summary in samples/expected/<file name>.json.
After an intended engine change, refresh them with:

    REVALO_UPDATE_EXPECTED=1 uv run pytest tests/test_samples.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from revalo.engine.pipeline import analyze

ROOT = Path(__file__).resolve().parents[2] / "samples"
EXPECTED = ROOT / "expected"
SAMPLE_DIRS = ("synthetic", "public")
DIM_TOLERANCE_MM = 2.0

SAMPLES = sorted(
    p
    for d in SAMPLE_DIRS
    if (ROOT / d).is_dir()
    for p in (ROOT / d).iterdir()
    if p.suffix.lower() in {".dxf", ".nc", ".gcode", ".ngc", ".tap", ".csv"}
)


def summarize(path: Path) -> dict:
    result = analyze(path.read_bytes(), path.name)
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


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_sample_matches_expected(path: Path):
    actual = summarize(path)
    expected_file = EXPECTED / f"{path.name}.json"
    if os.getenv("REVALO_UPDATE_EXPECTED") == "1" or not expected_file.exists():
        EXPECTED.mkdir(parents=True, exist_ok=True)
        expected_file.write_text(
            json.dumps(actual, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        if os.getenv("REVALO_UPDATE_EXPECTED") != "1":
            pytest.fail(f"No expected result for {path.name}; wrote one, review and commit it.")
        return

    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    for key in ("format", "material", "thickness_mm", "process", "kerf_mm"):
        assert actual[key] == expected[key], key
    assert len(actual["sheets"]) == len(expected["sheets"])
    for got, want in zip(actual["sheets"], expected["sheets"], strict=True):
        assert got["size"] == pytest.approx(want["size"], abs=0.5)
        assert got["sheet_detected"] == want["sheet_detected"]
        assert got["part_count"] == want["part_count"]
        assert len(got["remnants"]) == len(want["remnants"])
        for (gw, gh), (ww, wh) in zip(got["remnants"], want["remnants"], strict=True):
            assert abs(gw - ww) <= DIM_TOLERANCE_MM and abs(gh - wh) <= DIM_TOLERANCE_MM
