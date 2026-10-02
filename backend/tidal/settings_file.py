"""Load explicit JSON settings with actionable validation errors."""
from dataclasses import fields
from pathlib import Path
import json
from .config import Settings

# Grouping objects in config.json. They are not settings themselves.
SECTIONS = {
    "data_and_quality",
    "flow_cycles_profiles",
    "turbine_and_power",
    "comparisons",
}


def flatten_settings(data):
    """Accept either a flat settings object or the four section objects."""
    flat = {}
    for key, value in data.items():
        if key in SECTIONS:
            if not isinstance(value, dict):
                raise ValueError(f"Section '{key}' must be a JSON object of settings.")
            for name, item in value.items():
                if name in SECTIONS:
                    raise ValueError(f"Do not nest section '{name}' inside '{key}'.")
                if name in flat:
                    raise ValueError(f"Duplicate JSON setting: {name}")
                flat[name] = item
            continue
        if key in flat:
            raise ValueError(f"Duplicate JSON setting: {key}")
        flat[key] = value
    return flat


def load_settings(root, path="config.json"):
    base = Path(root).resolve()
    config_path = (base / path).resolve()
    if not config_path.is_relative_to(base):
        raise ValueError("Choose a configuration file inside the repository.")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON setting: {key}")
            result[key] = value
        return result
    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_pairs)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}") from error
    if not isinstance(data, dict):
        raise ValueError("Settings JSON must contain an object of named settings.")
    data = flatten_settings(data)
    defaults = Settings()
    names = {f.name for f in fields(Settings)}
    unknown = set(data)-names
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
    if "source" not in data or "input_path" not in data or "site" not in data:
        raise ValueError("Include source, site, and input_path; see CONFIGURATION.md.")
    for key, value in list(data.items()):
        if key == "power_curve_points":
            if not isinstance(value, list) or len(value) < 2:
                raise ValueError("power_curve_points must be an array of at least two [speed_mps, power_kw] pairs.")
            for pair in value:
                if not isinstance(pair, list) or len(pair) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in pair):
                    raise ValueError("Each power_curve_points entry must be [speed_mps, power_kw], using numbers.")
            data[key] = "speed_mps,power_kw\n" + "\n".join(f"{speed},{power}" for speed, power in value)
            continue
        default = getattr(defaults, key)
        valid = False
        if key == "water_depth_m":
            valid = value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))
        elif isinstance(default, bool):
            valid = isinstance(value, bool)
        elif isinstance(default, int):
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif isinstance(default, float):
            valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        elif isinstance(default, tuple):
            item_type = str if key == "verdant_sheets" else int if key == "excluded_bins" else (int, float)
            valid = isinstance(value, list) and all(isinstance(x, item_type) and not isinstance(x, bool) for x in value)
            if valid:
                data[key] = tuple(value)
        else:
            valid = isinstance(value, str)
        if not valid:
            raise ValueError(f"Invalid value/type for '{key}'. See CONFIGURATION.md; numbers must not be quoted.")
    if "slack_mps" in data and data["slack_mps"] != data.get("cut_in_mps", defaults.cut_in_mps):
        raise ValueError("Slack equals cut-in: remove slack_mps or set it equal to cut_in_mps.")
    cfg = Settings(**data).validate()
    if cfg.energy_enabled:
        from .turbine import power_curve
        power_curve(root, cfg)
    return cfg
