"""The accuracy command works on any job file, with or without a baseline."""

from __future__ import annotations

from pathlib import Path

from revalo import cli

SAMPLE = (
    Path(__file__).resolve().parents[2] / "samples" / "synthetic" / "laser_S235_3mm_3000x1500.dxf"
)


def test_accuracy_on_a_new_file_runs_the_physical_checks(capsys, tmp_path):
    copy = tmp_path / "workshop_job.dxf"
    copy.write_bytes(SAMPLE.read_bytes())
    assert cli.main(["accuracy", str(copy)]) == 0
    out = capsys.readouterr().out
    assert "workshop_job.dxf" in out and "ok, no baseline" in out and "1 of 1 files pass." in out


def test_accuracy_reports_files_it_cannot_read(capsys, tmp_path):
    bad = tmp_path / "broken.dxf"
    bad.write_text("not a dxf")
    assert cli.main(["accuracy", str(tmp_path)]) == 1
    assert "cannot read" in capsys.readouterr().out
