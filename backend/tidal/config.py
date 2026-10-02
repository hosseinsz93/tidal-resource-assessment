"""Explicit scientific and file settings shared by notebook and batch users."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import math
import re


@dataclass
class Settings:
    source: str = "coops"
    site: str = "LIS1016"
    input_path: str = "inputs/coops/depth_bins"
    time_zone: str = "unspecified"  # Do not guess a CO-OPS download's timezone.
    coops_depth_reference: str = "unknown"
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
        if self.axis_method not in {"pca", "doubled_angle", "fixed"}:
            raise ValueError("Axis method must be pca, doubled_angle, or fixed.")
        if self.profile_coordinate_mode not in {"physical", "legacy_normalized"}:
            raise ValueError("Profile coordinates must be physical or legacy_normalized.")
        if self.coops_depth_reference not in {"unknown", "below_surface", "above_bed"}:
            raise ValueError("Depth reference must be unknown, below_surface, or above_bed.")
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
        if not (0 <= self.cut_in_mps < self.rated_speed_mps < self.cut_out_mps < float('inf')):
            raise ValueError("Require 0 <= cut-in < rated speed < cut-off.")
        if self.min_cycle_hours >= self.max_cycle_hours or self.gap_factor <= 1:
            raise ValueError("Cycle limits must increase and gap factor must exceed 1.")
        if self.water_depth_m is not None and (not math.isfinite(self.water_depth_m) or self.water_depth_m <= 0):
            raise ValueError("Water depth must be positive, or None when unknown.")
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
