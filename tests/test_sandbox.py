"""Sandbox backend selection."""

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from deepagents.backends import LangSmithSandbox, LocalShellBackend

from medad.config import load_config
from medad.sandbox import DockerSandbox, build_backend


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


class _FakeDockerCli:
    """Stands in for subprocess.run, tracking container lifecycle calls."""

    def __init__(self, running=(), stopped=()):
        self.running = set(running)
        self.stopped = set(stopped)
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        subcommand = argv[1]
        if subcommand == "inspect":
            name = argv[-1]
            if name in self.running:
                return subprocess.CompletedProcess(argv, 0, stdout="true\n", stderr="")
            if name in self.stopped:
                return subprocess.CompletedProcess(argv, 0, stdout="false\n", stderr="")
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="No such object")
        if subcommand == "start":
            self.running.add(argv[-1])
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
        if subcommand == "run":
            self.running.add(argv[argv.index("--name") + 1])
            return subprocess.CompletedProcess(argv, 0, stdout="abc123\n", stderr="")
        raise AssertionError(f"unexpected docker call: {argv}")

    def subcommands(self) -> list[str]:
        return [argv[1] for argv in self.calls]


@pytest.fixture
def fake_docker(monkeypatch):
    def install(**kwargs):
        cli = _FakeDockerCli(**kwargs)
        monkeypatch.setattr("medad.sandbox.subprocess.run", cli)
        return cli

    return install


def test_docker_backend_creates_container_with_project_mount(tmp_path: Path, fake_docker):
    cli = fake_docker()
    cfg = _config_with_sandbox(tmp_path, '[sandbox]\nbackend = "docker"\n')
    backend = build_backend(cfg)
    assert isinstance(backend, DockerSandbox)
    assert backend.id == f"medad-{tmp_path.name}"
    assert cli.subcommands() == ["inspect", "run"]
    run_args = cli.calls[-1]
    project = str(cfg.project_dir)
    assert run_args[run_args.index("-w") + 1] == project
    assert run_args[run_args.index("-v") + 1] == f"{project}:{project}"
    assert run_args[-3:] == ["python:3.12-slim", "sleep", "infinity"]


def test_docker_backend_isolated_mode_uses_workspace(tmp_path: Path, fake_docker):
    cli = fake_docker()
    cfg = _config_with_sandbox(
        tmp_path, '[sandbox]\nbackend = "docker"\nimage = "alpine:3"\nmount_project = false\n'
    )
    build_backend(cfg)
    run_args = cli.calls[-1]
    assert run_args[run_args.index("-w") + 1] == "/workspace"
    assert "-v" not in run_args
    assert run_args[-3:] == ["alpine:3", "sleep", "infinity"]


def test_docker_backend_reuses_running_container(tmp_path: Path, fake_docker):
    cli = fake_docker(running=[f"medad-{tmp_path.name}"])
    cfg = _config_with_sandbox(tmp_path, '[sandbox]\nbackend = "docker"\n')
    build_backend(cfg)
    assert cli.subcommands() == ["inspect"]


def test_docker_backend_starts_stopped_container(tmp_path: Path, fake_docker):
    cli = fake_docker(stopped=["my-box"])
    cfg = _config_with_sandbox(tmp_path, '[sandbox]\nbackend = "docker"\nname = "my-box"\n')
    backend = build_backend(cfg)
    assert backend.id == "my-box"
    assert cli.subcommands() == ["inspect", "start"]


def test_docker_backend_surfaces_create_failure(tmp_path: Path, monkeypatch):
    def failing_run(argv, **kwargs):
        if argv[1] == "inspect":
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="No such object")
        return subprocess.CompletedProcess(argv, 125, stdout="", stderr="pull access denied")

    monkeypatch.setattr("medad.sandbox.subprocess.run", failing_run)
    cfg = _config_with_sandbox(tmp_path, '[sandbox]\nbackend = "docker"\n')
    with pytest.raises(RuntimeError, match="pull access denied"):
        build_backend(cfg)


# Small images with a POSIX sh, in preference order. The live test only
# exercises the four sandbox primitives (not the python3-derived file tools),
# so images without python3 are fine; the first one already present locally
# is used so the test also runs without registry access.
_LIVE_IMAGES = ("alpine:3", "busybox:latest", "node:22-alpine", "python:3.12-slim")


def _live_image() -> str | None:
    if shutil.which("docker") is None:
        return None
    try:
        if subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode != 0:
            return None
        for image in _LIVE_IMAGES:
            probe = subprocess.run(
                ["docker", "image", "inspect", image], capture_output=True, timeout=10
            )
            if probe.returncode == 0:
                return image
        pulled = subprocess.run(
            ["docker", "pull", _LIVE_IMAGES[0]], capture_output=True, timeout=120
        )
        return _LIVE_IMAGES[0] if pulled.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


_LIVE_IMAGE = _live_image()


@pytest.mark.skipif(_LIVE_IMAGE is None, reason="docker or a test image not available")
def test_docker_sandbox_live_roundtrip(tmp_path: Path):
    """End-to-end against a real container: execute, upload, download."""
    name = f"medad-test-{uuid.uuid4().hex[:8]}"
    cfg = _config_with_sandbox(
        tmp_path,
        f'[sandbox]\nbackend = "docker"\nname = "{name}"\n'
        f'image = "{_LIVE_IMAGE}"\nmount_project = false\n',
    )
    try:
        backend = build_backend(cfg)
        result = backend.execute("echo hello && pwd")
        assert result.exit_code == 0
        assert "hello" in result.output
        assert "/workspace" in result.output

        [up] = backend.upload_files([("/workspace/sub/a.txt", b"payload")])
        assert up.error is None
        [down] = backend.download_files(["/workspace/sub/a.txt"])
        assert down.content == b"payload"
        [missing] = backend.download_files(["/workspace/nope.txt"])
        assert missing.error == "file_not_found"

        failed = backend.execute("exit 3")
        assert failed.exit_code == 3
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
