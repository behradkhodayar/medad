from pathlib import Path

from medad.config import DEFAULT_MODEL, load_config


def test_defaults(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg.model == DEFAULT_MODEL
    assert cfg.project_dir == tmp_path.resolve()
    assert "git status" in cfg.permissions.allow_commands
    assert cfg.permissions.auto_approve_edits is False


def test_project_config_overrides(tmp_path: Path):
    (tmp_path / ".medad").mkdir()
    (tmp_path / ".medad" / "config.toml").write_text(
        """
model = "anthropic:claude-haiku-4-5"

[permissions]
allow_commands = ["make test"]
auto_approve_edits = true
"""
    )
    cfg = load_config(tmp_path)
    assert cfg.model == "anthropic:claude-haiku-4-5"
    assert cfg.permissions.allow_commands == ["make test"]
    assert cfg.permissions.auto_approve_edits is True


def test_state_dir(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg.state_dir == tmp_path.resolve() / ".medad"


def test_sandbox_defaults(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert cfg.sandbox.backend == "local"
    assert cfg.sandbox.name is None
    assert cfg.mcp_servers == {}


def test_sandbox_and_mcp_config(tmp_path: Path):
    (tmp_path / ".medad").mkdir()
    (tmp_path / ".medad" / "config.toml").write_text(
        """
[sandbox]
backend = "langsmith"
name = "scratch"

[mcp.servers.docs]
transport = "streamable_http"
url = "https://example.com/mcp"
"""
    )
    cfg = load_config(tmp_path)
    assert cfg.sandbox.backend == "langsmith"
    assert cfg.sandbox.name == "scratch"
    assert cfg.mcp_servers == {
        "docs": {"transport": "streamable_http", "url": "https://example.com/mcp"}
    }
