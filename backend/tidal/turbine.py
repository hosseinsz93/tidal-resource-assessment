"""User-supplied or explicitly idealized turbine curves."""
from io import StringIO
import numpy as np
import pandas as pd
from .config import input_file


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
        speeds = np.unique(np.r_[0, np.linspace(cfg.cut_in_mps, cfg.rated_speed_mps, 201), cfg.cut_out_mps])
        fraction = (speeds**3-cfg.cut_in_mps**3)/(cfg.rated_speed_mps**3-cfg.cut_in_mps**3)
        curve = pd.DataFrame({"speed_mps": speeds, "power_kw": cfg.rated_kw*np.clip(fraction, 0, 1)})
    if not {"speed_mps", "power_kw"}.issubset(curve):
        raise ValueError("Power curve requires speed_mps,power_kw columns.")
    curve = curve[["speed_mps", "power_kw"]].apply(pd.to_numeric, errors="coerce").sort_values("speed_mps")
    if len(curve) < 2 or curve.speed_mps.duplicated().any() or not np.isfinite(curve.to_numpy()).all() or (curve < 0).any().any():
        raise ValueError("Supply at least two unique, finite, nonnegative speed/power pairs.")
    if curve.power_kw.max() > cfg.rated_kw*1.001:
        raise ValueError("Curve exceeds rated power; revise the points or rated power.")
    return curve.reset_index(drop=True)
