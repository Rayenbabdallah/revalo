import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from revalo.engine.importers.common import ImportOptions
from revalo.engine.importers.cutlist import CutPart, guillotine_pack, import_cutlist
from revalo.engine.model import JobImportError, SourceFormat


def assert_valid_layout(job, kerf):
    for sheet in job.sheets:
        outline = sheet.outline
        for part in sheet.parts:
            assert outline.contains(part)
        # parts never overlap, and keep at least a kerf apart
        for i, a in enumerate(sheet.parts):
            for b in sheet.parts[i + 1 :]:
                assert a.distance(b) >= kerf - 1e-6


def test_french_semicolon_cut_list_with_decimal_comma():
    data = (
        "Désignation;Longueur;Largeur;Qté;Fil\n"
        "Côté;720;560;2;non\n"
        "Étagère;764,5;540;3;\n"
        "Fond;764;700;1;\n"
    ).encode("cp1252")
    job = import_cutlist(data, "caisson.csv", ImportOptions(kerf_mm=4))
    assert job.source_format is SourceFormat.CUTLIST
    assert job.layout_estimated
    assert job.part_count == 6
    assert len(job.sheets) == 2  # 87% of one panel's area; guillotine cuts need a second
    assert (job.sheets[0].width, job.sheets[0].height) == pytest.approx((2440, 1220))
    assert any("assumed" in w for w in job.warnings)
    assert_valid_layout(job, kerf=4)


def test_sheet_row_and_english_headers():
    data = b"name,length,width,qty\nsheet,2800,2070,1\nDoor,2000,600,2\nShelf,800,400,4\n"
    job = import_cutlist(data, "wardrobe.csv")
    assert (job.sheets[0].width, job.sheets[0].height) == pytest.approx((2800, 2070))
    assert job.part_count == 6


def test_overflow_goes_to_more_sheets():
    data = b"length,width,qty\n1200,1200,5\n"
    job = import_cutlist(data, "big.csv", ImportOptions(sheet_width_mm=2440, sheet_height_mm=1220))
    assert job.part_count == 5
    assert len(job.sheets) == 3
    assert_valid_layout(job, kerf=3.2)


def test_part_larger_than_panel_is_reported():
    data = b"length,width,qty\n3000,500,1\n400,400,1\n"
    job = import_cutlist(data, "x.csv")
    assert job.part_count == 1
    assert any("larger than the panel" in w for w in job.warnings)


def test_headerless_rows_and_trim():
    data = b"500;300;2;A\n"
    job = import_cutlist(data, "plain.csv", ImportOptions(trim_mm=10, kerf_mm=3))
    xs = sorted(p.bounds[0] for p in job.sheets[0].parts)
    assert xs[0] == pytest.approx(10)


def test_rotation_is_used_only_when_allowed():
    # Length follows the panel's long side (grain direction).
    across_grain = CutPart("a", 100, 1000, rotatable=False)
    sheets, too_big = guillotine_pack([across_grain], 1200, 500, kerf=0, trim=0)
    assert too_big == [across_grain] and not sheets

    free_part = CutPart("b", 100, 1000, rotatable=True)
    sheets, too_big = guillotine_pack([free_part], 1200, 500, kerf=0, trim=0)
    rect = sheets[0][0][1]
    assert not too_big and (rect.w, rect.h) == (1000, 100)


def test_packing_is_dense_enough():
    parts = [CutPart(str(i), 600, 400, True) for i in range(10)]
    sheets, _ = guillotine_pack(parts, 2440, 1220, kerf=3.2, trim=0)
    assert len(sheets) == 1
    used = unary_union([box(r.x, r.y, r.x + r.w, r.y + r.h) for _, r in sheets[0]]).area
    assert used == pytest.approx(10 * 600 * 400)


def test_empty_or_invalid():
    with pytest.raises(JobImportError):
        import_cutlist(b"", "empty.csv")
    with pytest.raises(JobImportError):
        import_cutlist(b"length,width\nabc,def\n", "bad.csv")
