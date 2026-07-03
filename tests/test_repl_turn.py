"""Drive run_turn's streaming loop against the real graph with a fake model."""

from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from medad.agent import build_agent
from medad.config import load_config
from medad.permissions import PermissionEngine
from medad.session import new_thread_id, open_checkpointer
from medad.ui.repl import ReplContext, run_turn


class _ToolBindableFakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_run_turn_streams_and_persists(tmp_path: Path, capsys):
    cfg = load_config(tmp_path)
    checkpointer = open_checkpointer(cfg.state_dir)
    model = _ToolBindableFakeModel(messages=iter([AIMessage(content="streamed reply")]))
    agent = build_agent(cfg, checkpointer, model=model)
    ctx = ReplContext(cfg, agent, PermissionEngine(), checkpointer, new_thread_id())

    run_turn(ctx, {"messages": [{"role": "user", "content": "hi"}]})

    assert "streamed reply" in capsys.readouterr().out
    state = agent.get_state(ctx.graph_config)
    assert state.values["messages"][-1].content == "streamed reply"
