import json
from pathlib import Path
import pytest
from backend.tidal import load_settings
from backend.tidal.turbine import power_curve


def write_config(tmp_path, **changes):
    path = tmp_path/'inputs'/'config.json'
    path.parent.mkdir(exist_ok=True)
    data = dict(source="standard_csv", site="Test", input_path="inputs/test.csv", energy_enabled=False)
    data.update(changes)
    path.write_text(json.dumps(data))
    return "inputs/config.json"


def test_examples_and_edited_points(tmp_path):
    root = Path(__file__).resolve().parents[2]
    coops = load_settings(root)
    assert coops.slack_mps == coops.cut_in_mps
    assert coops.power_curve_mode == "generated"
    assert power_curve(root, coops).power_kw.max() == coops.rated_kw
    path = write_config(tmp_path, energy_enabled=True, power_curve_mode="edited",
                        power_curve_points=[[0,0],[2,100],[3.2,100]], cut_in_mps=.6)
    cfg = load_settings(tmp_path, path)
    assert cfg.slack_mps == .6
    assert power_curve(tmp_path, cfg).power_kw.max() == 100


@pytest.mark.parametrize('changes,match', [({'typo':1}, 'Unknown'), ({'cut_in_mps':'0.4'}, 'type'),
    ({'energy_enabled':'false'}, 'type'), ({'excluded_bins':[True]}, 'type'),
    ({'slack_mps':.7}, 'Slack equals'), ({'power_curve_points':[[0,'bad'],[1,2]]}, 'numbers')])
def test_actionable_json_errors(tmp_path, changes, match):
    with pytest.raises(ValueError, match=match):
        load_settings(tmp_path, write_config(tmp_path, **changes))


def test_sectioned_config_flattens(tmp_path):
    path = write_config(tmp_path)
    (tmp_path / path).write_text(json.dumps({
        "data_and_quality": {"source": "standard_csv", "site": "Test", "input_path": "inputs/test.csv"},
        "turbine_and_power": {"energy_enabled": False, "cut_in_mps": 0.5},
    }))
    cfg = load_settings(tmp_path, path)
    assert cfg.site == "Test"
    assert cfg.energy_enabled is False
    assert cfg.cut_in_mps == 0.5
    (tmp_path / path).write_text(json.dumps({
        "data_and_quality": {"site": "Test"},
        "comparisons": {"site": "Other"},
    }))
    with pytest.raises(ValueError, match="Duplicate"):
        load_settings(tmp_path, path)


@pytest.mark.parametrize('sheets,site,offsets,bins,depth', [
    (["Station A", "Station A-2"], "Verdant_A", (-0.07, 0.04), (39, 40, 41, 42, 43), 24.0),
    (["Station B", "Station B-2"], "Verdant_B", (-5.53, 3.2), (45, 46, 47, 48, 49), 26.9)])
def test_verdant_station_preset_follows_sheets(tmp_path, sheets, site, offsets, bins, depth):
    from backend.tidal.config import output_run_name, output_station_tag
    cfg = load_settings(tmp_path, write_config(tmp_path, source="verdant", site="LIS1016", verdant_sheets=sheets))
    assert cfg.site == site
    assert cfg.verdant_heading_offsets == offsets
    assert cfg.excluded_bins == bins
    assert cfg.water_depth_m == depth
    assert output_station_tag(cfg) == site.replace("Verdant_", "Station")
    assert output_run_name(cfg, "stamp") == f"{site}_verdant_{output_station_tag(cfg)}_stamp"
    cfg = load_settings(tmp_path, write_config(tmp_path, source="verdant", verdant_sheets=sheets, water_depth_m=20.0))
    assert cfg.water_depth_m == 20.0


def test_unknown_verdant_sheets_need_explicit_values(tmp_path):
    with pytest.raises(ValueError, match="No station preset"):
        load_settings(tmp_path, write_config(tmp_path, source="verdant", verdant_sheets=["Station C"]))


def test_lis1016_uses_verified_noaa_deployment_metadata(tmp_path):
    cfg = load_settings(tmp_path, write_config(
        tmp_path, source="coops", site="LIS1016", coops_depth_reference="unknown",
        water_depth_m=37.8, flood_reference_deg=252.38))
    assert cfg.coops_depth_reference == "below_surface"
    assert cfg.coops_adcp_orientation == "upward"
    assert cfg.coops_nominal_water_depth_m == pytest.approx(47.0)
    assert cfg.water_depth_m == pytest.approx(47.18)
    assert cfg.coops_instrument_height_above_bed_m == pytest.approx(5.18)
    assert cfg.coops_bin1_center_distance_m == pytest.approx(4.23)
    assert cfg.coops_bin_size_m == pytest.approx(2.0)
    assert cfg.flood_reference_deg == pytest.approx(250.0)
    assert cfg.near_bed_fraction == pytest.approx(0.30)


def test_duplicate_keys_rejected(tmp_path):
    path = write_config(tmp_path)
    (tmp_path/path).write_text('{"source":"coops","source":"verdant"}')
    with pytest.raises(ValueError, match='Duplicate'):
        load_settings(tmp_path, path)
