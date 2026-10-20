"""Retained original postprocessing figure families on the shared data model."""
import numpy as np
import matplotlib.pyplot as plt
from .plots import COLORS, figure_prefix


def _cardinal_direction(angle):
    points = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    return points[int((float(angle) % 360 + 11.25) // 22.5) % 16]


def _polar_title(cfg):
    return f"{figure_prefix(cfg)} · Tidal Velocity Polar Plot"


def _phase_polar_statistics(resolved, bearing):
    """Summaries for the polar plot from canonical, source-independent columns."""
    rows = []
    for phase in ("FLOOD", "EBB"):
        sub = resolved.loc[resolved.phase.eq(phase)].dropna(subset=["direction_degT", "speed_mps"])
        angles = np.deg2rad(sub.direction_degT.to_numpy(dtype=float))
        resultant = np.hypot(np.sin(angles).mean(), np.cos(angles).mean()) if len(angles) else 0
        direction = (np.degrees(np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())) % 360
                     if len(angles) and resultant > 1e-10 else np.nan)
        rows.append({"phase": phase, "samples": len(sub), "direction_degT": direction,
                     "mean_speed_mps": sub.speed_mps.mean()})
    return float(bearing) % 180, rows


def _display_sample(frame, limit=30000):
    """Even deterministic sample for readable, bounded-size scatter rendering."""
    if len(frame) <= limit:
        return frame
    return frame.iloc[np.linspace(0, len(frame)-1, limit, dtype=int)]


def save_original_figures(assessment, directory, file_prefix=""):
    t, cfg = assessment.tables, assessment.settings
    avg = t["depth_averaged"]
    paths = {}

    def save(name, fig, note=None, prefix=None, title=None, polar_layout=False):
        heading = figure_prefix(cfg) if prefix is None else prefix
        fig.suptitle(title or f"{heading} · {name.strip('_').replace('_', ' ')}")
        if note:
            fig.text(.5, .01, note, ha="center", fontsize=11)
        if polar_layout:
            fig.subplots_adjust(left=.05, right=.72, bottom=.09, top=.88)
        else:
            fig.tight_layout(rect=(0, .035 if note else 0, 1, .97))
        path = directory / f"{file_prefix}{name}.png"
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        paths[name] = path

    def time_series(ax):
        for _, sub in avg.groupby("analysis_block"):
            ax.plot(sub.time, sub.along_mps, color="0.4", lw=.5)
        for phase in ("EBB", "FLOOD", "SLACK"):
            sub = avg[avg.phase == phase]
            ax.scatter(sub.time, sub.along_mps, color=COLORS[phase], s=2, label=phase.title())
        ax.set_ylabel("Signed streamwise velocity (m/s)")
        ax.legend(ncol=3, markerscale=3)

    def phase_hist(ax):
        limit = max(float(avg.along_mps.abs().max()), .01)
        edges = np.linspace(-limit*1.001, limit*1.001, 41)
        for phase in ("EBB", "FLOOD", "SLACK"):
            ax.hist(avg.loc[avg.phase == phase, "along_mps"].dropna(), bins=edges, color=COLORS[phase], alpha=.65,
                    edgecolor="k", linewidth=.6, label=phase.title())
        ax.set(xlabel="Signed streamwise velocity (m/s)", ylabel="Sample count")
        ax.legend()

    # Preserve the six original flowVisualized output identities.
    directions = t["dominant_directions"].set_index("phase")
    fig = plt.figure(figsize=(10, 4.5))
    bar, compass = fig.add_subplot(121), fig.add_subplot(122, projection="polar")
    phases = ["EBB", "FLOOD"]
    bar.bar([p.title() for p in phases], [directions.loc[p, "mean_speed_mps"] for p in phases], color=[COLORS[p] for p in phases])
    bar.set_ylabel("Mean horizontal velocity (m/s)")
    compass.set_theta_zero_location("N")
    compass.set_theta_direction(-1)
    compass.set_xticks(np.deg2rad(np.arange(0, 360, 45)), ["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    for phase in phases:
        bearing, speed = directions.loc[phase, ["circular_mean_degT", "mean_speed_mps"]]
        if np.isfinite(bearing) and np.isfinite(speed):
            angle = np.deg2rad(bearing)
            compass.plot([angle, angle], [0, speed], color=COLORS[phase], marker="o", label=f"{phase.title()} {bearing:.1f}°T")
    compass.legend(loc="upper left", bbox_to_anchor=(1.05, 1), fontsize=11)
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
    axs[1].set_ylabel("Absolute streamwise velocity (m/s)")
    for ax in axs:
        ax.spines[["top", "right"]].set_visible(True)
    save("_Statistics", fig)

    fig, axs = plt.subplots(1, 3, figsize=(14, 5))
    vectors = avg.dropna(subset=["east_mps", "north_mps"])[["east_mps", "north_mps"]].to_numpy()
    axs[0].scatter(vectors[:, 0], vectors[:, 1], s=2, alpha=.1, color="0.4")
    val, vec = np.linalg.eigh(np.cov(vectors.T))
    angle = np.linspace(0, 2*np.pi, 200)
    mean = vectors.mean(axis=0)
    ellipse = (vec @ np.diag(np.sqrt(np.maximum(val, 0))) @ np.array([np.cos(angle), np.sin(angle)])).T+mean
    axs[0].plot(ellipse[:, 0], ellipse[:, 1], color="tab:orange", label="std. ellipse")
    radius = np.max(np.linalg.norm(vectors, axis=1))
    phi = np.deg2rad(assessment.bearing)
    axs[0].plot(mean[0]+np.array([-1, 1])*radius*np.sin(phi), mean[1]+np.array([-1, 1])*radius*np.cos(phi), "k--", label="Principal axis")
    axs[0].set(xlabel="East (m/s)", ylabel="North (m/s)")
    axs[0].set_aspect("equal", adjustable="datalim")
    axs[0].legend(fontsize=11)
    pdf, cdf = t["signed_velocity_distribution"], t["signed_velocity_cdf"]
    axs[1].bar((pdf.velocity_lo_mps+pdf.velocity_hi_mps)/2, pdf.pdf, width=pdf.velocity_hi_mps-pdf.velocity_lo_mps, color="tab:green",
                edgecolor="k", linewidth=.6, linestyle="-")
    axs[1].set(xlabel="Signed streamwise velocity (m/s)", ylabel="Probability density")
    axs[2].plot(cdf.signed_velocity_mps, cdf.sample_cdf, color="tab:purple")
    axs[2].set(xlabel="Signed streamwise velocity (m/s)", ylabel="Sample CDF", ylim=(0, 1))
    for ax in axs[1:]:
        for sign in (-1, 1):
            ax.axvline(sign*cfg.slack_mps, color="0.4", ls="--")
    save("principal_flow_diagnostics", fig)

    # Source-independent bin-level velocity polar plot. Phase labels are inherited
    # from the same depth-averaged classification used throughout the workflow.
    resolved = t["depth_resolved"]
    polar = resolved.loc[resolved.phase.isin(["FLOOD", "EBB"])].dropna(
        subset=["direction_degT", "speed_mps"])
    axis_deg, phase_rows = _phase_polar_statistics(polar, assessment.bearing)
    phase_stats = {row["phase"]: row for row in phase_rows}
    fig, ax = plt.subplots(figsize=(12, 9), subplot_kw={"projection": "polar"})
    displayed = 0
    for phase in ("FLOOD", "EBB"):
        full = polar.loc[polar.phase.eq(phase)]
        shown = _display_sample(full)
        displayed += len(shown)
        ax.scatter(np.deg2rad(shown.direction_degT), shown.speed_mps, s=7, alpha=.08,
                   color=COLORS[phase], edgecolors="none", rasterized=True,
                   label=f"{phase.title()} (ADCP bin data)", zorder=3)
    maximum = float(polar.speed_mps.max()) if len(polar) else 0
    radius = max(maximum*1.08, .1)
    axis_angle = np.deg2rad(axis_deg)
    ax.plot([axis_angle, axis_angle], [0, radius], "k-.", lw=1.5,
            label=f"Principal axis ({axis_deg:.1f}°)", zorder=2)
    ax.plot([axis_angle+np.pi, axis_angle+np.pi], [0, radius], "k-.", lw=1.5, zorder=2)
    for phase in ("FLOOD", "EBB"):
        row = phase_stats[phase]
        direction = row["direction_degT"]
        if not np.isfinite(direction):
            continue
        angle = np.deg2rad(direction)
        length = radius*.88
        ax.annotate("", xy=(angle, length), xytext=(angle, 0),
                    arrowprops={"arrowstyle": "-|>", "color": COLORS[phase],
                                "lw": 2.2, "mutation_scale": 18}, zorder=5)
        ax.text(angle, length*1.04, f"{direction:.1f}°", color=COLORS[phase],
                fontsize=13, fontweight="bold", ha="center", va="center")
        ax.plot([], [], color=COLORS[phase], lw=2.2,
                label=f"{phase.title()} mean direction ({direction:.1f}°)")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    bearings = np.arange(0, 360, 30)
    ax.set_xticks(np.deg2rad(bearings), [f"{value}°" for value in bearings])
    ax.set_ylim(0, radius)
    radial_ticks = np.linspace(radius/4, radius, 4)
    ax.set_rticks(radial_ticks)
    ax.set_yticklabels([f"{value:.1f} m/s" for value in radial_ticks])
    ax.set_rlabel_position(78)
    ax.grid(True, color="0.45", ls="--", lw=.7, alpha=.75)
    legend = ax.legend(loc="upper left", bbox_to_anchor=(1.03, 1.08), fontsize=12,
                       frameon=True, fancybox=False)
    for handle in legend.legend_handles:
        handle.set_alpha(1)
    flood, ebb = phase_stats["FLOOD"], phase_stats["EBB"]
    summary = [f"Principal axis: {axis_deg:.1f}° "
               f"({_cardinal_direction(axis_deg)}–{_cardinal_direction(axis_deg+180)})"]
    for label, row in (("Flood", flood), ("Ebb", ebb)):
        direction = row["direction_degT"]
        summary.append(f"{label} direction: {direction:.1f}° ({_cardinal_direction(direction)})"
                       if np.isfinite(direction) else f"{label} direction: unavailable")
        summary.append(f"Mean {label.lower()} velocity: {row['mean_speed_mps']:.2f} m/s"
                       if np.isfinite(row["mean_speed_mps"]) else f"Mean {label.lower()} velocity: unavailable")
    fig.text(.75, .12, "\n".join(summary), ha="left", va="bottom", fontsize=13, linespacing=1.35)
    note = "Radius: horizontal velocity; angles: degrees true"
    if displayed < len(polar):
        note += f"; evenly displayed {displayed:,} of {len(polar):,} valid bin records"
    save("tidal_velocity_polar", fig, note=note, title=_polar_title(cfg), polar_layout=True)

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
        #note = "Legacy normalized grid; not confirmed physical z/h" if cfg.profile_coordinate_mode == "legacy_normalized" else "Physical z/h; missing metadata leaves fits unestimated"
        fig, axs = plt.subplots(1, 2, figsize=(11, 5.5), sharey=True)
        for ax, phase in zip(axs, ("EBB", "FLOOD")):
            sign = -1 if phase == "EBB" else 1
            sub = curves[(curves.phase == phase) & (curves.model == "peak_power")].sort_values("eta")
            ax.plot(sign*sub.measured_speed_mps, sub.eta, "o", color=COLORS[phase], label="ADCP profile")
            ax.plot(sign*sub.predicted_speed_mps, sub.eta, "k-", label="Powerlaw fit")
            log = curves[(curves.phase == phase) & (curves.model == "peak_log")].sort_values("eta")
            ax.plot(sign*log.predicted_speed_mps, log.eta, color="magenta", ls="--", label="Loglaw fit")
            lines = [phase.title()]
            for model in ("peak_power", "peak_log"):
                row = fits[(fits.phase == phase) & (fits.model == model)]
                name = "Powerlaw" if model == "peak_power" else "Loglaw"
                if not len(row):
                    continue
                r = row.iloc[0]
                if r.status != "ok":
                    lines.append(f"{name}: {r.status}")
                elif model == "peak_power":
                    lines.append(rf"Powerlaw: $\alpha={r.alpha:.2f}$, $\beta={r.beta:.3f}$, "
                                 rf"$U={r.reference_U_mps:.2f}$ m/s, $R^2={r.r_squared:.3f}$")
                else:
                    mantissa, exponent = f"{r.z0_over_h:.2e}".split("e")
                    lines.append(rf"Loglaw: $u_*={r.u_star_mps:.3f}$ m/s, "
                                 rf"$z_0/h={mantissa}\times10^{{{int(exponent)}}}$, $R^2={r.r_squared:.3f}$")
            ax.set_title("\n".join(lines), fontsize=12)
            ax.set(xlabel="Streamwise velocity (m/s)")
            ax.legend(fontsize=11)
        axs[0].set_ylabel("Normalized height ")
        save("Velocity_profiles", fig)

    ti = t["ti_original_by_bin"]
    if len(ti):
        fig, axs = plt.subplots(1, 2, figsize=(10, 5), sharey=True)
        for phase in ("FLOOD", "EBB"):
            sub = ti[ti.phase == phase].sort_values("eta")
            for ax, column in zip(axs, ("TI_from_fluct_percent", "TI_doppler_corrected_percent")):
                ax.plot(sub[column], sub.eta, "o-", color=COLORS[phase], label=phase.title())
        noise_title = rf"Noise-corrected · $σ_{{\text{{noise}}}}$={cfg.noise_std_mps:g} m/s"
        for ax, title in zip(axs, ("Raw original TI formula", noise_title)):
            ax.set(title=title, xlabel="Intensity (%)")
            ax.legend()
        axs[0].set_ylabel("Normalized height")
        save("TI_original_profiles", fig, "Ensemble-resolved variability; rolling horizontal-velocity denominator")

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
        ax.set(xlabel="Absolute hub velocity (m/s)", ylabel="Probability")
        ax.legend()
        save("ebb_flood_probabilities", fig, "Direction from hub-velocity sign; includes near-slack flow, unlike threshold phase labels")
        aep = t["turbine_aep_summary"].iloc[0]
        fig, ax = plt.subplots(figsize=(7, 4))
        bars = ax.bar(["Observed period", "Annual energy production"], [aep.observed_period_kwh/1000, aep.aep_kwh/1000],
                      color=["tab:purple", "tab:green"])
        ax.bar_label(bars, fmt="%.1f MWh")
        ax.set_ylabel("Single-turbine energy (MWh)")
        save("turbine_aep", fig, f"IEC TS 62600-200: AEP = 8766 h × Σ p(Uᵢ)·P(Uᵢ); capacity factor {aep.capacity_factor:.1%}")

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
            ax.legend(loc="upper right", fontsize=11, markerscale=3)
            ax.set(title=f"NOAA CO-OPS · {row.site} · {row.time_reference}", ylabel="Predicted event velocity (m/s)")
        fig.autofmt_xdate()
        save("annual_comparison", fig, "Nonuniform prediction events, shown separately from measured ADCP results", prefix="NOAA CO-OPS")
    return paths
