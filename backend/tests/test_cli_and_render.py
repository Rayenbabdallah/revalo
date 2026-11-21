import json
import xml.etree.ElementTree as ET

from dxf_helpers import new_doc, rect, to_bytes

from revalo.cli import main
from revalo.engine.pipeline import analyze
from revalo.engine.render import render_svg


def nest_file(tmp_path):
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    rect(msp, 0, 0, 1000, 1500)
    path = tmp_path / "S235_3mm.dxf"
    path.write_bytes(to_bytes(doc))
    return path


def test_svg_is_well_formed_and_labels_remnants(tmp_path):
    path = nest_file(tmp_path)
    svg = render_svg(analyze(path.read_bytes(), path.name))
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "R1" in svg and "kg" in svg


def test_cli_summary_svg_and_json(tmp_path, capsys):
    path = nest_file(tmp_path)
    svg = tmp_path / "out.svg"
    assert main(["analyze", str(path), "--svg", str(svg)]) == 0
    out = capsys.readouterr().out
    assert "Mild steel" in out and "S1-R1" in out
    assert svg.read_text(encoding="utf-8").startswith("<svg")

    assert main(["analyze", str(path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["totals"]["remnant_count"] == 1


def test_cli_reports_errors(tmp_path, capsys):
    bad = tmp_path / "bad.dxf"
    bad.write_bytes(b"not a dxf")
    assert main(["analyze", str(bad)]) == 1
    assert "error" in capsys.readouterr().err


def test_cli_lists_materials(capsys):
    assert main(["materials"]) == 0
    assert "steel_mild" in capsys.readouterr().out
