"""Checks of restored historical definitions against independent references."""
import numpy as np
import pandas as pd
import pytest
from backend.tidal import preprocess, process
from backend.tidal.config import Settings
from backend.tidal.plots import figure_prefix, FIGURE_ORDER
from backend.tidal.original_plots import _cardinal_direction, _phase_polar_statistics, _polar_title
from backend.tidal.postprocessing import fixed_period_cosine, original_ti
from test_analysis import synthetic


def test_figure_titles_follow_the_data_source():
    assert figure_prefix(Settings(source="verdant", site="LIS1016")) == "Verdant Power"
    assert figure_prefix(Settings(source="coops", site="LIS1016")) == "NOAA CO-OPS · LIS1016"
    assert figure_prefix(Settings(source="standard_csv", site="MySite")) == "Standard CSV · MySite"
    assert _polar_title(Settings(source="verdant", verdant_sheets=("Station A", "Station A-2"))) == \
        "Verdant Power · Tidal Velocity Polar Plot (Station A)"
    assert _polar_title(Settings(source="verdant", verdant_sheets=("Station B", "Station B-2"))) == \
        "Verdant Power · Tidal Velocity Polar Plot (Station B)"
    assert _polar_title(Settings(source="coops", site="LIS1016")) == \
        "NOAA CO-OPS · LIS1016 · Tidal Velocity Polar Plot"
    assert FIGURE_ORDER.index("tidal_velocity_polar") == FIGURE_ORDER.index("principal_flow_diagnostics") + 1


def test_polar_statistics_use_canonical_vectors_for_any_source():
    frame = pd.DataFrame({"phase": ["FLOOD", "FLOOD", "EBB", "EBB"],
                          "direction_degT": [70, 80, 250, 260],
                          "speed_mps": [1.0, 2.0, 1.2, 1.8]})
    axis, rows = _phase_polar_statistics(frame, 255)
    result = pd.DataFrame(rows).set_index("phase")
    assert axis == pytest.approx(75)
    assert result.loc["FLOOD", "direction_degT"] == pytest.approx(75)
    assert result.loc["EBB", "direction_degT"] == pytest.approx(255)
    assert result.loc["FLOOD", "mean_speed_mps"] == pytest.approx(1.5)
    assert _cardinal_direction(75) == "ENE"
    assert _cardinal_direction(255) == "WSW"


def test_fixed_period_model_recovers_amplitude_and_phase():
    seconds = np.arange(800)*360
    phase = 4200
    velocity = 1.7*np.sin(2*np.pi*(seconds-phase)/44700)
    result = fixed_period_cosine(pd.DataFrame({"time": pd.Timestamp("2024-01-01")+pd.to_timedelta(seconds, unit="s"), "along_mps": velocity}))
    fit = result["fixed_period_cosine_fit"].iloc[0]
    assert fit.amplitude_mps == pytest.approx(1.7)
    assert fit.phase_origin_seconds == pytest.approx(phase)
    assert fit.rmse_mps < 1e-12


def test_original_ti_uses_horizontal_speed_denominator(tmp_path):
    _, cfg = synthetic(tmp_path)
    time = pd.date_range("2024-01-01", periods=20, freq="6min")
    along = np.linspace(.2, 1.5, 20)
    frame = pd.DataFrame({"time": time, "along_mps": along, "speed_mps": np.hypot(along, .5),
                          "phase": "FLOOD", "analysis_block": 0, "bin": 1, "depth_m": 1})
    cfg.noise_std_mps = .02
    actual = original_ti(frame, frame, cfg)["ti_original_by_bin"].iloc[0]
    window = frame.set_index("time")[["along_mps", "speed_mps"]].rolling("60min", min_periods=1).mean()
    sigma = np.std(along-window.along_mps.to_numpy(), ddof=1)
    denominator = window.speed_mps.mean()
    assert actual.TI_from_fluct_percent == pytest.approx(100*sigma/denominator)
    assert actual.TI_doppler_corrected_percent == pytest.approx(100*np.sqrt(sigma**2-.02**2)/denominator)


def test_restored_profiles_resource_metrics_and_distributions(tmp_path):
    _, cfg = synthetic(tmp_path)
    result = process(preprocess(tmp_path, cfg))
    t = result.tables
    fits = t["original_profile_fits"].query("model == 'peak_power'")
    np.testing.assert_allclose(fits.alpha, 5, rtol=1e-6)
    assert fits.status.eq("ok").all()
    log_fits = t["original_profile_fits"].query("model == 'peak_log'")
    assert len(log_fits) == 2 and log_fits.status.eq("ok").all()
    assert (log_fits.u_star_mps > 0).all() and log_fits.z0_over_h.between(0, 1).all()
    all_metrics = t["resource_metrics"].query("phase == 'ALL'").iloc[0]
    profile = t["profile_speed_time_series"]
    expected = profile.loc[profile.peak_profile_speed_mps >= cfg.cut_in_mps, "weight_s"].sum()/3600
    assert all_metrics.peak_profile_above_cut_in_hours == pytest.approx(expected)
    hist = t["signed_velocity_distribution"]
    assert np.sum(hist.pdf*(hist.velocity_hi_mps-hist.velocity_lo_mps)) == pytest.approx(1)
    assert t["signed_velocity_cdf"].time_weighted_cdf.iloc[-1] == pytest.approx(1)
    assert len(t["postprocessing_catalog"]) == 21
    assert t["cycle_original_fit"].iloc[0].r_squared > .999
