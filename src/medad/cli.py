"""medad CLI entrypoint."""

from __future__ import annotations

import sys
from typing import Optional

import typer

from medad import __version__
from medad.agent import build_agent
from medad.config import load_config
from medad.permissions import PermissionEngine
from medad.session import (
    load_last_thread_id,
    new_thread_id,
    open_checkpointer,
    save_last_thread_id,
)
from medad.ui import render
from medad.ui.repl import ReplContext, run_repl, run_turn

app = typer.Typer(add_completion=False, rich_markup_mode="rich")


@app.command(help="medad — a terminal coding agent built on LangChain Deep Agents.")
def main(
    prompt: Optional[str] = typer.Argument(
        None, help="One-shot prompt; runs headless and exits. Omit for interactive mode."
    ),
    headless: bool = typer.Option(
        False, "--headless", "-n", help="Non-interactive mode (no approval gates)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model as provider:name, e.g. anthropic:claude-opus-4-8"
    ),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume the last session."),
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    if version:
        render.console.print(f"medad {__version__}")
        raise typer.Exit()

    cfg = load_config()
    if model:
        cfg.model = model

    # Piped stdin becomes the prompt (echo "fix the bug" | medad).
    if prompt is None and not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            prompt = piped

    headless = headless or prompt is not None
    if headless and not prompt:
        render.print_error("headless mode (-n) requires a prompt argument or piped stdin")
        raise typer.Exit(code=1)

    checkpointer = open_checkpointer(cfg.state_dir)
    thread_id = (load_last_thread_id(cfg.state_dir) if resume else None) or new_thread_id()
    if resume and thread_id:
        render.print_note(f"resuming session {thread_id[:8]}")

    engine = PermissionEngine(
        allow_commands=cfg.permissions.allow_commands,
        auto_approve_edits=cfg.permissions.auto_approve_edits,
    )
    agent = build_agent(cfg, checkpointer, headless=headless)
    ctx = ReplContext(cfg, agent, engine, checkpointer, thread_id)

    if headless:
        save_last_thread_id(cfg.state_dir, thread_id)
        run_turn(ctx, {"messages": [{"role": "user", "content": prompt}]})
        return

    run_repl(ctx)


if __name__ == "__main__":
    app()
