"""User-supplied or explicitly idealized turbine curves."""
from io import StringIO
import numpy as np
import pandas as pd
from .config import input_file


def rotor_area_m2(cfg):
    """Swept area from the rotor diameter, or the area implied by rated power at rated speed."""
    if cfg.rotor_diameter_m is not None:
        return np.pi*cfg.rotor_diameter_m**2/4
    return 2e3*cfg.rated_kw/(cfg.water_density_kgm3*cfg.power_coefficient*cfg.drivetrain_efficiency*cfg.rated_speed_mps**3)


def power_curve(root, cfg):
    if cfg.power_curve_mode == "csv":
        try:
            curve = pd.read_csv(input_file(root, cfg.power_curve))
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"Power-curve CSV not found: {cfg.power_curve}. Either add that file under inputs/, "
                "or set power_curve_mode to 'edited' to use power_curve_points from config.json."
            ) from error
    elif cfg.power_curve_mode == "edited":
        curve = pd.read_csv(StringIO(cfg.power_curve_points))
    else:
        # P = 0.5 rho A Cp eta U^3 between cut-in and rated, rated power up to cut-out (IEC TS 62600-200).
        below = cfg.cut_in_mps*(1-1e-6)
        speeds = np.unique(np.r_[0, below, np.linspace(cfg.cut_in_mps, cfg.rated_speed_mps, 201), cfg.cut_out_mps])
        power = np.minimum(1e-3*0.5*cfg.water_density_kgm3*rotor_area_m2(cfg)*cfg.power_coefficient
                           * cfg.drivetrain_efficiency*speeds**3, cfg.rated_kw)
        power[speeds < cfg.cut_in_mps] = 0
        curve = pd.DataFrame({"speed_mps": speeds, "power_kw": power})
    if not {"speed_mps", "power_kw"}.issubset(curve):
        raise ValueError("Power curve requires speed_mps,power_kw columns.")
    curve = curve[["speed_mps", "power_kw"]].apply(pd.to_numeric, errors="coerce").sort_values("speed_mps")
    if len(curve) < 2 or curve.speed_mps.duplicated().any() or not np.isfinite(curve.to_numpy()).all() or (curve < 0).any().any():
        raise ValueError("Supply at least two unique, finite, nonnegative speed/power pairs.")
    if curve.power_kw.max() > cfg.rated_kw*1.001:
        raise ValueError("Curve exceeds rated power; revise the points or rated power.")
    return curve.reset_index(drop=True)
