"""Three explicit stages with frozen settings and reproducible output run logs."""
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import pandas as pd
from .config import Settings, input_file
from .loaders import load
from . import analysis


@dataclass
class Assessment:
    root: Path
    settings: Settings
    dataset: object
    tables: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    nominal_seconds: float = 0
    bearing: float | None = None
    processed: bool = False
    output_directory: Path | None = None
    figure_paths: dict = field(default_factory=dict)

    def overview(self):
        data = self.dataset.data
        return pd.DataFrame([{
            "source": self.settings.source, "site": self.settings.site,
            "start": data.time.min(), "end": data.time.max(),
            "time_zone": self.dataset.metadata["time_zone"], "bins": data.bin.nunique(),
            "timestamps": data.time.nunique(), "sample_minutes": self.nominal_seconds / 60,
            "valid_velocity_percent": 100 * data.valid_velocity.mean(),
        }])


def preprocess(root, settings=None):
    settings = deepcopy(settings or Settings())
    root = Path(root).resolve()
    dataset = load(root, settings)
    avg, nominal = analysis.depth_average(dataset.data, settings)
    result = Assessment(root, settings, dataset, messages=list(dataset.messages), nominal_seconds=nominal)
    result.tables["depth_averaged"] = avg
    result.tables["depth_resolved"] = dataset.data
    result.tables["depth_bins"] = dataset.data[["bin", "depth_m", "depth_reference", "height_above_bed_m"]].drop_duplicates().sort_values("bin")
    result.tables["quality_control"] = pd.DataFrame([dataset.metadata["quality_control"]])
    result.tables["bin_coverage"] = dataset.data.groupby("bin").agg(
        samples=("valid_velocity", "size"), valid_samples=("valid_velocity", "sum"),
        valid_fraction=("valid_velocity", "mean")).reset_index()
    if avg.block.max() > 0:
        result.messages.append(f"Found {int(avg.block.max())} sampling gaps. Smoothing, cycles and time weights will not bridge those gaps.")
    missing = int(avg.east_mps.isna().sum())
    if missing:
        result.messages.append(f"{missing:,} depth-averaged timestamps fail the selected bin-coverage requirement.")
    if missing > 0.5 * len(avg):
        result.messages.append("More than half the record has no valid depth average. Review per-bin coverage and exclude unsupported bins before interpreting phase/profile results.")
    result.messages.append("Depth averages are arithmetic vector means over retained valid bins, not full-column integrals.")
    return result


def process(assessment):
    assessment.processed = False
    cfg = assessment.settings
    # Always start from the normalized input so repeated execution is deterministic.
    avg, nominal = analysis.depth_average(assessment.dataset.data, cfg)
    if avg.east_mps.notna().sum() < 0.5 * len(avg):
        raise ValueError("Fewer than half of depth averages pass coverage. Review the bin_coverage table and exclude poorly sampled bins or explicitly lower the coverage requirement, then rerun Preprocess.")
    avg, resolved, bearing = analysis.classify(avg, assessment.dataset.data, cfg)
    tables = {k: assessment.tables[k] for k in ("depth_bins", "quality_control", "bin_coverage")}
    tables["depth_averaged"], tables["depth_resolved"] = avg, resolved
    tables["phase_summary"] = analysis.phase_summary(avg, bearing, cfg)
    tables["cycles"], tables["cycle_ensemble"], tables["cycle_fit"], tables["cycle_members"] = analysis.tidal_cycles(avg, cfg)
    tables["profiles"], tables["event_peak_profiles"], tables["profile_fits"], tables["profile_fit_curves"] = analysis.profiles(resolved, cfg)
    tables["variability_by_bin"], tables["variability_depth_averaged"] = analysis.turbulence(resolved, avg, cfg)
    messages = list(assessment.messages)
    messages.append("Residual intensity is variability of the supplied ensembles. Six/ten-minute averages cannot resolve burst-scale turbulence or a Doppler-noise spectrum.")
    if not len(tables["cycles"]):
        messages.append("No complete cycles met the duration/gap criteria; cycle fitting was skipped.")
    if cfg.energy_enabled:
        from .turbine import power_curve
        tables["power_curve"] = power_curve(assessment.root, cfg)
        tables["energy_bins"], tables["energy_summary"] = analysis.energy(resolved, tables["power_curve"], cfg)
        messages.append("Single-turbine AEP follows IEC TS 62600-200, extrapolating this record's hub speed probabilities to 8,766 hours; it omits seasonal corrections.")
    from . import postprocessing as original
    tables.update(original.compute(assessment, tables, avg, resolved, bearing))
    tables.update(original.distributions(avg))
    tables.update(original.fixed_period_cosine(avg))
    tables["postprocessing_catalog"] = original.catalog(tables)
    if cfg.profile_coordinate_mode == "legacy_normalized":
        messages.append("Original normalized profile fits use velocity-inferred bin coordinates, not confirmed physical z/h. Their alpha/beta and z0/h are retained as legacy diagnostics alongside the physical-coordinate fits.")
    messages.append("Original TI tables retain the horizontal-speed rolling denominator; the separate residual-intensity tables use the newer along-speed definition. Pearson p-values are descriptive legacy outputs and assume independent samples, which these data need not satisfy.")
    assessment.tables, assessment.bearing = tables, bearing
    assessment.messages = list(dict.fromkeys(messages))
    assessment.processed = True
    return assessment


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def postprocess(assessment):
    if not assessment.processed:
        raise ValueError("Run the processing step before exporting results.")
    from .config import output_run_name, output_station_tag
    from .plots import save_figures
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run = output_run_name(assessment.settings, stamp)
    file_tag = output_station_tag(assessment.settings)
    file_prefix = f"{file_tag}_" if file_tag else ""
    output = assessment.root / "outputs"
    csv_dir = output / "csv" / run
    fig_dir = output / "figures" / run
    csv_dir.mkdir(parents=True, exist_ok=False)
    fig_dir.mkdir(parents=True, exist_ok=False)
    run_log_path = csv_dir / "run_log.json"
    run_log_path.write_text(json.dumps({"run": run, "status": "exporting", "settings": assessment.settings.to_dict()}, indent=2), encoding="utf-8")
    try:
        for name, frame in assessment.tables.items():
            if len(frame.columns):
                frame.to_csv(csv_dir / f"{file_prefix}{name}.csv", index=False)
        figure_paths = save_figures(assessment, fig_dir, file_prefix=file_prefix)
    except Exception as error:
        run_log_path.write_text(json.dumps({"run": run, "status": "failed", "error": str(error), "settings": assessment.settings.to_dict()}, indent=2), encoding="utf-8")
        raise
    files = list(assessment.dataset.files)
    if assessment.settings.energy_enabled and assessment.settings.power_curve_mode == "csv":
        files.append(str(input_file(assessment.root, assessment.settings.power_curve)))
    if "annual_events" in assessment.tables and not assessment.tables["annual_events"].empty:
        annual_dir = input_file(assessment.root, assessment.settings.annual_input_path)
        files.extend(str(annual_dir / name) for name in assessment.tables["annual_events"].source_file.unique())
    package_versions = {}
    for package in ("numpy", "pandas", "matplotlib", "openpyxl", "scipy"):
        package_versions[package] = importlib.metadata.version(package)
    run_log = {
        "run": run, "status": "complete", "created_utc": stamp, "settings": assessment.settings.to_dict(),
        "dataset": assessment.dataset.metadata, "flood_bearing_degT": assessment.bearing,
        "nominal_interval_seconds": assessment.nominal_seconds, "python": platform.python_version(),
        "packages": package_versions, "notes": assessment.messages,
        "input_files": [{"path": str(Path(f).relative_to(assessment.root)), "sha256": hash_file(f)} for f in files],
        "backend_files": [{"path": str(f.relative_to(assessment.root)), "sha256": hash_file(f)}
                          for f in sorted((assessment.root / "backend" / "tidal").glob("*.py"))],
        "figures": {k: str(v.relative_to(output)) for k, v in figure_paths.items()},
    }
    run_log_path.write_text(json.dumps(run_log, indent=2), encoding="utf-8")
    assessment.output_directory = csv_dir
    assessment.figure_paths = figure_paths
    return pd.DataFrame({"result": ["CSV tables and run log", "Figures"],
                         "folder": [str(csv_dir), str(fig_dir)]})
