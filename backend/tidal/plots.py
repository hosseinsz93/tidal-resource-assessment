"""Consistent figures plus lightweight interactive notebook exploration."""
import numpy as np
import matplotlib.pyplot as plt

COLORS = {"FLOOD": "#D62728", "EBB": "#1F77B4", "SLACK": "#808080", "MISSING": "#222222"}
FIGURE_ORDER = ("_TimeSeries", "velocity_components", "_Statistics", "current_rose", "current_rose_ebb_flood",
                "tidal_cycles", "cycle_cosine_view", "_FlowSummary", "principal_flow_diagnostics", "tidal_velocity_polar", "Velocity_profiles",
                "TI_original_profiles", "ebb_flood_probabilities", "turbine_power_curve", "energy_contributions",
                "farm_energy", "annual_comparison")
SOURCE_LABELS = {"coops": "NOAA CO-OPS", "verdant": "Verdant Power", "standard_csv": "Standard CSV"}


def figure_prefix(cfg, source=None):
    """Name the series being drawn. Verdant titles follow the source, not a CO-OPS station id left in site."""
    key = cfg.source if source is None else source
    label = SOURCE_LABELS.get(key, str(key).replace("_", " ").title())
    if key == "verdant":
        return label
    site = (getattr(cfg, "site", "") or "").strip()
    return f"{label} · {site}" if site else label


def style():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                         "mathtext.fontset": "stix", "figure.dpi": 110, "axes.grid": True,
                         "grid.alpha": 0.2, "axes.spines.top": False, "axes.spines.right": False})


def save_figures(assessment, directory):
    style()
    tables, cfg = assessment.tables, assessment.settings
    avg = tables["depth_averaged"]
    paths = {}

    def save(name, fig):
        fig.suptitle(f"{figure_prefix(cfg)} · {name.replace('_', ' ').title()}")
        fig.tight_layout()
        path = directory / f"{name}.png"
        fig.savefig(path, dpi=160, bbox_inches="tight")
        plt.close(fig)
        paths[name] = path

    valid = avg.dropna(subset=["east_mps", "north_mps"])
    fig, ax = plt.subplots(figsize=(7, 6), subplot_kw={"projection": "polar"})
    n_dirs, n_bands = 36, 100
    dirs = np.linspace(0, 360, n_dirs+1)
    speed_max = max(valid.speed_mps.max(), 0.1)*1.1
    speed_edges = np.linspace(0, speed_max, n_bands+1)
    hist, _, _ = np.histogram2d(valid.direction_degT, valid.speed_mps, bins=[dirs, speed_edges], weights=valid.weight_s)
    hist = 100*hist / hist.sum()
    bottom = np.zeros(n_dirs)
    colors = plt.colormaps["jet"](np.linspace(0, 1, n_bands))
    for i in range(n_bands):
        ax.bar(np.deg2rad((dirs[:-1]+dirs[1:])/2), hist[:, i], width=np.deg2rad(360/n_dirs), bottom=bottom,
               color=colors[i], edgecolor="none", antialiased=False, zorder=3)
        bottom += hist[:, i]
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(np.deg2rad(np.arange(0, 360, 45)), ["N", "NE", "E", "SE", "S", "SW", "W", "NW"], fontweight="bold")
    ax.set_title("Radius: percentage of valid observed time", pad=25)
    bar = fig.colorbar(plt.cm.ScalarMappable(cmap="jet", norm=plt.Normalize(0, speed_max)), ax=ax, pad=0.1, shrink=0.7)
    bar.set_ticks(np.linspace(0, speed_max, 5))
    bar.set_ticklabels([f"{v:.1f}" for v in np.linspace(0, speed_max, 5)])
    bar.set_label("Current Speed (m/s)")
    bar.outline.set_visible(False)
    save("current_rose", fig)

    fig, ax = plt.subplots(figsize=(11, 3.5))
    for component, color in (("east_mps", "tab:purple"), ("north_mps", "tab:green")):
        for i, (_, sub) in enumerate(avg.groupby("analysis_block")):
            ax.plot(sub.time, sub[component], color=color, lw=0.6, label=component.replace("_mps", "").title() if i == 0 else None)
    ax.set_ylabel("Velocity (m/s)")
    ax.legend()
    fig.autofmt_xdate()
    save("velocity_components", fig)

    members, ensemble = tables["cycle_members"], tables["cycle_ensemble"]
    if len(members.columns):
        fig, ax = plt.subplots(figsize=(8, 4))
        for col in members.columns[1:41]:
            ax.plot(members.normalized_time, members[col], color="0.8", lw=0.5)
        ax.plot(ensemble.normalized_time, ensemble.mean_mps, color="k", label="Ensemble mean")
        ax.plot(ensemble.normalized_time, ensemble.fit_mps, color="tab:orange", label="Harmonic fit")
        ax.set(xlabel="Normalized cycle time", ylabel="Along-channel velocity (m/s)")
        ax.legend()
        save("tidal_cycles", fig)

    if "energy_bins" in tables:
        bins = tables["energy_bins"]
        fig, axs = plt.subplots(1, 2, figsize=(10, 4))
        axs[0].plot(bins.speed_center_mps, bins.probability, color="tab:purple")
        axs[0].set(xlabel="Hub along-speed bin (m/s)", ylabel="Time-weighted probability")
        axs[1].bar(bins.speed_center_mps, bins.annual_kwh, width=cfg.speed_bin_width*0.9, color="tab:green")
        axs[1].set(xlabel="Hub along-speed bin (m/s)", ylabel="Annual contribution (kWh)")
        save("energy_contributions", fig)
        curve = tables["power_curve"].sort_values("speed_mps")
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(curve.speed_mps, curve.power_kw, color="0.4", ls="--", label="Supplied curve")
        effective = curve.power_kw.where((curve.speed_mps >= cfg.cut_in_mps) & (curve.speed_mps < cfg.cut_out_mps), 0)
        ax.plot(curve.speed_mps, effective, color="tab:green", label="With selected operating limits")
        ax.axvline(cfg.cut_in_mps, ls=":", color="0.4")
        ax.axvline(cfg.rated_speed_mps, ls="--", color="tab:orange", label="Rated speed")
        ax.axvline(cfg.cut_out_mps, ls=":", color="0.4")
        ax.set(xlabel="Speed (m/s)", ylabel="Power (kW)")
        ax.legend()
        save("turbine_power_curve", fig)
    if "postprocessing_catalog" in tables:
        from .original_plots import save_original_figures
        paths.update(save_original_figures(assessment, directory))
    rank = {name: i for i, name in enumerate(FIGURE_ORDER)}
    return dict(sorted(paths.items(), key=lambda item: rank.get(item[0], len(rank))))
