"""Sandbox backend selection: local shell (default) or a remote LangSmith sandbox.

    [sandbox]
    backend = "langsmith"     # default: "local"
    name = "my-sandbox"       # optional; a named sandbox is reused across runs

A remote sandbox makes headless mode (`medad -n`) safe to run unguarded:
`execute` and file tools act inside the sandbox VM, not on the host.
The langsmith backend needs LANGSMITH_API_KEY in the environment.
"""

from __future__ import annotations

from deepagents.backends import LangSmithSandbox, LocalShellBackend

from medad.config import Config

SANDBOX_BACKENDS = ("local", "langsmith")


def build_backend(cfg: Config):
    if cfg.sandbox.backend == "local":
        # virtual_mode=False: real host paths, no path virtualization — medad is
        # a local dev CLI and the approval gates are the safety layer.
        return LocalShellBackend(root_dir=cfg.project_dir, virtual_mode=False, inherit_env=True)
    if cfg.sandbox.backend == "langsmith":
        return _langsmith_backend(cfg)
    raise ValueError(
        f"unknown sandbox backend {cfg.sandbox.backend!r} (expected one of {SANDBOX_BACKENDS})"
    )


def _langsmith_backend(cfg: Config) -> LangSmithSandbox:
    from langsmith.sandbox import ResourceNotFoundError, SandboxClient

    client = SandboxClient()
    name = cfg.sandbox.name or f"medad-{cfg.project_dir.name}"
    try:
        sandbox = client.get_sandbox(name)
    except ResourceNotFoundError:
        sandbox = client.create_sandbox(name=name)
    return LangSmithSandbox(sandbox)
