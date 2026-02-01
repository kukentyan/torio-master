import json
import os
from typing import Any

class ConfigManager:
    DEFAULT_CONFIG = {
        "keybinds": {
            "brightness": "g",
            "zoom": "c",
            "sprint": "p",
            "autoclicker_left": "z",
            "autoclicker_right": "x"
        },
        "feature_states": {
            "brightness": False,
            "zoom": False,
            "sprint": False,
            "coordinates": False,
            "speed": False,
            "reach": False,
            "autoclicker": False,
            "antiknockback": False,
            "hitbox": False,
            "streamprotect": False,
            "nohurtcam": False,
            "truesight": False,
            "timechanger": False,
            "fastitem": False,
            "systemtray": False
        },
        "feature_settings": {
            "speed": {"speed": 0.5},
            "reach": {"reach": 3.0},
            "autoclicker": {
                "left_cps": 10.0,
                "right_cps": 10.0,
                "left_enabled": True,
                "right_enabled": True
            },
            "hitbox": {"hitbox": 1.0},
            "antiknockback": {
                "xz": 0.8,
                "y": 0.8
            }
        }
    }

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_or_create()

    def _load_or_create(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                return self._deep_merge(self.DEFAULT_CONFIG.copy(), loaded)
        else:
            self._save(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()

    def _deep_merge(self, default: dict, override: dict) -> dict:
        for key, value in override.items():
            if isinstance(value, dict) and key in default and isinstance(default[key], dict):
                default[key] = self._deep_merge(default[key], value)
            else:
                default[key] = value
        return default

    def _save(self, data: dict):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def get_keybind(self, feature: str) -> str | None:
        return self.config["keybinds"].get(feature)

    def set_keybind(self, feature: str, key: str):
        self.config["keybinds"][feature] = key
        self._save(self.config)

    def get_state(self, feature: str, default: bool = False) -> bool:
        return self.config["feature_states"].get(feature, default)

    def set_state(self, feature: str, state: bool):
        self.config["feature_states"][feature] = state
        self._save(self.config)

    def get_setting(self, feature: str, key: str, default: Any = None) -> Any:
        return self.config["feature_settings"].get(feature, {}).get(key, default)

    def set_setting(self, feature: str, key: str, value: Any):
        if feature not in self.config["feature_settings"]:
            self.config["feature_settings"][feature] = {}
        self.config["feature_settings"][feature][key] = value
        self._save(self.config)

    def save(self):
        self._save(self.config)