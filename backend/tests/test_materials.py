import pytest

from revalo.engine.materials import (
    default_kerf,
    get_material,
    infer_material,
    infer_process,
    infer_sheet_size,
    infer_thickness,
    materials,
)


def test_library_loads_and_densities_are_sane():
    lib = materials()
    assert "steel_mild" in lib and "mdf" in lib
    for mat in lib.values():
        assert 300 <= mat.density_kg_m3 <= 9000, mat.code


def test_weight_of_a_full_steel_sheet():
    # 3000 x 1500 x 3 mm mild steel is about 106 kg
    steel = get_material("steel_mild")
    assert steel.weight_kg(3000 * 1500, 3) == pytest.approx(105.975, rel=1e-3)


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("job_S235_3mm.dxf", "steel_mild"),
        ("Tole_INOX_304_2mm_3000x1500.dxf", "stainless_304"),
        ("nest-inox316-1.5mm.dxf", "stainless_316"),
        ("ALU 5754 ep2.dxf", "aluminium"),
        ("cuisine_MDF_18mm.csv", "mdf"),
        ("Contreplaqué 15 mm.csv", "plywood"),
        ("galva_1mm.nc", "steel_galvanized"),
        ("bracket_v2.dxf", None),
    ],
)
def test_infer_material(name, code):
    assert infer_material(name) == code


@pytest.mark.parametrize(
    ("name", "thickness"),
    [
        ("job_S235_3mm.dxf", 3.0),
        ("nest-inox316-1.5mm.dxf", 1.5),
        ("ALU 5754 ep2.dxf", 2.0),
        ("panel_t=18.csv", 18.0),
        ("cuisine_MDF_18,5mm.csv", 18.5),
        ("sheet_3000x1500.dxf", None),
    ],
)
def test_infer_thickness(name, thickness):
    assert infer_thickness(name) == thickness


def test_infer_sheet_size():
    assert infer_sheet_size("Tole_INOX_2mm_1500x3000.dxf") == (3000.0, 1500.0)
    assert infer_sheet_size("panneau 2440 x 1220") == (2440.0, 1220.0)
    assert infer_sheet_size("bracket.dxf") is None


def test_default_kerf():
    assert default_kerf("plasma", None) == 1.5
    assert default_kerf(None, "mdf") == 3.2
    assert default_kerf(None, None) == 1.0


@pytest.mark.parametrize(
    ("text", "material", "process"),
    [
        ("plasma_S355_10mm.nc", None, "plasma"),
        ("Laser fibre inox 2mm", "stainless_304", "fiber_laser"),
        ("laser_mdf_3mm.dxf", "mdf", "co2_laser"),
        ("DEFONCEUSE MDF 18", "mdf", "router"),
        ("job_118.dxf", None, None),
    ],
)
def test_infer_process(text, material, process):
    assert infer_process(text, material) == process


def test_every_shipped_price_and_co2_factor_has_a_source():
    for mat in materials().values():
        for block in (mat.price, mat.co2):
            if block is not None:
                assert block.get("source"), mat.code
        if mat.price is not None:
            assert mat.price["new_tnd_per_kg"] > mat.price["scrap_tnd_per_kg"] >= 0
            assert 0 < mat.price["resale_factor"] <= 1


def test_sourced_defaults_match_the_financial_model():
    steel = get_material("steel_mild")
    assert steel.price["new_tnd_per_kg"] == 3.0 and steel.price["scrap_tnd_per_kg"] == 0.27
    mdf = get_material("mdf")
    # 100 TND per 37.5 kg panel
    assert mdf.price["new_tnd_per_kg"] == pytest.approx(100 / 37.5, rel=0.01)
