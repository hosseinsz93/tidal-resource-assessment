"""Retained original postprocessing figure families on the shared data model."""
import numpy as np
import matplotlib.pyplot as plt
from .plots import COLORS


def save_original_figures(assessment, directory):
    t, cfg = assessment.tables, assessment.settings
    avg = t["depth_averaged"]
    paths = {}

    def save(name, fig, note=None):
        fig.suptitle(f"{cfg.site} · {name.strip('_').replace('_', ' ')}")
        if note:
            fig.text(.5, .01, note, ha="center", fontsize=8)
        fig.tight_layout(rect=(0, .035 if note else 0, 1, .97))
        path = directory / f"{name}.png"
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        paths[name] = path

    def time_series(ax):
        for _, sub in avg.groupby("analysis_block"):
            ax.plot(sub.time, sub.along_mps, color="0.4", lw=.5)
        for phase in ("EBB", "FLOOD", "SLACK"):
            sub = avg[avg.phase == phase]
            ax.scatter(sub.time, sub.along_mps, color=COLORS[phase], s=2, label=phase.title())
        ax.set_ylabel("Signed along velocity (m/s)")
        ax.legend(ncol=3, markerscale=3)

    def phase_hist(ax):
        limit = max(float(avg.along_mps.abs().max()), .01)
        edges = np.linspace(-limit*1.001, limit*1.001, 41)
        for phase in ("EBB", "FLOOD", "SLACK"):
            ax.hist(avg.loc[avg.phase == phase, "along_mps"].dropna(), bins=edges, color=COLORS[phase], alpha=.65,
                    edgecolor="k", linewidth=.6, label=phase.title())
        ax.set(xlabel="Signed along velocity (m/s)", ylabel="Sample count")
        ax.legend()

    # Preserve the six original flowVisualized output identities.
    directions = t["dominant_directions"].set_index("phase")
    fig = plt.figure(figsize=(10, 4.5))
    bar, compass = fig.add_subplot(121), fig.add_subplot(122, projection="polar")
    phases = ["EBB", "FLOOD"]
    bar.bar([p.title() for p in phases], [directions.loc[p, "mean_speed_mps"] for p in phases], color=[COLORS[p] for p in phases])
    bar.set_ylabel("Mean horizontal speed (m/s)")
    compass.set_theta_zero_location("N")
    compass.set_theta_direction(-1)
    compass.set_xticks(np.deg2rad(np.arange(0, 360, 45)), ["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    for phase in phases:
        bearing, speed = directions.loc[phase, ["circular_mean_degT", "mean_speed_mps"]]
        if np.isfinite(bearing) and np.isfinite(speed):
            angle = np.deg2rad(bearing)
            compass.plot([angle, angle], [0, speed], color=COLORS[phase], marker="o", label=f"{phase.title()} {bearing:.1f}°T")
    compass.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=8)
    save("_FlowSummary", fig)

    fig, ax = plt.subplots(figsize=(11, 3.5))
    time_series(ax)
    fig.autofmt_xdate()
    save("_TimeSeries", fig)

    fig, axs = plt.subplots(2, 1, figsize=(8, 7))
    phase_hist(axs[0])
    boxes = [avg.loc[avg.phase == p, "along_mps"].abs().dropna().to_numpy() for p in ("EBB", "FLOOD", "SLACK")]
    artists = axs[1].boxplot(boxes, patch_artist=True, boxprops=dict(edgecolor="k", linewidth=.8),
                             whiskerprops=dict(color="k", linestyle="--", linewidth=.8),
                             capprops=dict(color="k", linewidth=.8), medianprops=dict(color="k", linewidth=1.2))
    for patch, phase in zip(artists["boxes"], ("EBB", "FLOOD", "SLACK")):
        patch.set_facecolor((*plt.matplotlib.colors.to_rgb(COLORS[phase]), .6))
    axs[1].set_xticks([1, 2, 3], ["Ebb", "Flood", "Slack"])
    axs[1].set_ylabel("Absolute along velocity (m/s)")
    for ax in axs:
        ax.spines[["top", "right"]].set_visible(True)
    save("_Statistics", fig)

    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    vectors = avg.dropna(subset=["east_mps", "north_mps"])[["east_mps", "north_mps"]].to_numpy()
    axs[0].scatter(vectors[:, 0], vectors[:, 1], s=2, alpha=.1, color="0.4")
    val, vec = np.linalg.eigh(np.cov(vectors.T))
    angle = np.linspace(0, 2*np.pi, 200)
    mean = vectors.mean(axis=0)
    ellipse = (vec @ np.diag(np.sqrt(np.maximum(val, 0))) @ np.array([np.cos(angle), np.sin(angle)])).T+mean
    axs[0].plot(ellipse[:, 0], ellipse[:, 1], color="tab:orange", label="1σ ellipse")
    radius = np.max(np.linalg.norm(vectors, axis=1))
    phi = np.deg2rad(assessment.bearing)
    axs[0].plot(mean[0]+np.array([-1, 1])*radius*np.sin(phi), mean[1]+np.array([-1, 1])*radius*np.cos(phi), "k--", label="Principal axis")
    axs[0].set(xlabel="East (m/s)", ylabel="North (m/s)", aspect="equal")
    axs[0].legend(fontsize=8)
    pdf, cdf = t["signed_velocity_distribution"], t["signed_velocity_cdf"]
    axs[1].bar((pdf.velocity_lo_mps+pdf.velocity_hi_mps)/2, pdf.pdf, width=pdf.velocity_hi_mps-pdf.velocity_lo_mps, color="tab:green")
    axs[1].set(xlabel="Signed along velocity (m/s)", ylabel="Probability density")
    axs[2].plot(cdf.signed_velocity_mps, cdf.sample_cdf, color="tab:purple")
    axs[2].set(xlabel="Signed along velocity (m/s)", ylabel="Sample CDF", ylim=(0, 1))
    for ax in axs[1:]:
        for sign in (-1, 1):
            ax.axvline(sign*cfg.slack_mps, color="0.4", ls="--")
    save("principal_flow_diagnostics", fig)

    pcu = t["pcu_time_series"]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for ax, phase in zip(axs, ("EBB", "FLOOD")):
        sub = pcu[pcu.phase == phase]
        ax.scatter(sub.pcu_global_mps.abs(), sub.pcu_phase_mps.abs(), s=3, alpha=.3, color=COLORS[phase])
        ax.set(title=phase.title(), xlabel="Global-axis |PCU| (m/s)", ylabel="Phase-axis |PCU| (m/s)")
    save("phase_pcu_comparison", fig)
    events = t["tidal_events"]
    if len(events):
        fig, axs = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        for phase in ("FLOOD", "EBB"):
            sub = events[events.phase == phase]
            axs[0].scatter(sub.start, sub.observed_hours, color=COLORS[phase], s=8, label=phase.title())
            axs[1].scatter(sub.start, sub.rms_pcu_mps if "rms_pcu_mps" in sub else np.full(len(sub), np.nan), color=COLORS[phase], s=8)
        axs[0].set_ylabel("Event observed hours")
        axs[1].set_ylabel("Event RMS PCU (m/s)")
        axs[0].legend()
        fig.autofmt_xdate()
        save("event_diagnostics", fig)

    comparison = t["cycle_comparison"]
    if len(comparison):
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(comparison.cos_phase, comparison.mean_mps, "k", label="Mean cycle")
        ax.plot(comparison.cos_phase, comparison.original_no_offset_fit_mps, color="tab:orange", label="Cosine fit")
        ax.set(xlabel="cos(φ)", ylabel="Signed PCU (m/s)")
        ax.legend()
        save("cycle_cosine_view", fig)

    curves, fits = t["original_profile_curves"], t["original_profile_fits"]
    if len(curves):
        note = "Legacy normalized grid; not confirmed physical z/h" if cfg.profile_coordinate_mode == "legacy_normalized" else "Physical z/h; missing metadata leaves fits unestimated"
        fig, axs = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
        for ax, phase in zip(axs, ("EBB", "FLOOD")):
            sub = curves[(curves.phase == phase) & (curves.model == "peak_power")].sort_values("eta")
            ax.plot((-1 if phase == "EBB" else 1)*sub.measured_speed_mps, sub.eta, "o", color=COLORS[phase], label="Single record-peak profile")
            ax.plot((-1 if phase == "EBB" else 1)*sub.predicted_speed_mps, sub.eta, "k-", label="Power fit")
            row = fits[(fits.phase == phase) & (fits.model == "peak_power")]
            label = phase.title()
            if len(row) and row.iloc[0].status == "ok":
                r = row.iloc[0]
                label += f" · α={r.alpha:.2f}, β={r.beta:.3f}, U={r.reference_U_mps:.2f} m/s"
            elif len(row):
                ax.text(.05, .5, row.iloc[0].status, transform=ax.transAxes, wrap=True)
            ax.set(title=label, xlabel="Phase-signed speed magnitude (m/s)")
            ax.legend(fontsize=8)
        axs[0].set_ylabel("Normalized coordinate η")
        save("peak_power_profiles", fig, note)
        fig, axs = plt.subplots(2, 2, figsize=(11, 9))
        peaks = t["event_peak_profiles"]
        for column, phase in enumerate(("EBB", "FLOOD")):
            for _, group in peaks[peaks.phase == phase].groupby("event_id"):
                group = group.sort_values("depth_m")
                axs[0, column].plot(group.along_mps, group.depth_m, color=COLORS[phase], alpha=.2, lw=.7)
            sub = curves[(curves.phase == phase) & (curves.model == "phase_log")].sort_values("depth_m")
            sign = -1 if phase == "EBB" else 1
            ax = axs[1, column]
            ax.plot(sign*sub.measured_speed_mps, sub.depth_m, "o", color="0.6", label="Phase mean")
            chosen = sub[sub.used_for_fit]
            ax.plot(sign*chosen.measured_speed_mps, chosen.depth_m, "o", color=COLORS[phase], label="Fit points")
            ax.plot(sign*sub.predicted_speed_mps, sub.depth_m, "k-", label="Log fit")
            ax.legend(fontsize=8)
            axs[0, column].set_title(f"{phase.title()} event-peak profiles")
            ax.set_title(f"{phase.title()} phase-mean log law")
        for ax in axs.flat:
            ax.set(xlabel="Signed along velocity (m/s)", ylabel="Reported bin coordinate (m)")
            if assessment.dataset.data.depth_reference.eq("below_surface").all():
                ax.invert_yaxis()
        save("event_profiles_and_log_fit", fig, note)

    ti = t["ti_original_by_bin"]
    if len(ti):
        fig, axs = plt.subplots(1, 2, figsize=(10, 5), sharey=True)
        for phase in ("FLOOD", "EBB"):
            sub = ti[ti.phase == phase].sort_values("depth_m")
            for ax, column in zip(axs, ("TI_from_fluct_percent", "TI_doppler_corrected_percent")):
                ax.plot(sub[column], sub.depth_m, "o-", color=COLORS[phase], label=phase.title())
        for ax, title in zip(axs, ("Raw original TI formula", f"Noise-corrected · σnoise={cfg.noise_std_mps:g} m/s")):
            ax.set(title=title, xlabel="Intensity (%)")
            ax.legend()
        axs[0].set_ylabel("Reported bin coordinate (m)")
        if assessment.dataset.data.depth_reference.eq("below_surface").all():
            axs[0].invert_yaxis()
        save("TI_original_profiles", fig, "Ensemble-resolved variability; rolling horizontal-speed denominator")
        fig, axs = plt.subplots(1, 2, figsize=(10, 4))
        for ax, key, title in zip(axs, ("ti_original_depth_pooled", "ti_original_depth_averaged"), ("Depth-pooled", "Depth-averaged")):
            sub = t[key].set_index("phase").reindex(["EBB", "FLOOD"])
            x = np.arange(2)
            ax.bar(x-.18, sub.TI_from_fluct_percent, .36, color=[COLORS[p] for p in sub.index], label="Raw")
            ax.bar(x+.18, sub.TI_doppler_corrected_percent, .36, color=[COLORS[p] for p in sub.index], alpha=.4, hatch="//", label="Corrected")
            ax.set_xticks(x, ["Ebb", "Flood"])
            ax.set(title=title, ylabel="Intensity (%)")
            ax.legend()
        save("TI_original_phase_comparison", fig)

    fig, axs = plt.subplots(1, 2, figsize=(10, 5), subplot_kw={"projection": "polar"})
    for ax, phase in zip(axs, ("EBB", "FLOOD")):
        sub = avg[avg.phase == phase]
        ax.scatter(np.deg2rad(sub.direction_degT), sub.speed_mps, s=4, alpha=.25, color=COLORS[phase])
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_title(f"{phase.title()} · radius: m/s", pad=20)
    save("current_rose_ebb_flood", fig)

    if "site_probabilities_ebb_flood" in t:
        bins = t["site_probabilities_ebb_flood"]
        fig, ax = plt.subplots(figsize=(8, 4))
        for phase in ("FLOOD", "EBB"):
            ax.plot(bins.U_center_mps, bins[f"f_{phase.lower()}"], color=COLORS[phase], label=phase.title())
        ax.set(xlabel="Absolute signed hub velocity (m/s)", ylabel="Unconditional probability")
        ax.legend()
        save("ebb_flood_probabilities", fig, "Direction from hub-velocity sign; includes near-slack flow, unlike threshold phase labels")
        farm = t["farm_energy_summary"].iloc[0]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(["Observed period", "Annual extrapolation"], [farm.observed_period_kwh/1000, farm.annual_kwh/1000], color=["tab:purple", "tab:green"])
        ax.set_ylabel(f"Gross farm energy (MWh; {int(farm.turbines)} turbines)")
        save("farm_energy", fig)

    annual = t.get("annual_summary")
    if annual is not None and len(annual):
        fig, axs = plt.subplots(len(annual), 1, figsize=(11, 3*len(annual)), squeeze=False)
        for ax, row in zip(axs[:, 0], annual.itertuples()):
            events = t["annual_events"]
            # Slack events carry no speed; plotting them as NaN would break every line segment.
            sub = events.loc[events.site == row.site].dropna(subset=["time", "signed_speed_mps"])
            ax.plot(sub.time, sub.signed_speed_mps, lw=.3, color="0.6")
            for phase, mask in (("FLOOD", sub.signed_speed_mps > 0), ("EBB", sub.signed_speed_mps < 0)):
                ax.scatter(sub.time[mask], sub.signed_speed_mps[mask], s=3, color=COLORS[phase], label=f"{phase.title()} peak")
            ax.axhline(0, color="k", lw=.5)
            ax.legend(loc="upper right", fontsize=8, markerscale=3)
            ax.set(title=f"{row.site} · {row.time_reference}", ylabel="Predicted event speed (m/s)")
        fig.autofmt_xdate()
        save("annual_comparison", fig, "Nonuniform prediction events, shown separately from measured ADCP results")
    harmonic = t["fixed_period_cosine_series"]
    fig, axs = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    axs[0].plot(harmonic.time, harmonic.observed_mps, lw=.5, label="Observed")
    axs[0].plot(harmonic.time, harmonic.fitted_mps, lw=.6, label="Fixed-period fit")
    axs[0].set_ylabel("Along velocity (m/s)")
    axs[0].legend()
    axs[1].plot(harmonic.time, harmonic.residual_mps, lw=.5, color="0.4")
    axs[1].set_ylabel("Residual (m/s)")
    fig.autofmt_xdate()
    save("_CosineFit", fig, "Historical 12 h 25 min single harmonic; descriptive fit, not a long-term tidal prediction")
    return paths
