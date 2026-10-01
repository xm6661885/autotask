import os
import secrets
import yaml
from pathlib import Path
from werkzeug.security import generate_password_hash

DEFAULT_PASSWORD = "070827"

SEARCH_PATHS = [
    os.environ.get("AUTOTASK_CONFIG"),
    "/etc/autotask/config.yaml",
    os.path.expanduser("~/.config/autotask/config.yaml"),
]


def _default_config(scripts_dir, data_dir):
    return {
        "bind_host": "::",
        "port": 8990,
        "scripts_dir": scripts_dir,
        "data_dir": data_dir,
        "python_bin": "python3",
        "shell_bin": "bash",
        "poll_interval_sec": 2,
        "webhook_secret": os.environ.get("AUTOTASK_WEBHOOK_SECRET") or secrets.token_urlsafe(32),
        "password_hash": generate_password_hash(DEFAULT_PASSWORD),
        "secret_key": secrets.token_hex(32),
    }


def find_config_path():
    for p in SEARCH_PATHS:
        if p and os.path.isfile(p):
            return p
    return None


def load_config():
    path = find_config_path()
    if path is None:
        # No config anywhere: create a dev-friendly default under ~/.config
        path = os.path.expanduser("~/.config/autotask/config.yaml")
        home = os.path.expanduser("~")
        scripts_dir = os.path.join(home, "Automations", "scripts")
        data_dir = os.path.join(home, ".local", "share", "autotask")
        os.makedirs(scripts_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cfg = _default_config(scripts_dir, data_dir)
        save_config(cfg, path)
        return cfg, path

    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("webhook_secret"):
        cfg["webhook_secret"] = os.environ.get("AUTOTASK_WEBHOOK_SECRET") or secrets.token_urlsafe(32)
        save_config(cfg, path)
    return cfg, path


def save_config(cfg, path=None):
    if path is None:
        path = find_config_path()
    if path is None:
        raise RuntimeError("no config path known")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)


def ensure_dirs(cfg):
    Path(cfg["scripts_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["data_dir"]).mkdir(parents=True, exist_ok=True)
    Path(os.path.join(cfg["data_dir"], "logs")).mkdir(parents=True, exist_ok=True)
