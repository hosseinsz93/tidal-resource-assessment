"""Explicit scientific and file settings shared by notebook and batch users."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import math
import re


# Station-specific Verdant values, selected from verdant_sheets (see CONFIGURATION.md, Verdant stations).
VERDANT_STATIONS = {
    ("Station A", "Station A-2"): {"site": "Verdant_A", "verdant_heading_offsets": (-0.07, 0.04),
                                   "excluded_bins": (39, 40, 41, 42, 43), "water_depth_m": 24.0},
    ("Station B", "Station B-2"): {"site": "Verdant_B", "verdant_heading_offsets": (-5.53, 3.20),
                                   "excluded_bins": (45, 46, 47, 48, 49), "water_depth_m": 26.9},
}

# Verified NOAA deployment metadata for supported CO-OPS examples. These values
# are applied only when the matching station is selected; other CO-OPS sites
# remain explicit user inputs.
COOPS_STATIONS = {
    "LIS1016": {
        "coops_depth_reference": "below_surface",
        "coops_adcp_orientation": "upward",
        "coops_nominal_water_depth_m": 47.0,
        "water_depth_m": 47.18,
        "coops_instrument_height_above_bed_m": 5.18,
        "coops_bin1_center_distance_m": 4.23,
        "coops_bin_size_m": 2.0,
        "flood_reference_deg": 250.0,
        # The lowest three cells extend to z/h = 0.284; 0.30 keeps a
        # three-point physical log-law fit without automatic expansion.
        "near_bed_fraction": 0.30,
    },
}


def coops_station_preset(site):
    """Verified deployment geometry for a supported NOAA CO-OPS station."""
    return COOPS_STATIONS.get(str(site).strip().upper(), {})


def apply_coops_station_preset(settings):
    """Apply authoritative station metadata to an in-memory settings object."""
    preset = coops_station_preset(settings.site) if settings.source == "coops" else {}
    for key, value in preset.items():
        setattr(settings, key, value)
    return preset


def verdant_station_preset(sheets):
    return VERDANT_STATIONS.get(tuple(sheets), {})


def verdant_station_names(sheets):
    """Unique station labels from sheet names, e.g. Station A / Station A-2 -> ['Station A']."""
    names = []
    for sheet in sheets or ():
        name = str(sheet).strip()
        if name.endswith("-2"):
            name = name[:-2].rstrip()
        if name and name not in names:
            names.append(name)
    return names


def output_station_tag(settings):
    """Path-safe station tag for Verdant run folders and exported file names."""
    if getattr(settings, "source", None) != "verdant":
        return ""
    names = verdant_station_names(getattr(settings, "verdant_sheets", ()))
    return "".join(name.replace(" ", "") for name in names)


def output_run_name(settings, stamp):
    """Unique export folder name: site_source[_StationA]_timestamp."""
    parts = [settings.site, settings.source]
    tag = output_station_tag(settings)
    if tag:
        parts.append(tag)
    parts.append(stamp)
    return "_".join(parts)


@dataclass
class Settings:
    source: str = "coops"
    site: str = "LIS1016"
    input_path: str = "inputs/coops/depth_bins"
    time_zone: str = "unspecified"  # Do not guess a CO-OPS download's timezone.
    coops_depth_reference: str = "unknown"
    coops_adcp_orientation: str = "unknown"
    coops_nominal_water_depth_m: float | None = None
    coops_instrument_height_above_bed_m: float | None = None
    coops_bin1_center_distance_m: float | None = None
    coops_bin_size_m: float | None = None
    verdant_sheets: tuple = ("Station B", "Station B-2")
    verdant_heading_offsets: tuple = (-5.53, 3.20)
    excluded_bins: tuple = ()
    max_speed_mps: float = 6.0
    min_bin_coverage: float = 1.0
    axis_method: str = "pca"
    flood_reference_deg: float = 252.38
    slack_mps: float = 0.4
    smooth_samples: int = 3
    gap_factor: float = 1.5
    min_cycle_hours: float = 6.0
    max_cycle_hours: float = 18.0
    ensemble_minutes: int = 60
    noise_std_mps: float = 0.0
    water_depth_m: float | None = None
    near_bed_fraction: float = 0.2
    hub_bin: int = 13
    power_curve: str = "inputs/turbine/power_curve_generated.csv"
    rated_kw: float = 110.0
    rated_speed_mps: float = 2.0
    power_curve_mode: str = "csv"
    power_curve_points: str = "speed_mps,power_kw\n0,0\n0.4,0\n2,110\n3.2,110"
    rotor_diameter_m: float | None = None  # None: implied by rated power at rated speed.
    power_coefficient: float = 0.40
    drivetrain_efficiency: float = 0.90
    water_density_kgm3: float = 1025.0
    cut_in_mps: float = 0.4
    cut_out_mps: float = 3.2
    speed_bin_width: float = 0.1
    turbine_count: int = 24
    availability: float = 1.0
    energy_enabled: bool = True
    profile_coordinate_mode: str = "legacy_normalized"
    compare_annual_records: bool = True
    annual_input_path: str = "inputs/coops/annual"

    def validate(self):
        self.slack_mps = self.cut_in_mps
        if self.power_curve_mode not in {"csv", "edited", "generated"}:
            raise ValueError("Choose CSV, edited points, or generated power curve.")
        if self.source not in {"coops", "verdant", "standard_csv"}:
            raise ValueError("Choose coops, verdant, or standard_csv.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.site):
            raise ValueError("Site name must contain only letters, numbers, underscores or hyphens.")
        if self.axis_method not in {"pca", "doubled_angle"}:
            raise ValueError("Axis method must be pca or doubled_angle.")
        if self.profile_coordinate_mode not in {"physical", "legacy_normalized"}:
            raise ValueError("Profile coordinates must be physical or legacy_normalized.")
        if self.coops_depth_reference not in {"unknown", "below_surface", "above_bed"}:
            raise ValueError("Depth reference must be unknown, below_surface, or above_bed.")
        if self.coops_adcp_orientation not in {"unknown", "upward", "downward"}:
            raise ValueError("CO-OPS ADCP orientation must be unknown, upward, or downward.")
        positive = ["max_speed_mps", "gap_factor", "min_cycle_hours",
                    "max_cycle_hours", "ensemble_minutes", "rated_kw", "speed_bin_width"]
        for name in positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite.")
        for name in ("smooth_samples", "ensemble_minutes", "hub_bin", "turbine_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if any(not isinstance(b, int) or b < 1 for b in self.excluded_bins):
            raise ValueError("Excluded bins must be positive integers.")
        if not 0 < self.min_bin_coverage <= 1 or not 0 < self.availability <= 1:
            raise ValueError("Coverage and availability must be in (0, 1].")
        if not 0 < self.near_bed_fraction <= 1:
            raise ValueError("Near-bed fraction must be in (0, 1].")
        if not math.isfinite(self.flood_reference_deg):
            raise ValueError("Flood reference must be finite.")
        if not math.isfinite(self.noise_std_mps) or self.noise_std_mps < 0:
            raise ValueError("Noise standard deviation must be finite and nonnegative.")
        if not 0 < self.power_coefficient <= 16/27:
            raise ValueError("Power coefficient must be in (0, 16/27], the Betz limit.")
        if not 0 < self.drivetrain_efficiency <= 1:
            raise ValueError("Drivetrain efficiency must be in (0, 1].")
        if not math.isfinite(self.water_density_kgm3) or self.water_density_kgm3 <= 0:
            raise ValueError("Water density must be positive and finite.")
        if self.rotor_diameter_m is not None:
            if not math.isfinite(self.rotor_diameter_m) or self.rotor_diameter_m <= 0:
                raise ValueError("Rotor diameter must be positive, or None to derive it from the rated point.")
            if self.power_curve_mode == "generated":
                area = math.pi*self.rotor_diameter_m**2/4
                self.rated_speed_mps = (2e3*self.rated_kw/(self.water_density_kgm3*area*self.power_coefficient
                                                           * self.drivetrain_efficiency))**(1/3)
        if not (0 <= self.cut_in_mps < self.rated_speed_mps < self.cut_out_mps < float('inf')):
            raise ValueError("Require 0 <= cut-in < rated speed < cut-off.")
        if self.min_cycle_hours >= self.max_cycle_hours or self.gap_factor <= 1:
            raise ValueError("Cycle limits must increase and gap factor must exceed 1.")
        if self.water_depth_m is not None and (not math.isfinite(self.water_depth_m) or self.water_depth_m <= 0):
            raise ValueError("Water depth must be positive, or None when unknown.")
        geometry = ("coops_nominal_water_depth_m", "coops_instrument_height_above_bed_m",
                    "coops_bin1_center_distance_m", "coops_bin_size_m")
        for name in geometry:
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be positive, or None when unknown.")
        cell_geometry = (self.coops_instrument_height_above_bed_m,
                         self.coops_bin1_center_distance_m, self.coops_bin_size_m)
        if any(value is not None for value in cell_geometry) and not all(value is not None for value in cell_geometry):
            raise ValueError("CO-OPS cell geometry requires instrument height, bin-1 center distance, and bin size together.")
        if len(self.verdant_sheets) != len(self.verdant_heading_offsets):
            raise ValueError("Give one heading offset for each Verdant sheet/workbook.")
        if any(not math.isfinite(x) for x in self.verdant_heading_offsets):
            raise ValueError("Heading offsets must be finite.")
        return self

    def to_dict(self):
        return asdict(self)


@dataclass
class Dataset:
    data: object
    metadata: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)
    files: list = field(default_factory=list)


def input_file(root, relative):
    """All active inputs belong under inputs/, including user-supplied CSVs."""
    base = (Path(root) / "inputs").resolve()
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError("Choose a file or folder inside this repository's inputs/ folder.")
    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")
    return path
