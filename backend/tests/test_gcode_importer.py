import math

import pytest

from revalo.engine.importers.common import ImportOptions
from revalo.engine.importers.gcode import import_gcode
from revalo.engine.model import JobImportError, KerfSide, SourceFormat

SHEET = ImportOptions(sheet_width_mm=1000, sheet_height_mm=500)


def run(program: str, options: ImportOptions = SHEET, name: str = "job.nc"):
    return import_gcode(program.encode(), name, options)


def test_square_with_spindle_switch():
    job = run(
        """
        (Material: S235 3mm)
        G21 G90
        G0 X10 Y10
        M3
        G1 X110 Y10 F1000
        G1 X110 Y60
        G1 X10 Y60
        G1 X10 Y10
        M5
        G0 X0 Y0
        """
    )
    assert job.source_format is SourceFormat.GCODE
    assert job.kerf_side is KerfSide.CENTERED
    parts = job.sheets[0].parts
    assert len(parts) == 1
    assert parts[0].area == pytest.approx(100 * 50)
    assert "S235 3mm" in job.metadata_text


def test_full_circle_with_ij():
    job = run(
        """
        G21 G90
        G0 X200 Y100
        M3
        G2 X200 Y100 I-50 J0
        M5
        """
    )
    area = job.sheets[0].parts[0].area
    assert area == pytest.approx(math.pi * 50**2, rel=2e-3)


def test_arc_with_radius_word_and_lines():
    # Slot shape: two straight sides joined by half circles of radius 20.
    job = run(
        """
        G21 G90
        G0 X100 Y100
        M3
        G1 X200 Y100
        G3 X200 Y140 R20
        G1 X100 Y140
        G3 X100 Y100 R20
        M5
        """
    )
    expected = 100 * 40 + math.pi * 20**2
    assert job.sheets[0].parts[0].area == pytest.approx(expected, rel=3e-3)


def test_inches_and_incremental_moves():
    job = run(
        """
        G20 G91
        G0 X1 Y1
        M3
        G1 X2
        G1 Y1
        G1 X-2
        G1 Y-1
        M5
        """
    )
    assert job.sheets[0].parts[0].area == pytest.approx(50.8 * 25.4, rel=1e-6)


def test_router_only_full_depth_passes_count():
    # A shallow pocket (Z-2) and a through profile cut in two passes (Z-9, Z-18).
    job = run(
        """
        G21 G90
        M3 S18000
        G0 Z5
        G0 X50 Y50
        G1 Z-2
        G1 X80 Y50
        G1 X80 Y80
        G1 X50 Y80
        G1 X50 Y50
        G0 Z5
        G0 X200 Y200
        G1 Z-9
        G1 X400 Y200
        G1 X400 Y300
        G1 X200 Y300
        G1 X200 Y200
        G1 Z-18
        G1 X400 Y200
        G1 X400 Y300
        G1 X200 Y300
        G1 X200 Y200
        G0 Z5
        M5
        """
    )
    parts = job.sheets[0].parts
    assert len(parts) == 1
    assert parts[0].area == pytest.approx(200 * 100)


def test_plasma_m07_m08_convention():
    job = run(
        """
        G21 G90
        G0 X10 Y10
        M07
        G1 X60 Y10
        G1 X60 Y60
        G1 X10 Y60
        G1 X10 Y10
        M08
        G0 X300 Y300
        G1 X400 Y300
        """
    )
    assert len(job.sheets[0].parts) == 1


def test_contour_with_lead_in_is_closed():
    # Pierce inside the hole area, lead in to the contour, cut around, stop at the entry.
    job = run(
        """
        G21 G90
        G0 X40 Y30
        M07
        G1 X50 Y30
        G1 X50 Y10
        G1 X150 Y10
        G1 X150 Y110
        G1 X50 Y110
        G1 X50 Y30
        M08
        """
    )
    parts = job.sheets[0].parts
    assert len(parts) == 1
    assert parts[0].area == pytest.approx(100 * 100)


def test_sheet_size_from_file_name():
    job = run(
        "G21 G90\nG0 X10 Y10\nG1 X60 Y10\nG1 X60 Y60\nG1 X10 Y60\nG1 X10 Y10\n",
        options=ImportOptions(),
        name="mdf_18mm_2440x1220.nc",
    )
    sheet = job.sheets[0]
    assert (sheet.width, sheet.height) == pytest.approx((2440, 1220))


def test_not_gcode():
    with pytest.raises(JobImportError):
        run("hello world\nthis is text")
