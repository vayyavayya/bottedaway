"""Point the app at a throwaway data dir before anything imports the settings."""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="docbox-tests-")

os.environ.setdefault("DOCBOX_DATA_DIR", _TMP)
os.environ.setdefault("DOCBOX_SECRET", "test-secret-not-for-real-use")
os.environ.setdefault("DOCBOX_LLM_ENABLED", "0")   # no Ollama in CI
os.environ.setdefault("DOCBOX_OCR_ENABLED", "0")   # no tesseract in CI
os.environ.setdefault("DOCBOX_WORKER_ENABLED", "0")  # tests drive the pipeline directly

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare() -> None:
    settings.ensure_dirs()
    db.init_db()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
