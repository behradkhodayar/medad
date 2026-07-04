"""Agent assembly: wires the deepagents SDK into a medad agent."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from deepagents import create_deep_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from medad.config import Config
from medad.mcp import load_mcp_tools
from medad.permissions import GATED_TOOLS
from medad.sandbox import build_backend
from medad.skills import skill_source_dirs


def load_system_prompt() -> str:
    return (resources.files("medad") / "prompts" / "system.md").read_text()


def memory_sources(cfg: Config) -> list[str]:
    """AGENTS.md files to load as persistent memory, global then project."""
    candidates = [Path.home() / ".medad" / "AGENTS.md", cfg.project_dir / "AGENTS.md"]
    return [str(p) for p in candidates if p.is_file()]


def build_agent(
    cfg: Config,
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    headless: bool = False,
    model: str | None = None,
):
    """Build the deep agent.

    The backend gives the agent filesystem tools rooted at the project dir
    plus shell execution — on the host by default, or in a remote sandbox
    when `[sandbox]` selects one. In interactive mode, `execute`,
    `write_file`, `edit_file`, and every mounted MCP tool pause the graph
    for human approval; headless mode runs unguarded (documented behavior
    of `medad -n`).
    """
    backend = build_backend(cfg)
    mcp_tools = load_mcp_tools(cfg)
    interrupt_on = (
        None
        if headless
        else {
            tool: {"allowed_decisions": ["approve", "reject"]}
            for tool in (*GATED_TOOLS, *(t.name for t in mcp_tools))
        }
    )
    skills = [str(d) for d in skill_source_dirs(cfg)]
    memory = memory_sources(cfg)
    return create_deep_agent(
        model=model or cfg.model,
        system_prompt=load_system_prompt(),
        tools=mcp_tools or None,
        backend=backend,
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
        skills=skills or None,
        memory=memory or None,
        subagents=cfg.subagents or None,
    )
