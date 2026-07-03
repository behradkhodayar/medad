"""Human-in-the-loop approval: render the pending action, ask, decide.

Consumes the HITL interrupt payload produced by LangChain's
HumanInTheLoopMiddleware ({"action_requests": [...], ...}) and returns the
matching {"decisions": [...]} resume payload.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.syntax import Syntax

from medad.permissions import PermissionEngine

console = Console(highlight=False)


def _render_diff(path_str: str, old: str, new: str) -> None:
    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path_str}",
            tofile=f"b/{path_str}",
        )
    )
    if diff:
        console.print(Syntax(diff, "diff", background_color="default"))
    else:
        console.print("[dim](no content change)[/dim]")


def _existing_content(project_dir: Path, path_str: str) -> str:
    path = Path(path_str)
    if not path.is_absolute():
        path = project_dir / path
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return ""


def render_action(project_dir: Path, name: str, args: dict[str, Any]) -> None:
    console.print(f"\n[bold yellow]⏸ approval needed:[/bold yellow] [bold]{name}[/bold]")
    if name == "execute":
        console.print(f"  [bold]$ {args.get('command', '')}[/bold]")
    elif name == "write_file":
        path_str = str(args.get("file_path", ""))
        _render_diff(path_str, _existing_content(project_dir, path_str), str(args.get("content", "")))
    elif name == "edit_file":
        path_str = str(args.get("file_path", ""))
        old = _existing_content(project_dir, path_str)
        new = old.replace(
            str(args.get("old_string", "")),
            str(args.get("new_string", "")),
            -1 if args.get("replace_all") else 1,
        )
        _render_diff(path_str, old, new)
    else:
        console.print(f"  args: {args}")


def _ask() -> str:
    while True:
        answer = console.input(
            "[bold]approve?[/bold] [green]y[/green]es / [red]n[/red]o / [cyan]a[/cyan]lways: "
        ).strip().lower()
        if answer in ("y", "yes", "n", "no", "a", "always"):
            return answer[0]


def resolve_action_requests(
    action_requests: list[dict[str, Any]],
    engine: PermissionEngine,
    project_dir: Path,
) -> list[dict[str, Any]]:
    """Return one decision per action request, prompting only when needed."""
    decisions: list[dict[str, Any]] = []
    for request in action_requests:
        name = request.get("name", "")
        args = request.get("args", {}) or {}
        if engine.is_auto_approved(name, args):
            console.print(f"[dim]✓ auto-approved {name}[/dim]")
            decisions.append({"type": "approve"})
            continue
        render_action(project_dir, name, args)
        answer = _ask()
        if answer == "a":
            granted = engine.allow_always(name, args)
            console.print(f"[dim]will auto-approve {granted} for this session[/dim]")
            decisions.append({"type": "approve"})
        elif answer == "y":
            decisions.append({"type": "approve"})
        else:
            reason = console.input("[dim]reason (optional): [/dim]").strip()
            decision: dict[str, Any] = {"type": "reject"}
            if reason:
                decision["message"] = reason
            decisions.append(decision)
    return decisions
