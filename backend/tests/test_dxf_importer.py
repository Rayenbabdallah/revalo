import pytest
from dxf_helpers import new_doc, rect, to_bytes

from revalo.engine.importers.common import ImportOptions
from revalo.engine.importers.dxf import import_dxf
from revalo.engine.model import JobImportError, KerfSide, SourceFormat


def test_sheet_layer_and_parts():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    rect(msp, 10, 10, 500, 300)
    rect(msp, 520, 10, 500, 300)
    msp.add_circle((1500, 750), 100)
    job = import_dxf(to_bytes(doc), "job.dxf")

    assert job.source_format is SourceFormat.DXF
    assert job.kerf_side is KerfSide.OUTSIDE
    assert len(job.sheets) == 1
    sheet = job.sheets[0]
    assert sheet.sheet_detected
    assert (sheet.width, sheet.height) == pytest.approx((3000, 1500))
    assert len(sheet.parts) == 3
    circle = max(sheet.parts, key=lambda p: p.bounds[0])
    assert circle.area == pytest.approx(3.14159 * 100**2, rel=2e-3)


def test_standard_sheet_on_layer_zero_is_detected():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 2500, 1250)
    rect(msp, 10, 10, 400, 400)
    job = import_dxf(to_bytes(doc), "nest.dxf")
    assert job.sheets[0].sheet_detected
    assert len(job.sheets[0].parts) == 1


def test_parts_placed_as_block_references():
    doc = new_doc()
    block = doc.blocks.new("BRACKET")
    block.add_lwpolyline([(0, 0), (200, 0), (200, 100), (0, 100)], close=True)
    block.add_circle((50, 50), 10)
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    for i in range(4):
        msp.add_blockref("BRACKET", (20 + i * 220, 20))
    msp.add_blockref("BRACKET", (1000, 500), dxfattribs={"rotation": 90})
    job = import_dxf(to_bytes(doc), "blocks.dxf")
    parts = job.sheets[0].parts
    assert len(parts) == 5
    assert all(len(p.interiors) == 1 for p in parts)


def test_inch_units_are_converted():
    doc = new_doc(units=1)
    msp = doc.modelspace()
    rect(msp, 0, 0, 48, 24, layer="SHEET")
    rect(msp, 1, 1, 10, 10)
    job = import_dxf(to_bytes(doc), "inch.dxf")
    assert (job.sheets[0].width, job.sheets[0].height) == pytest.approx((1219.2, 609.6))


def test_segments_with_gaps_and_ignored_layers():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 2000, 1000, layer="SHEET")
    msp.add_line((100, 100), (300, 100))
    msp.add_line((300.01, 100), (300, 200))
    msp.add_line((300, 200.02), (100, 200))
    msp.add_line((100, 200), (100, 100.01))
    rect(msp, 500, 500, 50, 50, layer="MARKING")
    msp.add_text("S235 3mm", dxfattribs={"layer": "TEXT"})
    job = import_dxf(to_bytes(doc), "gaps.dxf")
    parts = job.sheets[0].parts
    assert len(parts) == 1
    assert parts[0].area == pytest.approx(200 * 100, rel=1e-3)
    assert "S235 3mm" in job.metadata_text


def test_no_sheet_uses_given_size():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 10, 10, 200, 200)
    rect(msp, 300, 10, 200, 200)
    job = import_dxf(
        to_bytes(doc), "parts.dxf", ImportOptions(sheet_width_mm=1500, sheet_height_mm=3000)
    )
    sheet = job.sheets[0]
    assert not sheet.sheet_detected
    assert (sheet.width, sheet.height) == pytest.approx((3000, 1500))
    assert any("assumed" in w for w in job.warnings)


def test_no_sheet_and_no_size_falls_back_to_bounding_box():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 10, 10, 200, 200)
    rect(msp, 300, 10, 200, 200)
    job = import_dxf(to_bytes(doc), "parts.dxf")
    assert (job.sheets[0].width, job.sheets[0].height) == pytest.approx((490, 200))
    assert any("bounding box" in w for w in job.warnings)


def test_plate_with_holes_is_a_part_not_a_sheet():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 300, 200)
    for x, y in [(30, 30), (270, 30), (30, 170), (270, 170)]:
        msp.add_circle((x, y), 8)
    job = import_dxf(to_bytes(doc), "flange.dxf")
    assert not job.sheets[0].sheet_detected
    assert len(job.sheets[0].parts) == 1
    assert len(job.sheets[0].parts[0].interiors) == 4


def test_two_sheets_in_one_file():
    doc = new_doc()
    msp = doc.modelspace()
    for ox in (0, 3500):
        rect(msp, ox, 0, 3000, 1500)
        rect(msp, ox + 10, 10, 800, 600)
    job = import_dxf(to_bytes(doc), "two.dxf")
    assert len(job.sheets) == 2
    assert all(len(s.parts) == 1 for s in job.sheets)
    assert all(s.outline.bounds[0] == pytest.approx(0) for s in job.sheets)


def test_rotated_sheet_is_normalized():
    doc = new_doc()
    msp = doc.modelspace()
    block = doc.blocks.new("NEST")
    rect(block, 0, 0, 3000, 1500, layer="SHEET")
    rect(block, 100, 100, 500, 500)
    msp.add_blockref("NEST", (1000, 1000), dxfattribs={"rotation": 30})
    job = import_dxf(to_bytes(doc), "rotated.dxf")
    sheet = job.sheets[0]
    assert sheet.outline.bounds == pytest.approx((0, 0, 3000, 1500), abs=0.01)
    assert sheet.parts[0].area == pytest.approx(250000, rel=1e-6)


def test_garbage_raises_import_error():
    with pytest.raises(JobImportError):
        import_dxf(b"this is not a dxf", "bad.dxf")


def test_construction_and_machine_bed_layers_are_ignored():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 2440, 1220, layer="bed 4x8")
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    for i in range(5):
        rect(msp, 100 + i * 10, 100 + i * 10, 800 - i * 20, 600 - i * 20, layer="construction")
    rect(msp, 50, 50, 300, 200, layer="CUT")
    rect(msp, 60, 60, 280, 0.5, layer="BEND")
    job = import_dxf(to_bytes(doc), "job.dxf")
    assert len(job.sheets) == 1
    assert len(job.sheets[0].parts) == 1


def test_overlapping_sheet_outlines_are_alternatives():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 2464, 1245, layer="sheet 49x97")
    rect(msp, 0, 0, 2464, 1549, layer="sheet 61x97")
    rect(msp, 0, 0, 2464, 1854, layer="sheet 73x97")
    rect(msp, 10, 10, 500, 500)
    job = import_dxf(to_bytes(doc), "alt.dxf")
    assert len(job.sheets) == 1
    assert (job.sheets[0].width, job.sheets[0].height) == pytest.approx((2464, 1245))
    assert any("overlapping sheet outlines" in w for w in job.warnings)


def test_layer_names_only_partly_matching_sheet_are_parts():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    rect(msp, 10, 10, 400, 300, layer="plated")
    rect(msp, 500, 10, 400, 300, layer="door panel")
    job = import_dxf(to_bytes(doc), "names.dxf")
    assert len(job.sheets) == 1
    assert len(job.sheets[0].parts) == 2


def test_parts_crossing_the_sheet_edge_are_reported():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 2000, 1000, layer="SHEET")
    rect(msp, 10, 10, 100, 100)
    rect(msp, -20, 500, 100, 100)
    job = import_dxf(to_bytes(doc), "edge.dxf")
    assert any("cross the sheet edge" in w for w in job.warnings)


def test_nest_in_non_standard_sheet_with_holed_parts_is_detected():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 1700, 900)
    for i in range(3):
        rect(msp, 20 + i * 520, 20, 500, 400)
        msp.add_circle((270 + i * 520, 220), 40)
    job = import_dxf(to_bytes(doc), "custom.dxf")
    assert job.sheets[0].sheet_detected
    assert len(job.sheets[0].parts) == 3
