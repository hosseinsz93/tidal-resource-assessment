"""Notebook controls and readable results; scientific calculations live elsewhere."""
from dataclasses import fields
from pathlib import Path
import json
from .config import Settings, verdant_station_preset


class SetupPanel:
    def __init__(self, root, initial=None):
        self.root = Path(root)
        self.initial = initial or Settings()
        self.controls = {}
        self.widget = None
        try:
            import ipywidgets as w
        except ImportError:
            print("Interactive controls are unavailable. Edit the Settings object in the setup cell, or install ipywidgets from environment.yml.")
            return
        self.w = w
        style = {"description_width": "190px"}
        layout = w.Layout(width="650px", max_width="100%")

        def add(key, kind, label, **kwargs):
            value = getattr(self.initial, key)
            if isinstance(value, (tuple, list)):
                value = ", ".join(str(v) for v in value)
            if value is None:
                value = ""
            if kind is w.Text:
                value = str(value)
            control = kind(value=value, description=label, style=style, layout=layout, **kwargs)
            self.controls[key] = control
            return control

        source = add("source", w.Dropdown, "Data source", options=[("NOAA CO-OPS", "coops"), ("Verdant Power", "verdant"), ("Other ADCP: standard CSV", "standard_csv")])
        data = [source, add("site", w.Text, "Site / run name"), add("input_path", w.Text, "Input folder or CSV"),
                add("time_zone", w.Text, "Source time zone"),
                add("coops_depth_reference", w.Dropdown, "CO-OPS depth datum", options=[("Unconfirmed", "unknown"), ("Below surface", "below_surface"), ("Above bed", "above_bed")]),
                add("verdant_sheets", w.Text, "Verdant sheet names"),
                add("verdant_heading_offsets", w.Text, "Heading offsets (degrees)"),
                add("excluded_bins", w.Text, "Exclude bins (comma list)"),
                add("water_depth_m", w.Text, "Total water depth (m)")]
        flow = [add("axis_method", w.Dropdown, "Channel axis method", options=[("Principal components (PCA)", "pca"), ("Doubled-angle directions", "doubled_angle")]),
                add("flood_reference_deg", w.FloatText, "Flood-end hint (° true)"),
                add("slack_mps", w.FloatText, "Slack threshold (m/s)"),
                add("smooth_samples", w.IntText, "Smoothing samples"),
                add("max_speed_mps", w.FloatText, "Maximum valid speed (m/s)"),
                add("min_bin_coverage", w.FloatText, "Required bin coverage (0–1)"),
                add("gap_factor", w.FloatText, "Gap / sample interval ratio"),
                add("min_cycle_hours", w.FloatText, "Shortest full cycle (hours)"),
                add("max_cycle_hours", w.FloatText, "Longest full cycle (hours)")]
        variability = [add("ensemble_minutes", w.IntText, "Residual window (minutes)"),
                       add("noise_std_mps", w.FloatText, "Known noise std. (m/s)"),
                       add("near_bed_fraction", w.FloatText, "Log-fit maximum z / h"),
                       add("profile_coordinate_mode", w.Dropdown, "Original profile coordinates", options=[("Legacy normalized bins", "legacy_normalized"), ("Confirmed physical z/h", "physical")]),
                       add("compare_annual_records", w.Checkbox, "Annual-event comparisons"),
                       add("annual_input_path", w.Text, "Annual comparison folder")]
        energy = [add("energy_enabled", w.Checkbox, "Estimate energy"),
                  add("hub_bin", w.IntText, "Turbine hub bin"),
                  add("power_curve", w.Text, "Power-curve CSV"),
                  add("power_curve_mode", w.Dropdown, "Power curve source", options=[("CSV file", "csv"), ("Edit points below", "edited"), ("Generate idealized curve", "generated")]),
                  add("power_curve_points", w.Textarea, "Speed,power points", rows=9),
                  add("rated_kw", w.FloatText, "Rated power (kW)"),
                  add("rated_speed_mps", w.FloatText, "Rated speed (m/s)"),
                  add("cut_in_mps", w.FloatText, "Cut-in speed (m/s)"),
                  add("cut_out_mps", w.FloatText, "Cut-off speed (m/s)"),
                  add("speed_bin_width", w.FloatText, "Speed-bin width (m/s)"),
                  add("turbine_count", w.IntText, "Number of turbines"),
                  add("availability", w.FloatText, "Availability (0–1)")]
        notes = [
            "Select a source first; this updates the example paths. Blank water depth means unknown. Confirm depth datum from station metadata. Verdant uses UTC and workbook bed heights.",
            "For PCA/doubled-angle methods, the flood bearing chooses the correct end of the bidirectional axis. For fixed mode, it is the exact projection bearing. The example bearing is specific to Long Island Sound.",
            "Residual intensity describes fluctuations resolved by the supplied time averages. Leave noise at zero unless a defensible instrument/ensemble-specific estimate is available. Physical log-law fits need water depth and at least three near-bed points.",
            "The supplied power curve and turbine settings are examples. Hub bin is a measurement bin, not a physical hub height. Single-turbine AEP (IEC TS 62600-200) assumes the sampled distribution represents a year.",
        ]
        sections = []
        for controls, note in zip((data, flow, variability, energy), notes):
            sections.append(w.VBox([w.HTML(f"<p>{note}</p>"), *controls]))
        tabs = w.Tab(children=sections)
        for i, title in enumerate(("Data", "Flow and quality", "Profiles and variability", "Energy")):
            tabs.set_title(i, title)
        self.feedback = w.Output()
        check = w.Button(description="Check settings", button_style="info", icon="check")
        check.on_click(self._check)
        self.widget = w.VBox([tabs, check, self.feedback,
                              w.HTML("<p><b>After changing a setting:</b> rerun Preprocess, Process, then Postprocess. Each exported run keeps its own settings and results.</p>")])
        source.observe(self._source_changed, names="value")
        self.controls["verdant_sheets"].observe(self._apply_station_preset, names="value")
        self.controls["slack_mps"].disabled = True
        self.controls["slack_mps"].value = self.controls["cut_in_mps"].value
        self.controls["cut_in_mps"].observe(lambda change: setattr(self.controls["slack_mps"], "value", change["new"]), names="value")
        preview = w.Button(description="Preview power curve", icon="line-chart")
        load_points = w.Button(description="Load CSV into editor", icon="edit")
        curve_output = w.Output()
        def curve_action(edit=False):
            with curve_output:
                curve_output.clear_output(wait=True)
                try:
                    from .turbine import power_curve
                    from IPython.display import display
                    import matplotlib.pyplot as plt
                    cfg = self.get_settings()
                    if edit:
                        cfg.power_curve_mode = "csv"
                    curve = power_curve(self.root, cfg)
                    if edit:
                        self.controls["power_curve_points"].value = curve.to_csv(index=False)
                        self.controls["power_curve_mode"].value = "edited"
                    import numpy as np
                    x = np.unique(np.r_[np.linspace(0, max(cfg.cut_out_mps*1.05, curve.speed_mps.max()), 1000), cfg.cut_in_mps, cfg.rated_speed_mps, cfg.cut_out_mps])
                    y = np.interp(x, curve.speed_mps, curve.power_kw)
                    y[(x < cfg.cut_in_mps) | (x >= cfg.cut_out_mps)] = 0
                    fig, ax = plt.subplots(figsize=(8, 3))
                    ax.plot(x, y, label="Operating curve")
                    ax.scatter(curve.speed_mps, curve.power_kw, s=8, label="Input points")
                    for speed, label in ((cfg.cut_in_mps, "Cut-in / slack"), (cfg.rated_speed_mps, "Rated"), (cfg.cut_out_mps, "Cut-off")):
                        ax.axvline(speed, ls=":", label=label)
                    ax.set(xlabel="Velocity (m/s)", ylabel="Power (kW)")
                    ax.legend(fontsize=8)
                    display(fig)
                    plt.close(fig)
                    print("CSV/edited curves retain your points; rated speed shapes only generated curves. Rerun all three stages after edits.")
                except (ValueError, FileNotFoundError) as error:
                    print(f"Please update the curve/settings: {error}")
        preview.on_click(lambda _: curve_action())
        load_points.on_click(lambda _: curve_action(True))
        sections[3].children += (w.HTML("<p>Slack equals cut-in. Generated curves use a cubic rise to rated power, then a plateau up to cut-off. CSV/edited points use linear interpolation. Powers are kW; speeds are m/s.</p>"), w.HBox([load_points, preview]), curve_output)

    def _source_changed(self, change):
        presets = {
            "coops": {"site": "LIS1016", "input_path": "inputs/coops/depth_bins", "time_zone": "unspecified", "hub_bin": 13},
            "verdant": {"site": "Verdant_B", "input_path": "inputs/verdant", "time_zone": "UTC", "hub_bin": 13},
            "standard_csv": {"site": "MySite", "input_path": "inputs/custom/my_adcp.csv", "time_zone": "unspecified", "hub_bin": 1},
        }
        for key, value in presets[change["new"]].items():
            self.controls[key].value = value
        # Source-specific geometry and excluded bins must not silently carry over.
        self.controls["water_depth_m"].value = "37.8" if change["new"] == "coops" else ""
        self.controls["excluded_bins"].value = ""
        if change["new"] == "verdant":
            self._apply_station_preset()
        if change["new"] in {"coops", "verdant"}:
            self.controls["ensemble_minutes"].value = 60 if change["new"] == "coops" else 10

    def _apply_station_preset(self, change=None):
        if self.controls["source"].value != "verdant":
            return
        sheets = [s.strip() for s in self.controls["verdant_sheets"].value.split(",") if s.strip()]
        preset = verdant_station_preset(sheets)
        if not preset:
            return
        self.controls["verdant_heading_offsets"].value = ", ".join(f"{x:g}" for x in preset["verdant_heading_offsets"])
        self.controls["excluded_bins"].value = ", ".join(str(b) for b in preset["excluded_bins"])
        self.controls["water_depth_m"].value = f"{preset['water_depth_m']:g}"

    def get_settings(self):
        if self.widget is None:
            return self.initial.validate()
        values = {key: control.value for key, control in self.controls.items()}
        for key, converter in (("verdant_sheets", str), ("verdant_heading_offsets", float), ("excluded_bins", int)):
            try:
                values[key] = tuple(converter(v.strip()) for v in values[key].split(",") if v.strip())
            except ValueError as error:
                raise ValueError(f"Check the comma-separated values for {key}.") from error
        values["water_depth_m"] = float(values["water_depth_m"]) if values["water_depth_m"].strip() else None
        return Settings(**values).validate()

    def _check(self, _):
        from IPython.display import display
        with self.feedback:
            self.feedback.clear_output()
            try:
                cfg = self.get_settings()
                from .config import input_file
                path = input_file(self.root, cfg.input_path)
                if cfg.energy_enabled:
                    from .turbine import power_curve
                    power_curve(self.root, cfg)
                print(f"Settings valid. Source: {cfg.source}; inputs: {path.name}.")
                print("Now run the Preprocess cell to check the contents and available bins.")
            except (ValueError, FileNotFoundError) as error:
                print(f"Please update the settings: {error}")

    def show(self):
        from IPython.display import display
        if self.widget is not None:
            display(self.widget)
        else:
            print(self.initial)
        return self


def show_preprocessing(assessment):
    from IPython.display import display
    display(assessment.overview())
    display(assessment.tables["quality_control"])
    display(assessment.tables["depth_bins"])
    display(assessment.tables["bin_coverage"])
    for message in assessment.messages:
        print("• " + message)


def show_results(assessment):
    from IPython.display import display, Markdown
    if not assessment.processed:
        raise ValueError("Run Process first.")
    print(f"Floodward axis: {assessment.bearing:.2f}° true. Positive streamwise flow = flood.")
    for title, key in (("Phase summary", "phase_summary"), ("Tidal-cycle fit", "cycle_fit"),
                       ("Vertical-profile fits", "profile_fits"), ("Depth-averaged residual variability", "variability_depth_averaged"),
                       ("Energy estimate", "energy_summary"),
                       ("Original postprocessing checklist", "postprocessing_catalog")):
        if key in assessment.tables:
            display(Markdown(f"**{title}**"))
            frame = assessment.tables[key]
            display(frame if len(frame) else "No eligible data for this calculation.")
    for message in assessment.messages:
        print("• " + message)
    try:
        import ipywidgets as w
    except ImportError:
        print("All tables are available in assessment.tables and exported as CSV.")
        return
    selector = w.Dropdown(options=sorted(assessment.tables), description="Result table", layout=w.Layout(width="650px"))
    output = w.Output()
    def show_table(_=None):
        with output:
            output.clear_output(wait=True)
            frame = assessment.tables[selector.value]
            print(f"{len(frame):,} rows. Showing the first 200; the complete table is exported as CSV.")
            display(frame.head(200))
    selector.observe(show_table, names="value")
    display(w.VBox([selector, output]))
    show_table()


def explore(assessment):
    from IPython.display import display, Image
    if not assessment.processed:
        raise ValueError("Run Process before exploring.")
    try:
        import ipywidgets as w
    except ImportError:
        for path in assessment.figure_paths.values():
            display(Image(filename=str(path)))
        return
    import matplotlib.pyplot as plt
    from .plots import COLORS, style
    style()
    bins = assessment.tables["depth_bins"]
    selector = w.Dropdown(options=[(f"Bin {int(r.bin)} · {r.depth_m:.2f} m ({r.depth_reference})", int(r.bin)) for r in bins.itertuples()], description="Depth bin", layout=w.Layout(width="600px"))
    phase = w.Dropdown(options=["ALL", "FLOOD", "EBB", "SLACK"], description="Phase")
    time_range = w.IntRangeSlider(value=(0, 100), min=0, max=100, step=1, description="Record (%)", continuous_update=False, layout=w.Layout(width="600px"))
    output = w.Output()

    def refresh(_=None):
        data = assessment.tables["depth_resolved"]
        sub = data[data.bin == selector.value].sort_values("time")
        n = len(sub)
        lo, hi = time_range.value
        sub = sub.iloc[int(n*lo/100):max(int(n*hi/100), int(n*lo/100)+1)]
        if phase.value != "ALL":
            sub = sub[sub.phase == phase.value]
        with output:
            output.clear_output(wait=True)
            fig, ax = plt.subplots(figsize=(10, 3.5))
            for label, group in sub.groupby("phase"):
                ax.scatter(group.time, group.along_mps, s=5, color=COLORS[label], label=label.title())
            ax.set(xlabel=f"Time ({assessment.dataset.metadata['time_zone']})", ylabel="Streamwise velocity (m/s)", title=selector.label)
            if len(sub):
                ax.legend()
            fig.autofmt_xdate()
            plt.show()
            plt.close(fig)
    for control in (selector, phase, time_range):
        control.observe(refresh, names="value")
    display(w.VBox([selector, phase, time_range, output]))
    refresh()
    if assessment.figure_paths:
        gallery = w.Dropdown(options=[(k.replace("_", " ").title(), str(v)) for k, v in assessment.figure_paths.items()], description="Saved figure", layout=w.Layout(width="600px"))
        gallery_output = w.Output()

        def show_figure(_=None):
            with gallery_output:
                gallery_output.clear_output(wait=True)
                display(Image(filename=gallery.value, width=950))
        gallery.observe(show_figure, names="value")
        display(w.VBox([gallery, gallery_output]))
        show_figure()
