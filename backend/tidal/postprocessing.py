"""Original workflow diagnostics, retained alongside the consolidated analyses.

These functions make historical definitions explicit rather than silently replacing
them with a related statistic. All results use the shared, corrected input tables.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from .analysis import estimate_axis, project, r_squared, contiguous_groups
from .loaders import rotate_heading, speed_scale


def fit_statistics(observed, predicted):
    x, y = np.asarray(observed), np.asarray(predicted)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    r, p = np.nan, np.nan
    if len(x) >= 3 and np.ptp(x) > 0 and np.ptp(y) > 0:
        r, p = pearsonr(x, y)
    return {"r_squared": r_squared(x, y) if len(x) else np.nan,
            "pearson_r": r, "pearson_p_naive": p,
            "rmse_mps": np.sqrt(np.mean((x-y)**2)) if len(x) else np.nan}


def circular_mean(values):
    x = np.deg2rad(np.asarray(values, dtype=float))
    x = x[np.isfinite(x)]
    if not len(x) or np.hypot(np.sin(x).mean(), np.cos(x).mean()) < 1e-10:
        return np.nan
    return float(np.degrees(np.arctan2(np.sin(x).mean(), np.cos(x).mean())) % 360)


def direction_summary(frame):
    rows = []
    for phase in ("FLOOD", "EBB", "SLACK"):
        sub = frame[frame.phase == phase].dropna(subset=["east_mps", "north_mps"])
        direction = np.degrees(np.arctan2(sub.east_mps, sub.north_mps)) % 360
        rows.append({"phase": phase, "samples": len(sub),
                     "mean_speed_mps": sub.speed_mps.mean(),
                     "circular_mean_degT": circular_mean(direction),
                     "arithmetic_mean_degT": direction.mean(),
                     "vector_mean_degT": float(np.degrees(np.arctan2(sub.east_mps.mean(), sub.north_mps.mean())) % 360) if len(sub) else np.nan})
    return pd.DataFrame(rows)


def axis_diagnostics(avg, resolved, bearing, cfg):
    series = avg[["time", "phase", "along_mps"]].rename(columns={"along_mps": "pcu_global_mps"}).copy()
    series["pcu_phase_mps"] = np.nan
    rows, events, depth_rows = [], [], []

    def summarize(sub, scope, reference):
        valid = sub.dropna(subset=["east_mps", "north_mps"])
        row = {"scope": scope, "samples": len(valid), "axis_degT": np.nan, "status": "insufficient vectors"}
        try:
            axis = estimate_axis(valid.east_mps, valid.north_mps, "pca", reference)
        except ValueError as error:
            row["status"] = str(error)
            return row, np.full(len(sub), np.nan)
        pcu, _ = project(sub.east_mps, sub.north_mps, axis)
        absolute = np.abs(pcu)
        row.update({"axis_degT": axis, "status": "ok", "mean_abs_pcu_mps": np.nanmean(absolute),
                    "p95_abs_pcu_mps": np.nanpercentile(absolute, 95), "max_abs_pcu_mps": np.nanmax(absolute),
                    "rms_pcu_mps": np.sqrt(np.nanmean(np.asarray(pcu)**2))})
        return row, np.asarray(pcu)

    row, _ = summarize(avg, "ALL", bearing)
    rows.append(row)
    for phase in ("FLOOD", "EBB"):
        mask = avg.phase.eq(phase)
        reference = bearing if phase == "FLOOD" else (bearing+180) % 360
        row, pcu = summarize(avg.loc[mask], phase, reference)
        rows.append(row)
        series.loc[mask, "pcu_phase_mps"] = pcu if phase == "FLOOD" else -pcu
    for event_id, sub in avg[avg.event_id >= 0].groupby("event_id"):
        phase = sub.phase.iloc[0]
        row, _ = summarize(sub, phase, bearing if phase == "FLOOD" else (bearing+180) % 360)
        row.update({"event_id": event_id, "phase": phase, "start": sub.time.min(), "end": sub.time.max(),
                    "elapsed_hours": (sub.time.max()-sub.time.min()).total_seconds()/3600,
                    "observed_hours": sub.weight_s.sum()/3600})
        events.append(row)
    for bin_id, sub in resolved.groupby("bin"):
        for phase in ("ALL", "FLOOD", "EBB"):
            selected = sub if phase == "ALL" else sub[sub.phase == phase]
            reference = (bearing+180) % 360 if phase == "EBB" else bearing
            row, _ = summarize(selected, phase, reference)
            row.update({"bin": bin_id, "depth_m": sub.depth_m.iloc[0]})
            depth_rows.append(row)
    return {"pcu_time_series": series, "pcu_summary": pd.DataFrame(rows),
            "tidal_events": pd.DataFrame(events), "depth_direction_diagnostics": pd.DataFrame(depth_rows),
            "dominant_directions": direction_summary(avg)}


def resource_metrics(avg, resolved, cfg):
    profile = resolved.groupby("time").agg(peak_profile_speed_mps=("speed_mps", "max"),
                                          mean_profile_speed_mps=("speed_mps", "mean")).reset_index()
    profile = profile.merge(avg[["time", "phase", "weight_s", "speed_mps"]], on="time", validate="one_to_one")
    rows = []
    total = profile.loc[profile.peak_profile_speed_mps.notna(), "weight_s"].sum()
    for phase in ("ALL", "FLOOD", "EBB"):
        sub = profile if phase == "ALL" else profile[profile.phase == phase]
        row = {"phase": phase, "profiles": len(sub), "peak_profile_speed_mps": sub.peak_profile_speed_mps.max(),
               "peak_depth_mean_speed_mps": sub.mean_profile_speed_mps.max(),
               "operating_threshold_mps": cfg.cut_in_mps}
        for label, column in (("peak_profile", "peak_profile_speed_mps"), ("mean_profile", "mean_profile_speed_mps")):
            weights = sub.loc[sub[column] >= cfg.cut_in_mps, "weight_s"]
            row[f"{label}_above_cut_in_hours"] = weights.sum()/3600
            row[f"{label}_above_cut_in_percent_of_record"] = 100*weights.sum()/total if total else np.nan
        rows.append(row)
    per_bin = resolved.groupby("bin").agg(depth_m=("depth_m", "first"), peak_speed_mps=("speed_mps", "max")).reset_index()
    return {"resource_metrics": pd.DataFrame(rows), "bin_peak_speeds": per_bin, "profile_speed_time_series": profile}


def profile_coordinates(resolved, cfg, kind):
    if "height_above_bed_m" not in resolved:
        resolved = resolved.assign(height_above_bed_m=np.nan)
    grid = resolved.groupby("bin").agg(depth_m=("depth_m", "first"),
        height_above_bed_m=("height_above_bed_m", "first"), mean_speed_mps=("speed_mps", "mean")).reset_index().sort_values("bin")
    if cfg.profile_coordinate_mode == "physical":
        if cfg.water_depth_m is None or grid.height_above_bed_m.isna().any():
            grid["eta"] = np.nan
        else:
            grid["eta"] = grid.height_above_bed_m/cfg.water_depth_m
        grid["coordinate_basis"] = "physical z / water depth"
    else:
        valid = grid.mean_speed_mps.notna()
        corr = grid.loc[valid, ["depth_m", "mean_speed_mps"]].corr().iloc[0, 1] if valid.sum() > 1 else np.nan
        if kind == "peak_power":
            # Retain the original 1/N .. 1 rank normalization, ranked by depth_m because bin
            # numbering runs bed-upward for upward-looking ADCPs.
            rank = grid.depth_m.rank(method="first").to_numpy()
            grid["eta"] = (len(grid)-rank+1)/len(grid) if corr < 0 else rank/len(grid)
        else:
            span = grid.depth_m.max()-grid.depth_m.min()
            height = grid.depth_m.max()-grid.depth_m if corr < 0 else grid.depth_m-grid.depth_m.min()
            grid["eta"] = height/span if span > 0 else np.nan
        grid["coordinate_basis"] = "legacy velocity-inferred normalized grid (not physical z/h)"
    return grid


def historical_profile_fits(avg, resolved, cfg):
    """Single record-peak power and log fits, plus phase-mean normalized log fits."""
    peak_grid = profile_coordinates(resolved, cfg, "peak_power")
    log_grid = profile_coordinates(resolved, cfg, "phase_log")
    curves, fits = [], []
    for phase in ("FLOOD", "EBB"):
        subset = resolved[resolved.phase == phase]
        valid = subset.dropna(subset=["speed_mps"])
        if valid.empty:
            for model in ("peak_power", "peak_log", "phase_log"):
                fits.append({"phase": phase, "model": model, "status": "no phase samples"})
            continue
        peak_time = valid.loc[valid.speed_mps.idxmax(), "time"]
        peak = subset[subset.time == peak_time].merge(peak_grid[["bin", "eta", "coordinate_basis"]], on="bin")
        match = avg.loc[avg.time == peak_time, "speed_mps"]
        U = float(match.iloc[0]) if len(match) else np.nan
        if not np.isfinite(U) or U <= 0:
            U = peak.speed_mps.mean()
        for model, frame, reference in (
            ("peak_power", peak, U),
            ("peak_log", peak, U),
            ("phase_log", subset.groupby("bin", as_index=False).agg(speed_mps=("along_mps", "mean")).assign(
                speed_mps=lambda x: x.speed_mps.abs()).merge(log_grid, on="bin", suffixes=("", "_grid")), subset.along_mps.abs().mean()),
        ):
            x, y = frame.eta.to_numpy(), frame.speed_mps.to_numpy()
            good = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
            row = {"phase": phase, "model": model, "reference_U_mps": reference,
                   "peak_time": peak_time if model.startswith("peak_") else pd.NaT,
                   "coordinate_basis": frame.coordinate_basis.iloc[0], "status": "insufficient coordinates or positive speeds"}
            predicted = np.full(len(frame), np.nan)
            chosen = good.copy()
            if model == "phase_log":
                threshold = cfg.near_bed_fraction
                chosen = good & (x <= threshold)
                # Preserve automatic expansion only for the explicitly historical mode.
                while chosen.sum() < 3 and threshold < 1 and cfg.profile_coordinate_mode == "legacy_normalized":
                    threshold = min(1.0, threshold+0.1)
                    chosen = good & (x <= threshold)
                row["near_bed_fraction_used"] = threshold
            if chosen.sum() >= 3 and reference > 0:
                if model == "peak_power":
                    a, b = np.polyfit(np.log(x[chosen]), np.log(y[chosen]/reference), 1)
                    if a > 0:
                        row.update(alpha=1/a, beta=np.exp(-b/a), status="ok")
                        predicted[good] = reference*np.exp(b)*x[good]**a
                    else:
                        row["status"] = "nonpositive power exponent"
                else:
                    a, b = np.polyfit(np.log(x[chosen]), y[chosen], 1)
                    if a > 0:
                        fraction = np.exp(-b/a)
                        row.update(u_star_mps=.41*a, z0_over_h=fraction, status="ok")
                        if 0 < fraction < 1:
                            drag = (.41/np.log(1/fraction))**2
                            row.update(drag_coefficient=drag, u_star_from_drag_mps=np.sqrt(drag)*reference)
                        predicted[good] = a*np.log(x[good])+b
                    else:
                        row["status"] = "nonpositive log slope"
                if row["status"] == "ok":
                    row.update(fit_points=int(chosen.sum()), **fit_statistics(y[chosen], predicted[chosen]))
            fits.append(row)
            curves.append(pd.DataFrame({"phase": phase, "model": model, "bin": frame.bin,
                "depth_m": frame.depth_m, "eta": x, "measured_speed_mps": y,
                "predicted_speed_mps": predicted, "used_for_fit": chosen,
                "coordinate_basis": row["coordinate_basis"], "peak_time": row["peak_time"]}))
    return {"original_profile_fits": pd.DataFrame(fits),
            "original_profile_curves": pd.concat(curves, ignore_index=True) if curves else pd.DataFrame()}


def original_ti(avg, resolved, cfg):
    """Original rolling horizontal-speed denominator and phase-only detrending.

    Retain explicit gap boundaries. This is exported separately from the newer
    along-speed residual measure so the definitions cannot be confused.
    """
    def residuals(frame):
        frame = frame[frame.phase.isin(["FLOOD", "EBB"])].sort_values("time").copy()
        frame["u_prime_mps"], frame["rolling_speed_mps"] = np.nan, np.nan
        if frame.empty:
            return frame
        groups = contiguous_groups(frame.analysis_block, frame.along_mps.notna()) if len(frame) else []
        # analysis_block changes at missing velocities/gaps, not ordinary slack.
        for _, sub in frame.groupby(groups):
            if sub.along_mps.isna().all():
                continue
            rolling = sub.set_index("time")[["along_mps", "speed_mps"]].rolling(f"{cfg.ensemble_minutes}min", min_periods=1).mean()
            frame.loc[sub.index, "u_prime_mps"] = sub.along_mps.to_numpy()-rolling.along_mps.to_numpy()
            frame.loc[sub.index, "rolling_speed_mps"] = rolling.speed_mps.to_numpy()
        return frame

    def summarize(sub, keys):
        sigma = sub.u_prime_mps.std(ddof=1)
        denominator = sub.rolling_speed_mps.mean()
        variance = sigma**2-cfg.noise_std_mps**2
        corrected = np.sqrt(max(variance, 0)) if np.isfinite(sigma) else np.nan
        return {**keys, "samples": sub.u_prime_mps.count(), "mean_speed_ms_used": denominator,
                "std_u_prime_ms": sigma, "sigma_turb_ms": corrected,
                "TI_from_fluct_percent": 100*sigma/denominator if denominator > 0 else np.nan,
                "TI_doppler_corrected_percent": 100*corrected/denominator if denominator > 0 else np.nan,
                "noise_std_mps": cfg.noise_std_mps, "noise_variance_clipped": bool(variance < 0)}
    pieces = [residuals(sub) for _, sub in resolved.groupby("bin")]
    dep = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
    per_bin = pd.DataFrame([summarize(sub, {"bin": b, "phase": phase, "depth_m": sub.depth_m.iloc[0]})
                            for (b, phase), sub in dep.groupby(["bin", "phase"])])
    if len(per_bin):
        grid = profile_coordinates(resolved, cfg, "peak_power")[["bin", "eta", "coordinate_basis"]]
        per_bin = per_bin.merge(grid, on="bin", how="left")
    pooled = [summarize(sub, {"phase": phase}) for phase, sub in dep.groupby("phase")]
    averaged = residuals(avg)
    mean = [summarize(sub, {"phase": phase}) for phase, sub in averaged.groupby("phase")]
    return {"ti_original_by_bin": per_bin, "ti_original_depth_pooled": pd.DataFrame(pooled),
            "ti_original_depth_averaged": pd.DataFrame(mean)}


def cycle_comparisons(tables):
    ensemble = tables["cycle_ensemble"].copy()
    if "mean_mps" not in ensemble:
        return {"cycle_original_fit": pd.DataFrame(), "cycle_comparison": pd.DataFrame()}
    phi = 2*np.pi*ensemble.normalized_time.to_numpy()
    design = np.column_stack([np.cos(phi), np.sin(phi)])
    a, b = np.linalg.lstsq(design, ensemble.mean_mps, rcond=None)[0]
    ensemble["original_no_offset_fit_mps"] = design @ np.array([a, b])
    ensemble["cos_phase"] = np.cos(phi)
    cycles = tables["cycles"]
    ensemble["representative_time"] = cycles.start.iloc[0] + pd.to_timedelta(ensemble.normalized_time * cycles.duration_hours.mean(), unit="h")
    row = {"amplitude_mps": np.hypot(a, b), "phase_shift_deg": np.degrees(np.arctan2(b, a)),
           "cycles": len(cycles), **fit_statistics(ensemble.mean_mps, ensemble.original_no_offset_fit_mps)}
    return {"cycle_original_fit": pd.DataFrame([row]), "cycle_comparison": ensemble}


def energy_direction_tables(resolved, tables, cfg):
    hub = resolved[resolved.bin == cfg.hub_bin].dropna(subset=["along_mps"])
    bins = tables["energy_bins"]
    edges = np.r_[bins.speed_lo_mps, bins.speed_hi_mps.iloc[-1]]
    result = bins[["speed_lo_mps", "speed_hi_mps", "speed_center_mps"]].rename(columns={
        "speed_lo_mps": "U_lo_mps", "speed_hi_mps": "U_hi_mps", "speed_center_mps": "U_center_mps"}).copy()
    for label, mask in (("flood", hub.along_mps > 0), ("ebb", hub.along_mps < 0), ("zero", hub.along_mps == 0)):
        seconds, _ = np.histogram(hub.loc[mask, "along_mps"].abs(), edges, weights=hub.loc[mask, "weight_s"])
        result[f"f_{label}"] = seconds/hub.weight_s.sum()
    result["f_total"] = result[["f_flood", "f_ebb", "f_zero"]].sum(axis=1)
    row = tables["energy_summary"].iloc[0]
    aep = pd.DataFrame([{"aep_kwh": row.aep_kwh, "observed_period_kwh": row.observed_period_kwh,
        "capacity_factor": row.capacity_factor,
        "period_scaled_annual_kwh": row.observed_period_kwh/row.valid_observed_hours*row.hours_per_year}])
    return {"site_probabilities_ebb_flood": result, "turbine_aep_summary": aep}


def orientation_diagnostics(resolved, metadata):
    deployments = {d["file"]: d for d in metadata.get("deployments", [])}
    if not deployments:
        return {"orientation_diagnostics": pd.DataFrame()}
    rows = []
    combined = {"before": [], "after": []}
    for file, sub in resolved.groupby("source_file"):
        vectors = sub.groupby("time")[["east_mps", "north_mps"]].mean().dropna()
        offset = deployments[file]["heading_offset_deg"]
        east, north = rotate_heading(vectors.east_mps, vectors.north_mps, -offset)
        for stage, e, n in (("before", east, north), ("after", vectors.east_mps, vectors.north_mps)):
            direction = np.degrees(np.arctan2(e, n)) % 360
            combined[stage].append(direction)
            rows.append({"source_file": file, "stage": stage, "samples": len(direction),
                "configured_offset_deg": offset, "circular_mean_degT": circular_mean(direction),
                "arithmetic_mean_degT": direction.mean(),
                "axis_degT": estimate_axis(e, n, "doubled_angle", 0) % 180})
    for stage, arrays in combined.items():
        direction = np.concatenate(arrays)
        rows.append({"source_file": "COMBINED", "stage": stage, "samples": len(direction),
            "circular_mean_degT": circular_mean(direction), "arithmetic_mean_degT": np.mean(direction)})
    result = pd.DataFrame(rows)
    target = result.loc[(result.source_file == "COMBINED") & (result.stage == "before"), "circular_mean_degT"].iloc[0]
    result["circular_offset_to_combined_deg"] = (target-result.circular_mean_degT+180)%360-180
    return {"orientation_diagnostics": result}


def compute(assessment, tables, avg, resolved, bearing):
    cfg = assessment.settings
    result = axis_diagnostics(avg, resolved, bearing, cfg)
    result.update(resource_metrics(avg, resolved, cfg))
    result.update(historical_profile_fits(avg, resolved, cfg))
    result.update(original_ti(avg, resolved, cfg))
    result.update(cycle_comparisons(tables))
    result.update(orientation_diagnostics(resolved, assessment.dataset.metadata))
    if "energy_bins" in tables:
        result.update(energy_direction_tables(resolved, tables, cfg))
    result.update(annual_comparisons(assessment.root, cfg))
    return result


def annual_comparisons(root, cfg):
    """Restore the separate annual-event exploration, never treating it as ADCP."""
    if not cfg.compare_annual_records:
        return {}
    from .config import input_file
    try:
        directory = input_file(root, cfg.annual_input_path)
    except FileNotFoundError:
        return {"annual_status": pd.DataFrame([{"status": "annual input folder is absent"}])}
    frames, summaries, ensembles, cycle_rows = [], [], [], []
    for path in sorted(directory.glob("*.csv")):
        raw = pd.read_csv(path)
        raw.columns = raw.columns.str.strip()
        time_col = next((c for c in raw if c.startswith("Date_Time")), None)
        speed_col = next((c for c in raw if c.lower().startswith("speed")), None)
        if time_col is None or speed_col is None:
            raise ValueError(f"Annual file {path.name} needs Date_Time and Speed (units) columns.")
        speed = pd.to_numeric(raw[speed_col], errors="coerce")*speed_scale(speed_col)
        time = pd.to_datetime(raw[time_col], format="%Y-%m-%d %I:%M %p", errors="coerce")
        site = path.stem
        source = pd.DataFrame({"site": site, "time": time, "signed_speed_mps": speed,
                               "time_reference": time_col, "source_file": path.name})
        frames.append(source)
        # As in coops-data.ipynb, only numeric signed peak events enter cycle fitting;
        # missing '-' slack values are not invented as measured zero velocities.
        sub = source.dropna(subset=["time", "signed_speed_mps"]).sort_values("time").reset_index(drop=True)
        summary = {"site": site, "events": len(sub), "peak_abs_speed_mps": sub.signed_speed_mps.abs().max(),
                   "mean_abs_event_speed_mps": sub.signed_speed_mps.abs().mean(), "time_reference": time_col,
                   "source_file": path.name, "data_kind": "nonuniform predicted events; not measured resource", "cycles": 0}
        if len(sub) >= 20:
            u = sub.signed_speed_mps.rolling(3, center=True, min_periods=1).mean().to_numpy()
            crosses = np.flatnonzero((u[:-1] <= 0) & (u[1:] > 0))
            grid = np.linspace(0, 1, 200)
            curves = []
            for a, b in zip(crosses[:-1]+1, crosses[1:]+1):
                hours = (sub.time.iloc[b]-sub.time.iloc[a]).total_seconds()/3600
                if b-a < 2 or not .5 <= hours <= 24:
                    continue
                segment = sub.iloc[a:b]
                t = (segment.time-segment.time.iloc[0]).dt.total_seconds().to_numpy()
                if t[-1] <= 0:
                    continue
                curves.append(np.interp(grid, t/t[-1], segment.signed_speed_mps))
                cycle_rows.append({"site": site, "start": sub.time.iloc[a], "end": sub.time.iloc[b], "duration_hours": hours})
            if curves:
                mean = np.mean(curves, axis=0)
                design = np.column_stack([np.cos(2*np.pi*grid), np.sin(2*np.pi*grid)])
                a, b = np.linalg.lstsq(design, mean, rcond=None)[0]
                fit = design @ np.array([a, b])
                ensembles.append(pd.DataFrame({"site": site, "normalized_time": grid, "cos_phase": np.cos(2*np.pi*grid),
                    "mean_mps": mean, "fit_mps": fit, "std_mps": np.std(curves, axis=0)}))
                summary.update(cycles=len(curves), amplitude_mps=np.hypot(a, b), phase_shift_deg=np.degrees(np.arctan2(b, a)), **fit_statistics(mean, fit))
        summaries.append(summary)
    return {"annual_events": pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(),
            "annual_summary": pd.DataFrame(summaries), "annual_cycles": pd.DataFrame(cycle_rows),
            "annual_cycle_ensemble": pd.concat(ensembles, ignore_index=True) if ensembles else pd.DataFrame()}


CATALOG = [
    ("MATLAB / inputs02 cosine prototypes", "Full-record fixed 12 h 25 min cosine and residuals", "fixed_period_cosine_fit", "(table only)"),
    ("flowVisualized.py", "Mean speeds and dominant-direction compass", "dominant_directions", "_FlowSummary"),
    ("flowVisualized.py", "Signed time series and velocity components", "depth_averaged", "_Time Series"),
    ("flowVisualized.py", "Phase histograms and magnitude box plots", "phase_statistics", "_Statistics"),
    ("flowVisualized.py", "Current rose", "depth_averaged", "current_rose"),
    ("principal_flood_ebb_calculation.ipynb", "Ellipse, signed PDF and CDF", "signed_velocity_distribution", "principal_flow_diagnostics"),
    ("Consolidated workflow", "Bin-level polar velocity, principal axis and phase directions", "depth_resolved", "tidal_velocity_polar"),
    ("principal_flood_ebb_calculation.ipynb", "Peaks and hours above cut-in", "resource_metrics", "(table only)"),
    ("tidal-cycles.ipynb", "Global, phase and event PCU summaries", "pcu_summary", "(table only)"),
    ("tidal-cycles.ipynb", "Per-event axes, duration, RMS and peak PCU", "tidal_events", "(table only)"),
    ("tidal-cycles.ipynb", "Normalized cycles and cosine view", "cycle_original_fit", "cycle_cosine_view"),
    ("tidal-cycles.ipynb", "Single peak ebb/flood power (alpha/beta) and log (u*, z0/h) fits", "original_profile_fits", "Velocity_profiles"),
    ("tidal-cycles.ipynb", "Event profiles and phase-mean normalized log fits", "original_profile_curves", "(table only)"),
    ("TI-calculator.ipynb", "Original raw and corrected TI by bin", "ti_original_by_bin", "TI_original_profiles"),
    ("TI-calculator.ipynb", "Pooled-depth and depth-averaged phase TI", "ti_original_depth_pooled", "(table only)"),
    ("adcp_aep_pcu_iec.ipynb", "Time-weighted hub velocity probability", "energy_bins", "hub_velocity_probability"),
    ("adcp_aep_pcu_iec.ipynb", "Power curve and IEC AEP contribution by speed bin", "energy_bins", "energy_contributions"),
    ("adcp_aep_pcu_iec.ipynb", "Unconditional signed ebb/flood probabilities", "site_probabilities_ebb_flood", "ebb_flood_probabilities"),
    ("adcp_aep_pcu_iec.ipynb", "Single-turbine IEC AEP and observed-period energy", "turbine_aep_summary", "turbine_aep"),
    ("orientation-correction.ipynb", "Before/after deployment heading comparison", "orientation_diagnostics", "(table only)"),
    ("orientation-correction.ipynb", "Separate ebb/flood direction plots", "dominant_directions", "current_rose_ebb_flood"),
    ("coops-data.ipynb", "Annual-event station comparison", "annual_summary", "annual_comparison"),
]


def catalog(tables):
    rows = []
    for original, description, table, figure in CATALOG:
        frame = tables.get(table)
        if frame is None:
            status = "optional analysis disabled or inputs unavailable"
        elif frame.empty:
            status = "not applicable / no eligible samples"
        else:
            status = "available"
        rows.append({"original_workflow": original, "postprocessing": description, "table": table,
                     "figure": figure, "status": status})
    return pd.DataFrame(rows)


def distributions(avg):
    rows = []
    for phase in ("FLOOD", "EBB", "SLACK"):
        sub = avg.loc[avg.phase == phase, "along_mps"].dropna()
        rows.append({"phase": phase, "samples": len(sub), "signed_mean_mps": sub.mean(), "signed_std_mps": sub.std(),
            "magnitude_min_mps": sub.abs().min(), "magnitude_q25_mps": sub.abs().quantile(.25),
            "magnitude_median_mps": sub.abs().median(), "magnitude_q75_mps": sub.abs().quantile(.75),
            "magnitude_max_mps": sub.abs().max()})
    valid = avg.dropna(subset=["along_mps"]).sort_values("along_mps")
    edges = np.linspace(valid.along_mps.min()-.001, valid.along_mps.max()+.001, 41)
    counts, _ = np.histogram(valid.along_mps, edges)
    density = counts / counts.sum() / np.diff(edges)
    hist = pd.DataFrame({"velocity_lo_mps": edges[:-1], "velocity_hi_mps": edges[1:], "pdf": density, "samples": counts})
    cdf = pd.DataFrame({"signed_velocity_mps": valid.along_mps.to_numpy(),
        "sample_cdf": np.arange(1, len(valid)+1)/len(valid), "time_weighted_cdf": valid.weight_s.cumsum().to_numpy()/valid.weight_s.sum()})
    return {"phase_statistics": pd.DataFrame(rows), "signed_velocity_distribution": hist, "signed_velocity_cdf": cdf}


def fixed_period_cosine(avg):
    """Historical fixed-period model, solved deterministically by least squares."""
    valid = avg.dropna(subset=["along_mps"]).copy()
    seconds = (valid.time - valid.time.iloc[0]).dt.total_seconds().to_numpy()
    period = 12*3600 + 25*60
    angle = 2*np.pi*seconds/period
    design = np.column_stack([np.cos(angle), np.sin(angle)])
    a, b = np.linalg.lstsq(design, valid.along_mps, rcond=None)[0]
    fitted = design @ np.array([a, b])
    residual = valid.along_mps.to_numpy()-fitted
    fit = {"amplitude_mps": np.hypot(a, b), "period_seconds": period,
           "phase_origin_seconds": np.mod(np.arctan2(-a, b), 2*np.pi)*period/(2*np.pi),
           "time_origin": valid.time.iloc[0], "max_absolute_error_mps": np.max(np.abs(residual)),
           **fit_statistics(valid.along_mps, fitted)}
    return {"fixed_period_cosine_fit": pd.DataFrame([fit]),
            "fixed_period_cosine_series": pd.DataFrame({"time": valid.time, "observed_mps": valid.along_mps,
                "fitted_mps": fitted, "residual_mps": residual})}
