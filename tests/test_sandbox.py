"""Sandbox backend selection."""

from pathlib import Path

import pytest
from deepagents.backends import LangSmithSandbox, LocalShellBackend

from medad.config import load_config
from medad.sandbox import build_backend


def _config_with_sandbox(tmp_path: Path, body: str):
    (tmp_path / ".medad").mkdir(exist_ok=True)
    (tmp_path / ".medad" / "config.toml").write_text(body)
    return load_config(tmp_path)


def test_default_backend_is_local_shell(tmp_path: Path):
    backend = build_backend(load_config(tmp_path))
    assert isinstance(backend, LocalShellBackend)


def test_unknown_backend_rejected(tmp_path: Path):
    cfg = _config_with_sandbox(tmp_path, '[sandbox]\nbackend = "e2b"\n')
    with pytest.raises(ValueError, match="unknown sandbox backend 'e2b'"):
        build_backend(cfg)


class _FakeSandbox:
    def __init__(self, name: str):
        self.name = name


class _FakeClient:
    existing = ["already-there"]
    created: list[str] = []

    def __init__(self, **kwargs):
        pass

    def get_sandbox(self, name: str, **kwargs):
        from langsmith.sandbox import ResourceNotFoundError

        if name in self.existing:
            return _FakeSandbox(name)
        raise ResourceNotFoundError(f"no sandbox {name}")

    def create_sandbox(self, name=None, **kwargs):
        _FakeClient.created.append(name)
        return _FakeSandbox(name)


@pytest.fixture
def fake_client(monkeypatch):
    _FakeClient.created = []
    monkeypatch.setattr("langsmith.sandbox.SandboxClient", _FakeClient)
    return _FakeClient


def test_langsmith_backend_reuses_named_sandbox(tmp_path: Path, fake_client):
    cfg = _config_with_sandbox(
        tmp_path, '[sandbox]\nbackend = "langsmith"\nname = "already-there"\n'
    )
    backend = build_backend(cfg)
    assert isinstance(backend, LangSmithSandbox)
    assert backend.id == "already-there"
    assert fake_client.created == []


def test_langsmith_backend_creates_default_named_sandbox(tmp_path: Path, fake_client):
    cfg = _config_with_sandbox(tmp_path, '[sandbox]\nbackend = "langsmith"\n')
    backend = build_backend(cfg)
    assert isinstance(backend, LangSmithSandbox)
    assert fake_client.created == [f"medad-{tmp_path.name}"]
