from pathlib import Path

from medad.config import load_config
from medad.skills import discover_skills, find_skill, skill_source_dirs


def _make_skill(root: Path, name: str, description: str = "does things") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\nInstructions.\n")
    return skill_md


def test_discovers_project_skills(tmp_path: Path):
    _make_skill(tmp_path / ".medad" / "skills", "web-research", "researches the web")
    cfg = load_config(tmp_path)
    skills = discover_skills(cfg)
    assert [s.name for s in skills] == ["web-research"]
    assert skills[0].description == "researches the web"
    assert skills[0].path.name == "SKILL.md"


def test_find_skill_and_missing(tmp_path: Path):
    _make_skill(tmp_path / ".medad" / "skills", "commit-msg")
    cfg = load_config(tmp_path)
    assert find_skill(cfg, "commit-msg") is not None
    assert find_skill(cfg, "nope") is None


def test_frontmatter_fallback_to_dirname(tmp_path: Path):
    skill_dir = tmp_path / ".medad" / "skills" / "bare"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("no frontmatter here\n")
    cfg = load_config(tmp_path)
    skills = discover_skills(cfg)
    assert skills[0].name == "bare"
    assert skills[0].description == ""


def test_no_sources(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert skill_source_dirs(cfg) == [] or all(
        d != tmp_path / ".medad" / "skills" for d in skill_source_dirs(cfg)
    )
    assert all(s.path.is_file() for s in discover_skills(cfg))
