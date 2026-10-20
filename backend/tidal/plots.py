"""Consistent figures plus lightweight interactive notebook exploration."""
import numpy as np
import matplotlib.pyplot as plt

COLORS = {"FLOOD": "#D62728", "EBB": "#1F77B4", "SLACK": "#808080", "MISSING": "#222222"}
FIGURE_ORDER = ("_TimeSeries", "velocity_components", "_Statistics", "current_rose", "current_rose_ebb_flood",
                "tidal_cycles", "cycle_cosine_view", "_FlowSummary", "principal_flow_diagnostics", "tidal_velocity_polar", "Velocity_profiles",
                "TI_original_profiles", "ebb_flood_probabilities", "turbine_power_curve", "hub_velocity_probability",
                "energy_contributions", "turbine_aep", "annual_comparison")
SOURCE_LABELS = {"coops": "NOAA CO-OPS", "verdant": "Verdant Power", "standard_csv": "Standard CSV"}


def figure_prefix(cfg, source=None):
    """Name the series being drawn. Verdant titles include Station A/B from the selected sheets."""
    from .config import verdant_station_names
    key = cfg.source if source is None else source
    label = SOURCE_LABELS.get(key, str(key).replace("_", " ").title())
    if key == "verdant":
        names = verdant_station_names(getattr(cfg, "verdant_sheets", ()))
        return f"{label} · {' / '.join(names)}" if names else label
    site = (getattr(cfg, "site", "") or "").strip()
    return f"{label} · {site}" if site else label


def style():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                         "mathtext.fontset": "stix", "figure.dpi": 110, "axes.grid": True,
                         "grid.alpha": 0.2, "axes.spines.top": False, "axes.spines.right": False,
                         "font.size": 14, "axes.labelsize": 15, "axes.titlesize": 15,
                         "xtick.labelsize": 13, "ytick.labelsize": 13, "legend.fontsize": 12,
                         "figure.titlesize": 16})


def save_figures(assessment, directory, file_prefix=""):
    style()
    tables, cfg = assessment.tables, assessment.settings
    avg = tables["depth_averaged"]
    paths = {}

    def save(name, fig):
        fig.suptitle(f"{figure_prefix(cfg)} · {name.replace('_', ' ').title()}")
        fig.tight_layout()
        path = directory / f"{file_prefix}{name}.png"
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
    bar.set_label("Current velocity (m/s)")
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
        ax.set(xlabel="Normalized cycle time", ylabel="Streamwise velocity (m/s)")
        ax.legend()
        save("tidal_cycles", fig)

    if "energy_bins" in tables:
        bins = tables["energy_bins"]
        width = cfg.speed_bin_width*0.9
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(bins.speed_center_mps, 100*bins.probability, width=width, color="tab:purple", alpha=0.8)
        for speed, label in ((cfg.cut_in_mps, "Cut-in"), (cfg.rated_speed_mps, "Rated"), (cfg.cut_out_mps, "Cut-out")):
            ax.axvline(speed, color="0.3", ls="--", lw=0.9)
            ax.text(speed, ax.get_ylim()[1]*0.97, f" {label}", ha="left", va="top", fontsize=12)
        ax.set(xlabel=f"Hub streamwise velocity, bin {cfg.hub_bin} (m/s)",
               ylabel=f"Time-weighted probability p(Uᵢ) (%), ΔU = {cfg.speed_bin_width:g} m/s")
        save("hub_velocity_probability", fig)
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(bins.speed_center_mps, bins.annual_kwh/1000, width=width, color="tab:green")
        ax.set(xlabel=f"Hub streamwise velocity, bin {cfg.hub_bin} (m/s)",
               ylabel="AEP contribution (MWh/yr)",
               title=f"Single turbine AEP = 8766 h × Σ p(Uᵢ)·P(Uᵢ) = {bins.annual_kwh.sum()/1000:,.1f} MWh/yr")
        save("energy_contributions", fig)
        curve = tables["power_curve"].sort_values("speed_mps")
        cin, rated_u, cout, rated_p = cfg.cut_in_mps, cfg.rated_speed_mps, cfg.cut_out_mps, cfg.rated_kw
        x_max = cout*1.2
        inside = np.linspace(cin, cout, 400)
        speeds = np.r_[0, cin, inside, cout, cout, x_max]
        power = np.r_[0, 0, np.interp(inside, curve.speed_mps, curve.power_kw), np.interp(cout, curve.speed_mps, curve.power_kw), 0, 0]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot(speeds, power, color="tab:red", lw=1.8)
        ax.vlines(rated_u, 0, rated_p, color="k", lw=0.8)
        arrow = dict(arrowstyle="->", color="k", lw=0.8)
        ax.annotate("Cut-in velocity", xy=(cin, 0), xytext=(cin, rated_p*0.3), ha="center", arrowprops=arrow)
        ax.annotate("Rated output velocity", xy=(rated_u, rated_p), xytext=(rated_u, rated_p*1.15), ha="center", arrowprops=arrow)
        ax.annotate("Rated output power", xy=(rated_u*0.97, rated_p), xytext=(cin*0.6, rated_p*1.0),
                    ha="left", va="center", arrowprops=arrow)
        ax.annotate("Cut-out velocity", xy=(cout, rated_p), xytext=(cout*0.82, rated_p*1.15), ha="center", arrowprops=arrow)
        ax.set_xticks([cin, rated_u, cout])
        ax.set_xticklabels([f"{cin:g}", f"{rated_u:.2g}", f"{cout:g}"])
        ax.set_yticks([])
        ax.set(xlim=(0, x_max), ylim=(0, rated_p*1.3), xlabel="Steady flow velocity (m/s)", ylabel="Power (kW)")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        save("turbine_power_curve", fig)
    if "postprocessing_catalog" in tables:
        from .original_plots import save_original_figures
        paths.update(save_original_figures(assessment, directory, file_prefix=file_prefix))
    rank = {name: i for i, name in enumerate(FIGURE_ORDER)}
    return dict(sorted(paths.items(), key=lambda item: rank.get(item[0], len(rank))))
