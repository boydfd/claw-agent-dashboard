"""Config service — read/write /data/config.json with LLM config overrides."""
import json
from pathlib import Path

from ..config import DATA_DIR

CONFIG_PATH = Path(DATA_DIR) / "config.json"

DEFAULT_CONFIG = {
    "llm": {
        "default": {
            "openai_base_url": "",
            "api_key": "",
            "model_name": "gpt-4o-mini",
        },
        "overrides": {},
    },
    "features": {
        "auto_summary": True,
    },
}


def _deep_merge(base: dict, override: dict):
    """Recursively merge override into base (in-place)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _migrate_config(data: dict) -> dict:
    """Migrate old flat config format to new nested format."""
    if "llm" in data:
        return data  # Already new format

    new_config = {
        "llm": {
            "default": {
                "openai_base_url": data.get("openai_base_url", ""),
                "api_key": data.get("api_key", ""),
                "model_name": data.get("model_name", "gpt-4o-mini"),
            },
            "overrides": {},
        },
        "features": {
            "auto_summary": True,
        },
    }
    _write_raw(new_config)
    return new_config


def _write_raw(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            data = _migrate_config(data)
            result = json.loads(json.dumps(DEFAULT_CONFIG))
            _deep_merge(result, data)
            return result
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_CONFIG))


def write_config(data: dict) -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = json.loads(json.dumps(DEFAULT_CONFIG))
    _deep_merge(result, data)
    _write_raw(result)
    return result


def get_llm_config(purpose: str = "default") -> dict:
    """Get LLM config for a specific purpose, with fallback to default."""
    config = read_config()
    default = config.get("llm", {}).get("default", {})
    if purpose == "default":
        return dict(default)
    override = config.get("llm", {}).get("overrides", {}).get(purpose, {})
    result = dict(default)
    for key, value in override.items():
        if value:  # Non-empty string = override
            result[key] = value
    return result
