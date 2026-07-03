"""Agent assembly: wires the deepagents SDK into a medad agent."""

from __future__ import annotations

from importlib import resources

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver

from medad.config import Config
from medad.permissions import GATED_TOOLS


def load_system_prompt() -> str:
    return (resources.files("medad") / "prompts" / "system.md").read_text()


def build_agent(
    cfg: Config,
    checkpointer: BaseCheckpointSaver | None = None,
    *,
    headless: bool = False,
    model: str | None = None,
):
    """Build the deep agent.

    The backend gives the agent filesystem tools rooted at the project dir
    plus local shell execution. In interactive mode, `execute`, `write_file`,
    and `edit_file` pause the graph for human approval; headless mode runs
    unguarded (documented behavior of `medad -n`).
    """
    # virtual_mode=False: real host paths, no path virtualization — medad is a
    # local dev CLI and the approval gates are the safety layer.
    backend = LocalShellBackend(root_dir=cfg.project_dir, virtual_mode=False, inherit_env=True)
    interrupt_on = (
        None
        if headless
        else {tool: {"allowed_decisions": ["approve", "reject"]} for tool in GATED_TOOLS}
    )
    return create_deep_agent(
        model=model or cfg.model,
        system_prompt=load_system_prompt(),
        backend=backend,
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
    )
