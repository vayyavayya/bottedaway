"""Small JSON helpers for the capture side: settings.json (shared with config.models(), so writes are
read-modify-write and keep foreign keys), calibration.json, probe results. Atomic replace on write."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROUTES = ("clipboard", "ocr")


def _data_dir() -> Path:
    from radbrain import config
    return config.data_dir()


def settings_path() -> Path:
    return _data_dir() / "settings.json"


def probe_path() -> Path:
    return _data_dir() / "logs" / "probe_citrix.json"


def load_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {} if default is None else default


def save_json(path: Path, data) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def load_settings() -> dict:
    s = load_json(settings_path())
    return s if isinstance(s, dict) else {}


def update_settings(**kv) -> dict:
    s = load_settings()
    s.update(kv)
    save_json(settings_path(), s)
    return s


def current_route() -> str:
    """settings.json "route" -> probe_citrix.json recommended_route -> "ocr"."""
    r = str(load_settings().get("route") or "").lower()
    if r in ROUTES:
        return r
    rec = str((load_json(probe_path()) or {}).get("recommended_route") or "").lower()
    return rec if rec in ROUTES else "ocr"
