import hashlib

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import ROOT, Settings
from inference.verify_models import verify_model


def test_health_does_not_claim_model_readiness():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_paths_are_relative_to_project_not_terminal(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert settings.asr_model_dir == ROOT / "models/asr/Fun-ASR-Nano-2512"


def test_environment_can_override_model_path(monkeypatch, tmp_path):
    monkeypatch.setenv("XIYANG_ASR_MODEL_DIR", str(tmp_path))
    assert Settings(_env_file=None).asr_model_dir == tmp_path


def test_same_size_model_corruption_is_detected(tmp_path):
    (tmp_path / "weights.bin").write_bytes(b"bad")
    spec = {"name": "fixture", "local_dir": ".", "files": [{
        "path": "weights.bin", "size": 3, "sha256": hashlib.sha256(b"yes").hexdigest(),
    }]}
    with pytest.raises(ValueError, match="SHA256"):
        verify_model(tmp_path, spec)


def test_manifest_cannot_escape_model_directory(tmp_path):
    spec = {"name": "fixture", "local_dir": ".", "files": [{"path": "../secret"}]}
    with pytest.raises(ValueError, match="无效路径"):
        verify_model(tmp_path, spec)
