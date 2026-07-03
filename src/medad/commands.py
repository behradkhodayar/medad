"""Slash-command registry for the REPL."""

from __future__ import annotations

import enum

from medad import agent as agent_mod
from medad import skills as skills_mod
from medad.session import new_thread_id, save_last_thread_id
from medad.ui import render


class CommandResult(enum.Enum):
    OK = "ok"
    QUIT = "quit"
    COMPACT = "compact"  # handled by the REPL: summarize, then reseed a fresh thread


HELP = """\
/help              show this help
/model [name]      show or switch the model (provider:model), e.g. /model anthropic:claude-opus-4-8
/clear             start a fresh session (new thread)
/compact           summarize the conversation and continue in a fresh, smaller thread
/todos             show the agent's current todo list
/skills            list available skills (~/.medad/skills and .medad/skills)
/skill:<name> ...  run a skill explicitly, with optional arguments
/allow [prefix]    list allowed command prefixes, or add one for this session
/quit              exit
"""


def dispatch(ctx, line: str) -> CommandResult | str:
    """Handle a slash command. A returned string is a user message the REPL
    should run as a normal agent turn (used by /skill:<name>)."""
    parts = line[1:].split(None, 1)
    name = parts[0].lower() if parts else ""
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name.startswith("skill:"):
        return _invoke_skill(ctx, name[len("skill:") :], arg)

    if name in ("quit", "exit", "q"):
        return CommandResult.QUIT
    if name == "help":
        render.console.print(HELP)
    elif name == "model":
        if arg:
            ctx.cfg.model = arg
            ctx.agent = agent_mod.build_agent(ctx.cfg, ctx.checkpointer)
            render.print_note(f"model switched to {arg} (same session)")
        else:
            render.print_note(f"model: {ctx.cfg.model}")
    elif name == "clear":
        ctx.thread_id = new_thread_id()
        save_last_thread_id(ctx.cfg.state_dir, ctx.thread_id)
        render.print_note(f"new session {ctx.thread_id[:8]}")
    elif name == "compact":
        return CommandResult.COMPACT
    elif name == "todos":
        state = ctx.agent.get_state(ctx.graph_config)
        render.print_todos(state.values.get("todos", []) if state and state.values else [])
    elif name == "skills":
        _list_skills(ctx)
    elif name == "allow":
        if arg:
            ctx.engine.session_commands.append(arg)
            render.print_note(f"allowed for this session: {arg}")
        else:
            prefixes = [*ctx.engine.allow_commands, *ctx.engine.session_commands]
            render.print_note("allowed command prefixes: " + (", ".join(prefixes) or "(none)"))
    else:
        render.print_error(f"unknown command: /{name} (try /help)")
    return CommandResult.OK


def _list_skills(ctx) -> None:
    skills = skills_mod.discover_skills(ctx.cfg)
    if not skills:
        render.print_note(
            "no skills found (add dirs with SKILL.md under ~/.medad/skills or .medad/skills)"
        )
        return
    for skill in skills:
        render.console.print(f"[bold]{skill.name}[/bold]  [dim]{skill.description}[/dim]")


def _invoke_skill(ctx, skill_name: str, arg: str) -> CommandResult | str:
    skill = skills_mod.find_skill(ctx.cfg, skill_name)
    if skill is None:
        render.print_error(f"unknown skill: {skill_name} (see /skills)")
        return CommandResult.OK
    message = (
        f"Use the '{skill.name}' skill for this task: read {skill.path} in full "
        f"(pass limit=1000) and follow its instructions exactly."
    )
    if arg:
        message += f"\n\nTask: {arg}"
    return message
