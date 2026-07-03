from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from medad.agent import build_agent, memory_sources
from medad.config import load_config


class _ToolBindableFakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_subagents_parsed_and_merged_by_name(tmp_path: Path):
    (tmp_path / ".medad").mkdir()
    (tmp_path / ".medad" / "config.toml").write_text(
        """
[[subagents]]
name = "reviewer"
description = "Reviews code"
system_prompt = "You review code."
model = "anthropic:claude-haiku-4-5"
"""
    )
    cfg = load_config(tmp_path)
    assert cfg.subagents == [
        {
            "name": "reviewer",
            "description": "Reviews code",
            "system_prompt": "You review code.",
            "model": "anthropic:claude-haiku-4-5",
        }
    ]


def test_subagent_missing_keys_raises(tmp_path: Path):
    (tmp_path / ".medad").mkdir()
    (tmp_path / ".medad" / "config.toml").write_text(
        """
[[subagents]]
name = "broken"
"""
    )
    with pytest.raises(ValueError, match="missing required keys"):
        load_config(tmp_path)


def test_memory_sources_project_agents_md(tmp_path: Path):
    cfg = load_config(tmp_path)
    assert memory_sources(cfg) == [] or all("AGENTS.md" in s for s in memory_sources(cfg))
    (tmp_path / "AGENTS.md").write_text("# notes\n")
    assert str(tmp_path / "AGENTS.md") in memory_sources(cfg)


def test_agent_builds_with_phase3_features(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# project memory\n")
    skills_dir = tmp_path / ".medad" / "skills" / "demo"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: demo\ndescription: demo skill\n---\nSteps.\n")
    (tmp_path / ".medad" / "config.toml").write_text(
        """
[[subagents]]
name = "reviewer"
description = "Reviews code"
system_prompt = "You review code."
"""
    )
    cfg = load_config(tmp_path)
    model = _ToolBindableFakeModel(messages=iter([AIMessage(content="ready")]))
    agent = build_agent(cfg, checkpointer=None, model=model)
    result = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"][-1].content == "ready"
