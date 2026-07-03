"""Terminal rendering helpers (rich)."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console(highlight=False)


def message_text(content: Any) -> str:
    """Extract plain text from a LangChain message content payload."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in ("text", "text_delta"):
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


def print_banner(model: str, project_dir: str, thread_id: str) -> None:
    console.print(f"[bold]medad[/bold] · [cyan]{model}[/cyan] · {project_dir}")
    console.print(f"[dim]session {thread_id[:8]} · /help for commands · ctrl-d to quit[/dim]\n")


def stream_text(text: str) -> None:
    if text:
        console.print(text, end="", soft_wrap=True)


def _short_args(args: dict[str, Any], limit: int = 100) -> str:
    try:
        rendered = json.dumps(args, ensure_ascii=False)
    except (TypeError, ValueError):
        rendered = str(args)
    return rendered if len(rendered) <= limit else rendered[: limit - 1] + "…"


def print_tool_call(name: str, args: dict[str, Any]) -> None:
    console.print(f"\n[yellow]→ {name}[/yellow] [dim]{_short_args(args)}[/dim]")


def print_tool_result(name: str, status: str | None = None) -> None:
    mark = "[red]✗[/red]" if status == "error" else "[green]✓[/green]"
    console.print(f"{mark} [dim]{name}[/dim]")


def print_note(text: str) -> None:
    console.print(f"[dim]{text}[/dim]")


def print_error(text: str) -> None:
    console.print(f"[bold red]error:[/bold red] {text}")


def print_todos(todos: list[dict[str, Any]]) -> None:
    if not todos:
        console.print("[dim]no todos[/dim]")
        return
    table = Table(show_header=False, box=None, pad_edge=False)
    marks = {"completed": "[green]✔[/green]", "in_progress": "[yellow]▸[/yellow]"}
    for todo in todos:
        status = todo.get("status", "pending")
        table.add_row(marks.get(status, "[dim]○[/dim]"), todo.get("content", ""))
    console.print(table)
