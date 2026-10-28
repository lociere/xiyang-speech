"""Installation resource regressions: no GPU or network required."""
import sys
from types import ModuleType

import pytest
from packaging.requirements import Requirement
from packaging.utils import parse_wheel_filename

from inference.config import ROOT
from inference.tts.resources import WETEXT_FILES, local_wetext_resources


def test_missing_wetext_fails_before_sdk_import(tmp_path):
    with pytest.raises(RuntimeError, match="缺少 WeText"):
        with local_wetext_resources(tmp_path):
            pass


def test_lfs_pointer_is_not_accepted_as_resource(tmp_path):
    for relative in WETEXT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
    with pytest.raises(RuntimeError, match="LFS"):
        with local_wetext_resources(tmp_path):
            pass


def test_local_resource_binding_is_scoped_and_restored(tmp_path, monkeypatch):
    package = ModuleType("wetext")
    package.__path__ = []
    module = ModuleType("wetext.wetext")
    def forbidden_network(*args, **kwargs):
        raise AssertionError("network must not be used")
    module.snapshot_download = forbidden_network
    package.wetext = module
    monkeypatch.setitem(sys.modules, "wetext", package)
    monkeypatch.setitem(sys.modules, "wetext.wetext", module)
    for relative in WETEXT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="fixture"):
        with local_wetext_resources(tmp_path):
            assert module.snapshot_download("pengzhendong/wetext") == str(tmp_path)
            with pytest.raises(RuntimeError, match="未配置"):
                module.snapshot_download("unexpected/model")
            raise ValueError("fixture")
    assert module.snapshot_download is forbidden_network


def test_gpu_build_sources_match_runtime_pins():
    from urllib.parse import unquote, urlparse
    for component in ("asr", "tts", "talk"):
        pins = {}
        for line in (ROOT / f"requirements/{component}.txt").read_text().splitlines():
            if line and not line.startswith("#"):
                requirement = Requirement(line)
                pins[requirement.name.replace("_", "-").lower()] = requirement.specifier
        for line in (ROOT / f"requirements/{component}-cuda.txt").read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            requirement = Requirement(line)
            url = urlparse(requirement.url)
            assert url.scheme == "https" and url.fragment.startswith("sha256=")
            assert len(url.fragment.removeprefix("sha256=")) == 64
            distribution, version, _, tags = parse_wheel_filename(unquote(url.path.rsplit("/", 1)[-1]))
            assert version in pins[str(distribution)]
            assert any(tag.interpreter == "cp310" and "x86_64" in tag.platform for tag in tags)
