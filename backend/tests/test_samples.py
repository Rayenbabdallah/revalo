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

from revalo.engine.audit import audit, compare_expected
from revalo.engine.audit import summarize as summarize_result
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
    return summarize_result(analyze(path.read_bytes(), path.name))


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


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_sample_holds_together_physically(path: Path):
    """No overlaps, nothing outside the sheet, areas and weights consistent."""
    report = audit(analyze(path.read_bytes(), path.name))
    assert report.ok, [f"sheet {f.sheet} {f.check}: {f.message}" for f in report.findings]


def test_comparison_names_each_difference():
    base = summarize(SAMPLES[0])
    changed = json.loads(json.dumps(base))
    changed["sheets"][0]["part_count"] += 1
    assert compare_expected(base, base) == []
    assert any("parts" in d for d in compare_expected(changed, base))
