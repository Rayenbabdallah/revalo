import json

import pytest
from dxf_helpers import new_doc, rect, to_bytes

from revalo.engine.model import JobImportError, SourceFormat
from revalo.engine.pipeline import AnalysisOptions, analyze, detect_format


def laser_nest_bytes():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    for i in range(5):
        rect(msp, 0, i * 300, 1000, 290)
    return to_bytes(doc)


def test_detect_format_by_extension_and_content():
    assert detect_format(b"", "a.DXF") is SourceFormat.DXF
    assert detect_format(b"", "prog.tap") is SourceFormat.GCODE
    assert detect_format(b"", "list.csv") is SourceFormat.CUTLIST
    assert detect_format(b"G21\nG90\nG0 X1 Y1\n", "upload.txt") is SourceFormat.GCODE
    with pytest.raises(JobImportError):
        detect_format(b"\x89PNG....", "photo.png")


def test_dxf_end_to_end_with_inferred_metadata():
    result = analyze(
        laser_nest_bytes(), "Tole_S235_3mm.dxf", AnalysisOptions(process="fiber_laser")
    )
    assert result.material.code == "steel_mild"
    assert result.material_source == "file_name"
    assert result.thickness_mm == 3.0
    assert result.kerf_mm == 0.2
    data = result.to_dict()
    json.dumps(data)  # must be serializable
    sheet = data["sheets"][0]
    assert sheet["part_count"] == 5
    assert sheet["remnants"][0]["id"] == "S1-R1"
    assert sheet["remnants"][0]["width"] == 1999
    # 1999 x 1500 x 3 mm of steel is about 70.6 kg
    assert sheet["remnants"][0]["weight_kg"] == pytest.approx(70.61, rel=1e-3)
    assert data["totals"]["sheet_weight_kg"] == pytest.approx(105.975, rel=1e-3)
    assert "geometry" in sheet and sheet["geometry"]["parts"]


def test_unknown_material_still_returns_geometry_with_warning():
    result = analyze(laser_nest_bytes(), "nest.dxf")
    data = result.to_dict(include_geometry=False)
    assert data["material"] is None
    assert data["sheets"][0]["remnants"][0]["weight_kg"] is None
    assert any("Material" in w for w in data["warnings"])
    assert "geometry" not in data["sheets"][0]


def test_given_options_override_inference():
    opts = AnalysisOptions(material_code="aluminium", thickness_mm=2, kerf_mm=0.5, min_side_mm=50)
    result = analyze(laser_nest_bytes(), "Tole_S235_3mm.dxf", opts)
    assert result.material.code == "aluminium"
    assert result.thickness_mm == 2
    assert result.kerf_mm == 0.5
    assert result.min_side_mm == 50


def test_cut_list_uses_panel_saw_kerf_and_wood_min_side():
    data = b"length,width,qty\n2440,600,1\n"
    result = analyze(data, "mdf_18mm.csv")
    assert result.kerf_mm == 3.2
    assert result.min_side_mm == 150
    assert result.sheets[0].leftover.remnants


def test_router_gcode_defaults_to_tool_kerf():
    program = (
        b"G21 G90\nM3\nG0 X10 Y10\nG1 Z-18\nG1 X300 Y10\nG1 X300 Y200\nG1 X10 Y200\nG1 X10 Y10\n"
    )
    result = analyze(program, "mdf_18mm_2440x1220.nc")
    assert result.kerf_mm == 6.0


def test_rejects_empty_and_unknown_material():
    with pytest.raises(JobImportError):
        analyze(b"   ", "x.dxf")
    with pytest.raises(JobImportError):
        analyze(laser_nest_bytes(), "x.dxf", AnalysisOptions(material_code="unobtainium"))
