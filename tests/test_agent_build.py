"""Assemble the real deep agent graph with a fake model — no API calls."""

from pathlib import Path

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from medad.agent import build_agent, load_system_prompt
from medad.config import load_config


class _ToolBindableFakeModel(GenericFakeChatModel):
    """GenericFakeChatModel doesn't implement bind_tools; the graph only needs
    it to not raise, since the scripted replies never call tools."""

    def bind_tools(self, tools, **kwargs):
        return self


def _fake_model(*replies: str) -> GenericFakeChatModel:
    return _ToolBindableFakeModel(messages=iter([AIMessage(content=r) for r in replies]))


def test_system_prompt_loads():
    prompt = load_system_prompt()
    assert "medad" in prompt
    assert "edit_file" in prompt


def test_agent_builds_and_answers(tmp_path: Path):
    cfg = load_config(tmp_path)
    agent = build_agent(cfg, checkpointer=None, model=_fake_model("hello from the agent"))
    result = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"][-1].content == "hello from the agent"


def test_headless_agent_builds(tmp_path: Path):
    cfg = load_config(tmp_path)
    agent = build_agent(cfg, checkpointer=None, headless=True, model=_fake_model("ok"))
    result = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert result["messages"][-1].content == "ok"
