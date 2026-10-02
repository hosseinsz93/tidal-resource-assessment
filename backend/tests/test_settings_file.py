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
    assert coops.power_curve_mode == "edited"
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


def test_duplicate_keys_rejected(tmp_path):
    path = write_config(tmp_path)
    (tmp_path/path).write_text('{"source":"coops","source":"verdant"}')
    with pytest.raises(ValueError, match='Duplicate'):
        load_settings(tmp_path, path)
