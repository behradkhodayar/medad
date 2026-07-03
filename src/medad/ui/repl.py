"""The interactive REPL: streams agent turns, handles interrupts and slash commands."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.types import Command
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from medad.commands import CommandResult, dispatch
from medad.session import new_thread_id, save_last_thread_id
from medad.ui import approval, render

COMPACT_PROMPT = (
    "Write a dense handoff summary of this session for a fresh assistant: the "
    "goal, key decisions, files touched, current state, and open next steps. "
    "Output only the summary."
)


class ReplContext:
    """Mutable state shared between the loop and slash commands."""

    def __init__(self, cfg, agent, engine, checkpointer, thread_id: str):
        self.cfg = cfg
        self.agent = agent
        self.engine = engine
        self.checkpointer = checkpointer
        self.thread_id = thread_id

    @property
    def graph_config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}, "recursion_limit": 200}


def _emit_update(update: Any, printed_tool_call_ids: set[str]) -> None:
    """Print compact tool activity from an `updates` stream entry."""
    if not isinstance(update, dict):
        return
    for message in update.get("messages", []) or []:
        if isinstance(message, AIMessage) and not isinstance(message, AIMessageChunk):
            for call in message.tool_calls or []:
                call_id = call.get("id") or ""
                if call_id not in printed_tool_call_ids:
                    printed_tool_call_ids.add(call_id)
                    render.print_tool_call(call.get("name", "?"), call.get("args", {}))
        elif isinstance(message, ToolMessage):
            render.print_tool_result(message.name or "tool", message.status)


def run_turn(ctx: ReplContext, payload: Any) -> None:
    """Run one agent turn, resuming through approval interrupts until done."""
    while True:
        interrupts: list[Any] = []
        printed: set[str] = set()
        streamed_any_text = False
        for mode, data in ctx.agent.stream(
            payload, config=ctx.graph_config, stream_mode=["updates", "messages"]
        ):
            if mode == "messages":
                chunk, _meta = data
                if isinstance(chunk, AIMessageChunk):
                    text = render.message_text(chunk.content)
                    if text:
                        render.stream_text(text)
                        streamed_any_text = True
            else:  # updates
                for node, update in data.items():
                    if node == "__interrupt__":
                        interrupts.extend(update)
                    else:
                        _emit_update(update, printed)
        if streamed_any_text:
            render.console.print()
        if not interrupts:
            return
        resume: dict[str, Any] = {}
        for interrupt in interrupts:
            value = interrupt.value if not isinstance(interrupt, dict) else interrupt
            requests = (value or {}).get("action_requests", [])
            decisions = approval.resolve_action_requests(
                requests, ctx.engine, ctx.cfg.project_dir
            )
            resume[interrupt.id] = {"decisions": decisions}
        payload = Command(resume=resume)


def _compact(ctx: ReplContext) -> None:
    """Summarize the conversation, then continue in a fresh thread seeded
    with the summary — the manual counterpart to the SDK's auto-summarization."""
    state = ctx.agent.get_state(ctx.graph_config)
    messages = state.values.get("messages", []) if state and state.values else []
    if len(messages) < 2:
        render.print_note("nothing to compact yet")
        return
    run_turn(ctx, {"messages": [{"role": "user", "content": COMPACT_PROMPT}]})
    state = ctx.agent.get_state(ctx.graph_config)
    summary = render.message_text(state.values["messages"][-1].content)
    if not summary.strip():
        render.print_error("compaction failed: empty summary; staying on the current session")
        return
    ctx.thread_id = new_thread_id()
    save_last_thread_id(ctx.cfg.state_dir, ctx.thread_id)
    ctx.agent.update_state(
        ctx.graph_config,
        {"messages": [HumanMessage(f"[compacted context from the previous session]\n{summary}")]},
        as_node="__start__",
    )
    render.print_note(f"compacted into new session {ctx.thread_id[:8]}")


def run_repl(ctx: ReplContext) -> None:
    render.print_banner(ctx.cfg.model, str(ctx.cfg.project_dir), ctx.thread_id)
    save_last_thread_id(ctx.cfg.state_dir, ctx.thread_id)
    history = FileHistory(str(ctx.cfg.state_dir / "history"))
    prompt_session: PromptSession = PromptSession("medad> ", history=history)
    while True:
        try:
            line = prompt_session.prompt()
        except (EOFError, KeyboardInterrupt):
            render.print_note("bye")
            return
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            result = dispatch(ctx, line)
            if result is CommandResult.QUIT:
                return
            if result is CommandResult.COMPACT:
                _compact(ctx)
                continue
            if not isinstance(result, str):
                continue
            line = result  # e.g. /skill:<name> expands to a user message
        try:
            run_turn(ctx, {"messages": [{"role": "user", "content": line}]})
        except KeyboardInterrupt:
            render.print_note("\ninterrupted — state saved; continue with a new message")
        except Exception as exc:  # surface, keep the session alive
            render.print_error(str(exc))
