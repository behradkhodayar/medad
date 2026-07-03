"""Permission engine: decides which gated tool calls are auto-approved.

The agent is built with HITL interrupts on `execute`, `write_file`, and
`edit_file`. When an interrupt fires, the REPL consults this engine first;
only calls it does not auto-approve are shown to the user, who can answer
"always" to widen the session scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

GATED_TOOLS = ("execute", "write_file", "edit_file")
EDIT_TOOLS = ("write_file", "edit_file")


def command_matches_prefix(command: str, prefix: str) -> bool:
    """True if `command` starts with `prefix` on a word boundary.

    "git status" matches "git status" and "git status -sb",
    but not "git status-foo".
    """
    command = command.strip()
    prefix = prefix.strip()
    if not prefix or not command.startswith(prefix):
        return False
    rest = command[len(prefix) :]
    return rest == "" or rest[0] in (" ", "\t")


@dataclass
class PermissionEngine:
    allow_commands: list[str] = field(default_factory=list)
    auto_approve_edits: bool = False
    # Session-scoped grants accumulated from "always" answers.
    session_commands: list[str] = field(default_factory=list)
    session_tools: set[str] = field(default_factory=set)

    def is_auto_approved(self, tool_name: str, args: dict[str, Any]) -> bool:
        if tool_name in self.session_tools:
            return True
        if tool_name in EDIT_TOOLS:
            return self.auto_approve_edits
        if tool_name == "execute":
            command = str(args.get("command", ""))
            return any(
                command_matches_prefix(command, p)
                for p in (*self.allow_commands, *self.session_commands)
            )
        return False

    def allow_always(self, tool_name: str, args: dict[str, Any]) -> str:
        """Record an 'always allow' answer for this session. Returns a description."""
        if tool_name == "execute":
            command = str(args.get("command", "")).strip()
            # Grant the first two words as a prefix ("git push", "npm test") so
            # the grant covers variants of the same command, not everything.
            prefix = " ".join(command.split()[:2]) or command
            self.session_commands.append(prefix)
            return f"commands starting with '{prefix}'"
        self.session_tools.add(tool_name)
        return f"all '{tool_name}' calls"
