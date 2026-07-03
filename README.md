# medad

A Claude-Code-like terminal coding agent built on
[LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)
(the same SDK powering LangChain's `dcode`), with LangGraph as the runtime.

## Features (MVP)

- Interactive REPL with streaming responses and compact tool-activity lines
- Filesystem + shell tools rooted at your project (`ls`, `read_file`,
  `write_file`, `edit_file`, `glob`, `grep`, `execute`) via the deepagents SDK
- **Approval gates**: file writes/edits show a unified diff, shell commands
  show the command line — approve / reject / always-allow
- Permission allowlists (`~/.medad/config.toml` + per-project
  `.medad/config.toml`)
- Persistent sessions (SQLite checkpointer) with `--resume`
- Todo planning (`write_todos`), subagent delegation (`task`), and automatic
  context summarization — inherited from the SDK
- Slash commands: `/model`, `/clear`, `/todos`, `/allow`, `/help`, `/quit`
- Headless mode for scripting/CI: `medad -n "..."` or `echo "..." | medad`

## Install & run

```sh
uv sync
export ANTHROPIC_API_KEY=...   # or any provider langchain supports
uv run medad                   # interactive, in the current directory
uv run medad -n "add a hello.py that prints hi"   # headless one-shot
uv run medad --resume          # continue the last session
uv run medad -m anthropic:claude-opus-4-8         # explicit model
```

## Configuration

`~/.medad/config.toml` (global) merged with `<project>/.medad/config.toml`:

```toml
model = "anthropic:claude-opus-4-8"

[permissions]
allow_commands = ["git status", "git diff", "ls", "uv run pytest"]
auto_approve_edits = false
```

Anything not on the allowlist pauses the agent and asks. Headless mode runs
without approval gates — use it in trusted contexts only.

## Development

```sh
uv run pytest
```

## Roadmap

- Phase 3 — skills directory + `/skill:` invocation, `AGENTS.md` memory,
  custom subagent definitions
- Phase 4 — MCP servers from config, remote sandbox backends (E2B/LangSmith),
  LangSmith tracing docs
