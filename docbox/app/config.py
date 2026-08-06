"""Configuration, read once from the environment.

Everything has a working default so `make run` works on a fresh checkout.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("DOCBOX_DATA_DIR", "./data")).resolve())
    library_dir: Path = field(init=False)
    db_path: Path = field(init=False)

    # Auth
    secret: str = field(default_factory=lambda: _env("DOCBOX_SECRET", ""))
    session_days: int = field(default_factory=lambda: _env_int("DOCBOX_SESSION_DAYS", 90))

    # Library layout
    inbox_name: str = field(default_factory=lambda: _env("DOCBOX_INBOX_NAME", "Inbox"))
    max_upload_mb: int = field(default_factory=lambda: _env_int("DOCBOX_MAX_UPLOAD_MB", 64))

    # Local LLM (Ollama)
    ollama_url: str = field(default_factory=lambda: _env("DOCBOX_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"))
    llm_model: str = field(default_factory=lambda: _env("DOCBOX_LLM_MODEL", "qwen2.5:3b"))
    vision_model: str = field(default_factory=lambda: _env("DOCBOX_VISION_MODEL", ""))
    llm_timeout: int = field(default_factory=lambda: _env_int("DOCBOX_LLM_TIMEOUT", 180))
    llm_enabled: bool = field(default_factory=lambda: _env_bool("DOCBOX_LLM_ENABLED", True))

    # Text extraction
    ocr_enabled: bool = field(default_factory=lambda: _env_bool("DOCBOX_OCR_ENABLED", True))
    ocr_langs: str = field(default_factory=lambda: _env("DOCBOX_OCR_LANGS", "eng+deu"))
    ocr_max_pages: int = field(default_factory=lambda: _env_int("DOCBOX_OCR_MAX_PAGES", 3))
    extract_max_chars: int = field(default_factory=lambda: _env_int("DOCBOX_EXTRACT_MAX_CHARS", 6000))

    # Worker
    worker_enabled: bool = field(default_factory=lambda: _env_bool("DOCBOX_WORKER_ENABLED", True))
    worker_poll_seconds: float = field(default_factory=lambda: float(_env("DOCBOX_WORKER_POLL_SECONDS", "2")))
    max_attempts: int = field(default_factory=lambda: _env_int("DOCBOX_MAX_ATTEMPTS", 3))

    def __post_init__(self) -> None:
        self.library_dir = Path(_env("DOCBOX_LIBRARY_DIR", str(self.data_dir / "library"))).resolve()
        self.db_path = Path(_env("DOCBOX_DB", str(self.data_dir / "docbox.db"))).resolve()

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.library_dir.mkdir(parents=True, exist_ok=True)
        (self.library_dir / self.inbox_name).mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def resolve_secret(self) -> str:
        """Persist a generated secret so sessions survive a restart."""
        if self.secret:
            return self.secret
        keyfile = self.data_dir / "secret.key"
        if keyfile.exists():
            self.secret = keyfile.read_text().strip()
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.secret = secrets.token_urlsafe(48)
            keyfile.write_text(self.secret)
            keyfile.chmod(0o600)
        return self.secret


settings = Settings()
