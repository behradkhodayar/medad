from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from medad.agent import build_agent
from medad.commands import CommandResult, dispatch
from medad.config import load_config
from medad.permissions import PermissionEngine
from medad.session import new_thread_id, open_checkpointer
from medad.ui.repl import ReplContext, _compact, run_turn


class _ToolBindableFakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def _ctx(tmp_path: Path, *replies: str) -> ReplContext:
    cfg = load_config(tmp_path)
    checkpointer = open_checkpointer(cfg.state_dir)
    model = _ToolBindableFakeModel(messages=iter([AIMessage(content=r) for r in replies]))
    agent = build_agent(cfg, checkpointer, model=model)
    return ReplContext(cfg, agent, PermissionEngine(), checkpointer, new_thread_id())


def test_skill_dispatch_expands_to_message(tmp_path: Path):
    skill_dir = tmp_path / ".medad" / "skills" / "commit-msg"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: commit-msg\ndescription: d\n---\nSteps.\n")
    ctx = _ctx(tmp_path)
    result = dispatch(ctx, "/skill:commit-msg summarize the diff")
    assert isinstance(result, str)
    assert "commit-msg" in result and "SKILL.md" in str(result)
    assert "summarize the diff" in result
    assert dispatch(ctx, "/skill:nope") is CommandResult.OK


def test_compact_reseeds_fresh_thread(tmp_path: Path):
    ctx = _ctx(tmp_path, "first answer", "the dense summary")
    run_turn(ctx, {"messages": [{"role": "user", "content": "do something"}]})
    old_thread = ctx.thread_id

    assert dispatch(ctx, "/compact") is CommandResult.COMPACT
    _compact(ctx)

    assert ctx.thread_id != old_thread
    state = ctx.agent.get_state(ctx.graph_config)
    messages = state.values["messages"]
    assert len(messages) == 1
    assert "the dense summary" in messages[0].content


def test_compact_on_empty_session_is_noop(tmp_path: Path):
    ctx = _ctx(tmp_path)
    thread = ctx.thread_id
    _compact(ctx)
    assert ctx.thread_id == thread
