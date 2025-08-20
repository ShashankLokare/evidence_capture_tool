from __future__ import annotations
import json, os

DEFAULTS = {
    "image_quality": 90,
    "embed_max_width_px": 1200,
    "theme": "light",
}

def config_dir() -> str:
    path = os.path.join(os.path.expanduser("~"), ".evidence_capture")
    os.makedirs(path, exist_ok=True)
    return path

def settings_path() -> str:
    return os.path.join(config_dir(), "settings.json")

def load_settings() -> dict:
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULTS.items():
                data.setdefault(k, v)
            return data
    except Exception:
        return DEFAULTS.copy()

def save_settings(data: dict) -> None:
    with open(settings_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
