# medad — development notes

medad is a Claude-Code-like terminal coding harness built on the `deepagents`
SDK (LangChain Deep Agents) with LangGraph as the runtime.

## Architecture

- `src/medad/agent.py` assembles `create_deep_agent()` with a
  `LocalShellBackend` rooted at the project dir. The SDK contributes the tools
  (`ls`/`read_file`/`write_file`/`edit_file`/`glob`/`grep`/`execute`), the
  `write_todos` planner, subagents (`task`), and context summarization.
- Approvals use `interrupt_on` (LangGraph HITL middleware). The REPL catches
  `__interrupt__` updates, consults `permissions.PermissionEngine`, renders a
  diff/command via `ui/approval.py`, and resumes with
  `Command(resume={interrupt_id: {"decisions": [...]}})`.
- Sessions persist via `SqliteSaver` in `.medad/sessions.db`; `--resume` reuses
  the thread id stored in `.medad/last_session`.
- Config: `~/.medad/config.toml` merged with `<project>/.medad/config.toml`.

## Conventions

- `uv` for everything: `uv run pytest`, `uv run medad`.
- Headless mode (`medad -n "..."` or piped stdin) builds the agent without
  interrupts — documented as unguarded.
- Verify deepagents API shapes against the installed package
  (`.venv/.../deepagents`), not memory — the SDK moves fast.
