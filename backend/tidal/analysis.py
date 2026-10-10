"""Shared calculations. No source-specific column positions or implicit units."""
import numpy as np
import pandas as pd

HOURS_PER_YEAR = 8766


def time_support(times, gap_factor=1.5):
    """Forward sample support, capped at nominal cadence across gaps and at end.

    Timestamps are ensemble starts. Gaps are not assigned to the adjacent sample.
    Returns a block ID so smoothing and cycle extraction never span a gap.
    """
    t = pd.DatetimeIndex(times)
    if len(t) < 2 or not t.is_monotonic_increasing or t.has_duplicates:
        raise ValueError("Time support requires at least two unique, sorted timestamps.")
    seconds = (t[1:] - t[:-1]).total_seconds().to_numpy()
    nominal = float(np.median(seconds))
    gaps = seconds > gap_factor * nominal
    weights = np.r_[np.where(gaps, nominal, seconds), nominal]
    return weights, np.r_[0, np.cumsum(gaps)].astype(int), nominal


def depth_average(data, settings):
    count = int(data.bin.nunique())
    avg = data.groupby("time", sort=True).agg(
        east_mps=("east_mps", "mean"), north_mps=("north_mps", "mean"),
        valid_bins=("valid_velocity", "sum"), mean_bin_speed_mps=("speed_mps", "mean"),
    ).reset_index()
    avg["bin_coverage"] = avg.valid_bins / count
    missing = avg.bin_coverage < settings.min_bin_coverage
    avg.loc[missing, ["east_mps", "north_mps", "mean_bin_speed_mps"]] = np.nan
    avg["speed_mps"] = np.hypot(avg.east_mps, avg.north_mps)
    avg["direction_degT"] = np.degrees(np.arctan2(avg.east_mps, avg.north_mps)) % 360
    weights, blocks, nominal = time_support(avg.time, settings.gap_factor)
    avg["weight_s"], avg["block"] = weights, blocks
    return avg, nominal


def estimate_axis(east, north, method="pca", reference=252.38):
    east, north = np.asarray(east), np.asarray(north)
    good = np.isfinite(east) & np.isfinite(north) & (np.hypot(east, north) > 0)
    if good.sum() < 3:
        raise ValueError("At least three valid, nonzero vectors are required for an axis estimate.")
    if method == "pca":
        cov = np.cov(np.vstack([east[good], north[good]]))
        values, vectors = np.linalg.eigh(cov)
        if values[-1] <= 0 or np.isclose(values[0], values[-1], rtol=1e-3, atol=1e-12):
            raise ValueError("There is no well-defined principal axis; try axis_method 'doubled_angle'.")
        direction = vectors[:, -1]
        bearing = np.degrees(np.arctan2(direction[0], direction[1])) % 360
    elif method == "doubled_angle":
        theta = np.arctan2(east[good], north[good])
        s, c = np.sin(2 * theta).mean(), np.cos(2 * theta).mean()
        if np.hypot(s, c) < 1e-6:
            raise ValueError("Doubled-angle direction is undefined; try axis_method 'pca'.")
        bearing = np.degrees(0.5 * np.arctan2(s, c)) % 360
    else:
        raise ValueError(f"Unknown axis method: {method}")
    options = (bearing, (bearing + 180) % 360)
    return float(min(options, key=lambda b: abs((b - reference + 180) % 360 - 180)))


def project(east, north, bearing):
    phi = np.deg2rad(bearing)
    return east * np.sin(phi) + north * np.cos(phi), east * np.cos(phi) - north * np.sin(phi)


def contiguous_groups(blocks, valid):
    """Separate missing runs as well as time gaps."""
    b, v = np.asarray(blocks), np.asarray(valid, dtype=bool)
    return np.cumsum(np.r_[True, (b[1:] != b[:-1]) | (v[1:] != v[:-1])])


def classify(avg, data, settings):
    avg = avg.copy()
    bearing = estimate_axis(avg.east_mps, avg.north_mps, settings.axis_method, settings.flood_reference_deg)
    avg["along_mps"], avg["across_mps"] = project(avg.east_mps, avg.north_mps, bearing)
    avg["analysis_block"] = contiguous_groups(avg.block, avg.along_mps.notna())
    avg["along_smoothed_mps"] = avg.groupby("analysis_block").along_mps.transform(
        lambda x: x.rolling(settings.smooth_samples, center=True, min_periods=1).mean())
    avg["phase"] = np.select(
        [avg.along_mps.isna(), avg.along_smoothed_mps > settings.slack_mps,
         avg.along_smoothed_mps < -settings.slack_mps],
        ["MISSING", "FLOOD", "EBB"], default="SLACK")
    changes = avg.phase.ne(avg.phase.shift()) | avg.analysis_block.ne(avg.analysis_block.shift())
    avg["event_id"] = changes.cumsum() - 1
    avg.loc[~avg.phase.isin(["FLOOD", "EBB"]), "event_id"] = -1
    resolved = data.copy()
    resolved["along_mps"], resolved["across_mps"] = project(resolved.east_mps, resolved.north_mps, bearing)
    resolved = resolved.merge(avg[["time", "phase", "event_id", "analysis_block", "weight_s"]], on="time", validate="many_to_one")
    # Phase is a record-wide label inherited from the depth average, including at
    # bins where the local velocity is unavailable. valid_velocity remains explicit.
    return avg, resolved, bearing


def phase_summary(avg, bearing, settings):
    rows = []
    total = avg.weight_s.sum()
    for phase in ("FLOOD", "EBB", "SLACK", "MISSING"):
        sub = avg[avg.phase == phase]
        axis = np.nan
        if phase in {"FLOOD", "EBB"} and len(sub) >= 3:
            try:
                axis = estimate_axis(sub.east_mps, sub.north_mps, settings.axis_method,
                                     bearing if phase == "FLOOD" else (bearing + 180) % 360)
            except ValueError:
                pass
        rows.append({"phase": phase, "samples": len(sub), "observed_hours": sub.weight_s.sum()/3600,
                     "observed_time_fraction": sub.weight_s.sum()/total,
                     "mean_speed_mps": sub.speed_mps.mean(), "peak_speed_mps": sub.speed_mps.max(),
                     "phase_axis_degT": axis})
    return pd.DataFrame(rows)


def tidal_cycles(avg, settings, points=200):
    grid = np.linspace(0, 1, points)
    curves, records = [], []
    for block_id, sub in avg.groupby("analysis_block"):
        if sub.along_mps.isna().any():
            continue
        u = sub.along_smoothed_mps.to_numpy()
        times = (sub.time - sub.time.iloc[0]).dt.total_seconds().to_numpy()
        cross = np.flatnonzero((u[:-1] <= 0) & (u[1:] > 0))
        crossing_times = times[cross] - u[cross] * (times[cross+1] - times[cross]) / (u[cross+1] - u[cross])
        for a, b in zip(crossing_times[:-1], crossing_times[1:]):
            hours = (b - a) / 3600
            if not settings.min_cycle_hours <= hours <= settings.max_cycle_hours:
                continue
            cycle_id = len(records)
            y = np.interp(a + grid * (b-a), times, sub.along_mps)
            curves.append(y)
            records.append({"cycle_id": cycle_id, "block": block_id,
                            "start": sub.time.iloc[0] + pd.Timedelta(seconds=a),
                            "end": sub.time.iloc[0] + pd.Timedelta(seconds=b), "duration_hours": hours})
    cycles = pd.DataFrame(records, columns=["cycle_id", "block", "start", "end", "duration_hours"])
    ensemble = pd.DataFrame({"normalized_time": grid})
    if not curves:
        return cycles, ensemble, pd.DataFrame(), pd.DataFrame()
    matrix = np.asarray(curves)
    phi = 2*np.pi*grid
    design = np.column_stack([np.ones(points), np.cos(phi), np.sin(phi)])
    mean = matrix.mean(axis=0)
    offset, a, b = np.linalg.lstsq(design, mean, rcond=None)[0]
    fitted = design @ np.array([offset, a, b])
    ensemble["mean_mps"], ensemble["std_mps"], ensemble["fit_mps"] = mean, matrix.std(axis=0), fitted
    metrics = pd.DataFrame([{"cycles": len(cycles), "offset_mps": offset,
                             "amplitude_mps": np.hypot(a, b), "phase_shift_deg": np.degrees(np.arctan2(b, a)),
                             "r_squared": r_squared(mean, fitted), "rmse_mps": np.sqrt(np.mean((mean-fitted)**2))}])
    members = pd.DataFrame(matrix.T, columns=[f"cycle_{i}" for i in range(len(curves))])
    members.insert(0, "normalized_time", grid)
    return cycles, ensemble, metrics, members


def r_squared(observed, predicted):
    observed, predicted = np.asarray(observed), np.asarray(predicted)
    residual = np.sum((observed-predicted)**2)
    total = np.sum((observed-observed.mean())**2)
    return 1 - residual/total if total > 0 else np.nan


def profiles(resolved, settings):
    active = resolved[resolved.phase.isin(["FLOOD", "EBB"])]
    summary = active.groupby(["phase", "bin", "depth_m", "depth_reference"], observed=True).agg(
        mean_along_mps=("along_mps", "mean"), std_along_mps=("along_mps", "std"),
        mean_speed_mps=("speed_mps", "mean"), max_speed_mps=("speed_mps", "max"),
        height_above_bed_m=("height_above_bed_m", "first"), samples=("along_mps", "count")
    ).reset_index()
    peaks = active.dropna(subset=["along_mps"]).copy()
    if len(peaks):
        peaks["absolute_along"] = peaks.along_mps.abs()
        index = peaks.groupby("event_id").absolute_along.idxmax()
        peak_times = peaks.loc[index, ["event_id", "time"]]
        peaks = active.merge(peak_times, on=["event_id", "time"], validate="many_to_one")
    fits, fitted_curves = [], []
    for phase, sub in summary.groupby("phase"):
        sign = 1 if phase == "FLOOD" else -1
        z = sub.height_above_bed_m.to_numpy()
        u = sub.mean_along_mps.to_numpy() * sign
        valid = np.isfinite(z) & np.isfinite(u) & (z > 0) & (u > 0)
        if valid.sum() < 3:
            fits.append({"phase": phase, "model": "power", "status": "needs at least 3 valid heights above bed"})
            fits.append({"phase": phase, "model": "log", "status": "needs confirmed bed heights and total water depth"})
            continue
        slope, intercept = np.polyfit(np.log(z[valid]), np.log(u[valid]), 1)
        predicted = np.full(len(z), np.nan)
        if slope > 0:
            predicted[valid] = np.exp(intercept)*z[valid]**slope
            row = {"phase": phase, "model": "power", "status": "ok", "alpha": 1/slope,
                   "coefficient": np.exp(intercept), "fit_points": int(valid.sum()),
                   "r_squared": r_squared(u[valid], predicted[valid]),
                   "rmse_mps": np.sqrt(np.mean((u[valid]-predicted[valid])**2))}
            # beta is normalized to the observed-bin mean, not a measured bed roughness.
            if settings.water_depth_m is not None:
                U = u[valid].mean()
                row["reference_mean_mps"] = U
                row["beta"] = (U/np.exp(intercept))**(1/slope)/settings.water_depth_m
            fits.append(row)
            fitted_curves.append(pd.DataFrame({"phase": phase, "bin": sub.bin, "height_above_bed_m": z,
                                               "model": "power", "predicted_speed_mps": predicted}))
        else:
            fits.append({"phase": phase, "model": "power", "status": "nonpositive exponent; inspect profile"})
        if settings.water_depth_m is None:
            fits.append({"phase": phase, "model": "log", "status": "total water depth needed to select near-bed region"})
            continue
        near = valid & (z/settings.water_depth_m <= settings.near_bed_fraction)
        if near.sum() < 3:
            fits.append({"phase": phase, "model": "log", "status": "fewer than 3 near-bed bins; no automatic window expansion"})
            continue
        a, b = np.polyfit(np.log(z[near]), u[near], 1)
        if a <= 0:
            fits.append({"phase": phase, "model": "log", "status": "nonpositive log slope; inspect profile"})
            continue
        fitted = a*np.log(z[near])+b
        fits.append({"phase": phase, "model": "log", "status": "ok", "u_star_mps": 0.41*a,
                     "z0_m": np.exp(-b/a), "fit_points": int(near.sum()),
                     "r_squared": r_squared(u[near], fitted), "rmse_mps": np.sqrt(np.mean((u[near]-fitted)**2))})
        fitted_curves.append(pd.DataFrame({"phase": phase, "bin": sub.bin.to_numpy()[near],
                                          "height_above_bed_m": z[near], "model": "log", "predicted_speed_mps": fitted}))
    return summary, peaks, pd.DataFrame(fits), pd.concat(fitted_curves, ignore_index=True) if fitted_curves else pd.DataFrame()


def turbulence(resolved, avg, settings):
    """Rolling residual variability, not burst-resolved turbulence from coarse ensembles.

    Retain slack in detrending; reduce by phase only AFTER constructing residuals.
    Require three samples and at least 80% of the configured window duration.
    """
    def calculate(frame, keys):
        frame = frame.sort_values("time").copy()
        groups = contiguous_groups(frame.analysis_block, frame.along_mps.notna())
        frame["residual"] = np.nan
        for _, indices in frame.groupby(groups).groups.items():
            sub = frame.loc[indices]
            if sub.along_mps.isna().any():
                continue
            series = sub.set_index("time").along_mps
            mean = series.rolling(f"{settings.ensemble_minutes}min", min_periods=3).mean()
            ready = (sub.time - sub.time.iloc[0]).dt.total_seconds() >= 0.8*settings.ensemble_minutes*60
            frame.loc[indices, "residual"] = np.where(ready, series.to_numpy()-mean.to_numpy(), np.nan)
        rows = []
        for phase in ("FLOOD", "EBB"):
            sub = frame[(frame.phase == phase) & frame.residual.notna()]
            mean_speed = sub.along_mps.abs().mean()
            sigma = sub.residual.std(ddof=1)
            raw_variance = sigma**2 - settings.noise_std_mps**2
            corrected = np.sqrt(max(raw_variance, 0)) if np.isfinite(sigma) else np.nan
            rows.append({**keys, "phase": phase, "samples": len(sub), "mean_abs_along_mps": mean_speed,
                         "residual_std_mps": sigma,
                         "residual_intensity_percent": 100*sigma/mean_speed if mean_speed > 0 else np.nan,
                         "noise_corrected_percent": 100*corrected/mean_speed if mean_speed > 0 else np.nan,
                         "noise_variance_clipped": bool(np.isfinite(raw_variance) and raw_variance < 0)})
        return rows
    rows = []
    for bin_id, sub in resolved.groupby("bin"):
        rows.extend(calculate(sub, {"bin": bin_id, "depth_m": sub.depth_m.iloc[0]}))
    return pd.DataFrame(rows), pd.DataFrame(calculate(avg, {}))


def energy(resolved, curve, settings):
    hub = resolved[resolved.bin == settings.hub_bin].sort_values("time")
    if hub.empty:
        raise ValueError(f"Hub bin {settings.hub_bin} is absent. Choose one of {sorted(resolved.bin.unique())}.")
    good = hub.along_mps.notna()
    hub = hub.loc[good].copy()
    if hub.empty:
        raise ValueError("Hub bin contains no valid velocities.")
    curve = curve.copy()
    required = {"speed_mps", "power_kw"}
    if not required.issubset(curve):
        raise ValueError("Power curve needs speed_mps and power_kw columns.")
    curve = curve[list(sorted(required))].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(curve.to_numpy()).all() or (curve < 0).any().any():
        raise ValueError("Power-curve values must be finite and nonnegative.")
    curve = curve.sort_values("speed_mps")
    if len(curve) < 2 or curve.speed_mps.duplicated().any():
        raise ValueError("Power curve must contain at least two unique speeds.")
    if curve.power_kw.max() > settings.rated_kw * 1.001:
        raise ValueError("Power curve exceeds the selected rated power. Check the turbine settings.")
    signed = hub.along_mps.to_numpy()
    speed = np.abs(signed)
    weights = hub.weight_s.to_numpy()
    step = settings.speed_bin_width
    upper = max(step, np.ceil(speed.max()/step)*step)
    edges = np.arange(0, upper + step*0.5, step)
    centers = (edges[:-1]+edges[1:])/2
    seconds, _ = np.histogram(speed, edges, weights=weights)
    operating = (centers >= settings.cut_in_mps) & (centers < settings.cut_out_mps)
    occupied = operating & (seconds > 0)
    if occupied.any() and ((centers[occupied] < curve.speed_mps.min()).any() or (centers[occupied] > curve.speed_mps.max()).any()):
        raise ValueError("Power curve does not cover occupied operating speed bins. Supply a curve covering the selected operating range.")
    power = np.interp(centers, curve.speed_mps, curve.power_kw)
    power[~operating] = 0
    table = pd.DataFrame({"speed_lo_mps": edges[:-1], "speed_hi_mps": edges[1:], "speed_center_mps": centers,
                          "probability": seconds/weights.sum(), "power_kw": power})
    # Direction bins include slack and zero separately to account for all support.
    for phase in ("FLOOD", "EBB", "SLACK", "MISSING"):
        mask = hub.phase.eq(phase).to_numpy()
        sec, _ = np.histogram(speed[mask], edges, weights=weights[mask])
        table[f"prob_{phase.lower()}"] = sec/weights.sum()
    # IEC TS 62600-200: AEP = N_h * sum_i p(U_i) * P(U_i), with N_h = 8766 h per year.
    table["annual_kwh"] = HOURS_PER_YEAR * settings.availability * table.probability * power
    annual = table.annual_kwh.sum()
    mean_power = np.dot(table.probability, power)
    summary = pd.DataFrame([{"hub_bin": settings.hub_bin, "valid_observed_hours": weights.sum()/3600,
                             "hours_per_year": HOURS_PER_YEAR, "mean_power_kw": mean_power,
                             "aep_kwh": annual,
                             "observed_period_kwh": mean_power*weights.sum()/3600*settings.availability,
                             "capacity_factor": annual/(HOURS_PER_YEAR*settings.rated_kw),
                             "availability": settings.availability}])
    return table, summary
