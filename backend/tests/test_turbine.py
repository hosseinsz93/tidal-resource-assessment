import numpy as np
import pytest
from backend.tidal import Settings, preprocess, process
from backend.tidal.turbine import power_curve
from backend.tidal.notebook import SetupPanel
from test_analysis import synthetic


def test_generated_curve_and_slack_follow_turbine_settings(tmp_path):
    _, cfg = synthetic(tmp_path)
    cfg.cut_in_mps, cfg.rated_speed_mps, cfg.cut_out_mps, cfg.rated_kw = .6, .8, 1.5, 50
    cfg.power_curve_mode, cfg.energy_enabled = "generated", True
    cfg.validate()
    assert cfg.slack_mps == .6
    curve = power_curve(tmp_path, cfg)
    np.testing.assert_allclose(np.interp([0, .6, .8, 1.2], curve.speed_mps, curve.power_kw), [0, 0, 50, 50])
    assessment = process(preprocess(tmp_path, cfg))
    avg = assessment.tables["depth_averaged"]
    assert avg.loc[avg.phase == "SLACK", "along_smoothed_mps"].abs().le(.6).all()
    bins = assessment.tables["energy_bins"]
    assert bins.loc[bins.speed_center_mps < .6, "power_kw"].eq(0).all()
    assert bins.power_kw.max() <= 50


def test_edited_curve_and_invalid_points(tmp_path):
    cfg = Settings(power_curve_mode="edited", power_curve_points="speed_mps,power_kw\n0,0\n2,90\n3.2,90")
    assert power_curve(tmp_path, cfg).power_kw.max() == 90
    cfg.power_curve_points = "speed_mps,power_kw\n1,2\n1,3"
    with pytest.raises(ValueError, match="unique"):
        power_curve(tmp_path, cfg)
    with pytest.raises(ValueError, match="rated speed"):
        Settings(cut_in_mps=2.5, rated_speed_mps=2).validate()


def test_notebook_slack_control_tracks_cut_in(tmp_path):
    panel = SetupPanel(tmp_path)
    panel.controls["cut_in_mps"].value = .7
    assert panel.controls["slack_mps"].disabled
    assert panel.controls["slack_mps"].value == .7
    assert panel.get_settings().slack_mps == .7
