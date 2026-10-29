import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def storage_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path / "storage"))