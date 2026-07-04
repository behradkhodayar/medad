"""Sandbox backend selection: local shell (default), a local Docker container,
or a remote LangSmith sandbox.

    [sandbox]
    backend = "docker"           # "local" (default), "docker", or "langsmith"
    name = "my-sandbox"          # optional; named sandboxes are reused across runs
    image = "python:3.12-slim"   # docker only
    mount_project = true         # docker only: bind-mount the project dir

A sandbox makes headless mode (`medad -n`) safe to run unguarded: `execute`
and file tools act inside the sandbox, not on the host.

docker needs no account — commands run in a local container (reused across
runs, `docker rm` it to reset). With `mount_project` (the default) the project
dir is bind-mounted at its host path, so edits land in your working tree while
the rest of the host stays out of reach; without it the container filesystem
is fully isolated. The image needs python3 on PATH: BaseSandbox derives the
file tools from `execute` via python3 snippets. The langsmith backend is a
remote VM and needs LANGSMITH_API_KEY in the environment.
"""

from __future__ import annotations

import re
import shlex
import subprocess

from deepagents.backends import LangSmithSandbox, LocalShellBackend
from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import MAX_OUTPUT_BYTES, TRUNCATION_MSG, BaseSandbox

from medad.config import Config

SANDBOX_BACKENDS = ("local", "docker", "langsmith")

_DEFAULT_TIMEOUT = 30 * 60


class DockerSandbox(BaseSandbox):
    """Runs the sandbox protocol against a long-lived local Docker container."""

    def __init__(self, container: str, workdir: str) -> None:
        self._container = container
        self._workdir = workdir

    @property
    def id(self) -> str:
        return self._container

    def _exec(
        self, argv: list[str], *, input_bytes: bytes | None = None, timeout: int | None = None
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["docker", "exec", "-i", "-w", self._workdir, self._container, *argv],
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
        )

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        effective_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT
        try:
            proc = self._exec(
                ["sh", "-lc", command], timeout=effective_timeout or None
            )
        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Command timed out after {effective_timeout} seconds",
                exit_code=124,
                truncated=False,
            )
        output = proc.stdout.decode(errors="replace")
        stderr = proc.stderr.decode(errors="replace")
        if stderr:
            output = f"{output}\n{stderr}" if output else stderr
        truncated = len(output) > MAX_OUTPUT_BYTES
        if truncated:
            output = output[:MAX_OUTPUT_BYTES] + TRUNCATION_MSG
        return ExecuteResponse(output=output, exit_code=proc.returncode, truncated=truncated)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for path, content in files:
            quoted = shlex.quote(path)
            try:
                proc = self._exec(
                    ["sh", "-c", f"mkdir -p $(dirname {quoted}) && cat > {quoted}"],
                    input_bytes=content,
                    timeout=60,
                )
                error = proc.stderr.decode(errors="replace").strip() or None
                responses.append(
                    FileUploadResponse(path=path, error=None if proc.returncode == 0 else error)
                )
            except (OSError, subprocess.SubprocessError) as exc:
                responses.append(FileUploadResponse(path=path, error=str(exc)))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                proc = self._exec(["sh", "-c", f"cat {shlex.quote(path)}"], timeout=60)
            except (OSError, subprocess.SubprocessError) as exc:
                responses.append(FileDownloadResponse(path=path, content=None, error=str(exc)))
                continue
            if proc.returncode == 0:
                responses.append(FileDownloadResponse(path=path, content=proc.stdout, error=None))
            else:
                stderr = proc.stderr.decode(errors="replace")
                error = "file_not_found" if "No such file" in stderr else stderr.strip()
                responses.append(FileDownloadResponse(path=path, content=None, error=error))
        return responses


def build_backend(cfg: Config):
    if cfg.sandbox.backend == "local":
        # virtual_mode=False: real host paths, no path virtualization — medad is
        # a local dev CLI and the approval gates are the safety layer.
        return LocalShellBackend(root_dir=cfg.project_dir, virtual_mode=False, inherit_env=True)
    if cfg.sandbox.backend == "docker":
        return _docker_backend(cfg)
    if cfg.sandbox.backend == "langsmith":
        return _langsmith_backend(cfg)
    raise ValueError(
        f"unknown sandbox backend {cfg.sandbox.backend!r} (expected one of {SANDBOX_BACKENDS})"
    )


def _default_name(cfg: Config) -> str:
    # Docker container names must match [a-zA-Z0-9][a-zA-Z0-9_.-]*.
    return "medad-" + re.sub(r"[^a-zA-Z0-9_.-]", "-", cfg.project_dir.name)


def _docker_backend(cfg: Config) -> DockerSandbox:
    name = cfg.sandbox.name or _default_name(cfg)
    workdir = str(cfg.project_dir) if cfg.sandbox.mount_project else "/workspace"
    _ensure_container(cfg, name, workdir)
    return DockerSandbox(name, workdir)


def _ensure_container(cfg: Config, name: str, workdir: str) -> None:
    """Get-or-create the named container; start it if it is stopped."""
    inspect = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
    )
    if inspect.returncode == 0:
        if inspect.stdout.strip() != "true":
            started = subprocess.run(["docker", "start", name], capture_output=True, text=True)
            if started.returncode != 0:
                raise RuntimeError(f"failed to start sandbox container {name!r}: {started.stderr.strip()}")
        return
    args = ["docker", "run", "-d", "--name", name, "-w", workdir]
    if cfg.sandbox.mount_project:
        project = str(cfg.project_dir)
        args += ["-v", f"{project}:{project}"]
    args += [cfg.sandbox.image, "sleep", "infinity"]
    created = subprocess.run(args, capture_output=True, text=True)
    if created.returncode != 0:
        raise RuntimeError(
            f"failed to create sandbox container {name!r} from image "
            f"{cfg.sandbox.image!r}: {created.stderr.strip()}"
        )


def _langsmith_backend(cfg: Config) -> LangSmithSandbox:
    from langsmith.sandbox import ResourceNotFoundError, SandboxClient

    client = SandboxClient()
    name = cfg.sandbox.name or _default_name(cfg)
    try:
        sandbox = client.get_sandbox(name)
    except ResourceNotFoundError:
        sandbox = client.create_sandbox(name=name)
    return LangSmithSandbox(sandbox)
