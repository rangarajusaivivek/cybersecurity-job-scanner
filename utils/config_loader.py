"""utils/config_loader.py — Load YAML config + .env overrides."""
import os
import yaml
from dotenv import load_dotenv

load_dotenv()

def load_config(path: str = "config/config.yaml") -> dict:
    fallback = "config/config.example.yaml"
    target = path if os.path.exists(path) else fallback
    with open(target) as f:
        raw = f.read()
    # Substitute ${ENV_VAR} placeholders
    for key, val in os.environ.items():
        raw = raw.replace(f"${{{key}}}", val)
    return yaml.safe_load(raw)
