"""Skill discovery: skills live in <source>/<name>/SKILL.md.

Sources (later overrides earlier, matching SkillsMiddleware semantics):

  ~/.medad/skills/           (global)
  <project>/.medad/skills/   (per-project)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from medad.config import Config


@dataclass
class Skill:
    name: str
    description: str
    path: Path  # the SKILL.md file


def skill_source_dirs(cfg: Config) -> list[Path]:
    candidates = [Path.home() / ".medad" / "skills", cfg.project_dir / ".medad" / "skills"]
    return [d for d in candidates if d.is_dir()]


def _parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
        data = yaml.safe_load("\n".join(lines[1:end]))
        return data if isinstance(data, dict) else {}
    except (StopIteration, yaml.YAMLError):
        return {}


def discover_skills(cfg: Config) -> list[Skill]:
    """Skills from all sources, later sources overriding earlier by name."""
    found: dict[str, Skill] = {}
    for source in skill_source_dirs(cfg):
        for skill_md in sorted(source.glob("*/SKILL.md")):
            meta = _parse_frontmatter(skill_md.read_text(errors="replace"))
            name = str(meta.get("name") or skill_md.parent.name)
            found[name] = Skill(
                name=name,
                description=str(meta.get("description", "")),
                path=skill_md,
            )
    return list(found.values())


def find_skill(cfg: Config, name: str) -> Skill | None:
    return next((s for s in discover_skills(cfg) if s.name == name), None)
