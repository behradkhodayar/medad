"""Configuration loading for medad.

Two TOML files are merged, project over global:

  ~/.medad/config.toml          (global)
  <project>/.medad/config.toml  (per-project)

Schema::

    model = "anthropic:claude-opus-4-8"

    [permissions]
    allow_commands = ["git status", "git diff", "ls"]
    auto_approve_edits = false

    [[subagents]]
    name = "reviewer"
    description = "Reviews code changes for bugs and style issues"
    system_prompt = "You are a meticulous code reviewer..."
    model = "anthropic:claude-haiku-4-5"   # optional; defaults to the main model
    skills = []                            # optional skill source dirs

Subagent entries from both files are merged by name, project winning.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "anthropic:claude-opus-4-8"

# Read-only commands that are safe to run without asking, used when the user
# has no config of their own yet.
DEFAULT_ALLOW_COMMANDS = [
    "ls",
    "cat",
    "pwd",
    "git status",
    "git diff",
    "git log",
]


@dataclass
class PermissionsConfig:
    allow_commands: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOW_COMMANDS))
    auto_approve_edits: bool = False


# Keys copied from a [[subagents]] entry into the SDK's SubAgent spec.
SUBAGENT_REQUIRED_KEYS = ("name", "description", "system_prompt")
SUBAGENT_OPTIONAL_KEYS = ("model", "skills")


@dataclass
class Config:
    project_dir: Path
    model: str = DEFAULT_MODEL
    permissions: PermissionsConfig = field(default_factory=PermissionsConfig)
    subagents: list[dict[str, Any]] = field(default_factory=list)

    @property
    def state_dir(self) -> Path:
        """Per-project medad state directory (sessions db, last-session marker)."""
        return self.project_dir / ".medad"


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _parse_subagents(entries: Any) -> list[dict[str, Any]]:
    subagents: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        missing = [k for k in SUBAGENT_REQUIRED_KEYS if not entry.get(k)]
        if missing:
            raise ValueError(
                f"subagent entry {entry.get('name', '?')!r} missing required keys: {missing}"
            )
        spec = {k: entry[k] for k in (*SUBAGENT_REQUIRED_KEYS, *SUBAGENT_OPTIONAL_KEYS) if k in entry}
        subagents.append(spec)
    return subagents


def load_config(project_dir: Path | None = None) -> Config:
    project_dir = (project_dir or Path.cwd()).resolve()
    merged: dict[str, Any] = {}
    subagents_by_name: dict[str, dict[str, Any]] = {}
    for path in (Path.home() / ".medad" / "config.toml", project_dir / ".medad" / "config.toml"):
        data = _read_toml(path)
        perms = {**merged.get("permissions", {}), **data.get("permissions", {})}
        for spec in _parse_subagents(data.get("subagents", [])):
            subagents_by_name[spec["name"]] = spec
        merged.update(data)
        merged["permissions"] = perms

    perms_data = merged.get("permissions", {})
    permissions = PermissionsConfig(
        allow_commands=list(perms_data.get("allow_commands", DEFAULT_ALLOW_COMMANDS)),
        auto_approve_edits=bool(perms_data.get("auto_approve_edits", False)),
    )
    return Config(
        project_dir=project_dir,
        model=str(merged.get("model", DEFAULT_MODEL)),
        permissions=permissions,
        subagents=list(subagents_by_name.values()),
    )
