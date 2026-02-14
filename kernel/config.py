import json
from pathlib import Path


def load_config() -> dict:
    """Load config by merging defaults with user overrides."""
    root = Path.cwd()
    defaults_path = root / "config.default.json"
    overrides_path = root / "config.json"

    with open(defaults_path) as f:
        config = json.load(f)

    if overrides_path.exists():
        with open(overrides_path) as f:
            overrides = json.load(f)
        config = _deep_merge(config, overrides)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values win."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
