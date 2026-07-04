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
- **Skills**: drop `<name>/SKILL.md` dirs under `~/.medad/skills/` (global) or
  `.medad/skills/` (project); list with `/skills`, invoke with `/skill:<name> [task]`
- **Memory**: `AGENTS.md` (project) and `~/.medad/AGENTS.md` (global) load into
  every session; the agent updates them as it learns
- **Custom subagents**: define named `[[subagents]]` in config; the agent
  delegates to them via the `task` tool
- Slash commands: `/model`, `/clear`, `/compact`, `/todos`, `/skills`,
  `/skill:<name>`, `/allow`, `/help`, `/quit`
- Headless mode for scripting/CI: `medad -n "..."` or `echo "..." | medad`
- **MCP servers**: declare `[mcp.servers.<name>]` connections in config; their
  tools are mounted into the agent and gated by the same approval flow
- **Sandboxes**: `[sandbox] backend = "docker"` runs shell/file tools in a
  local container (no account needed); `backend = "langsmith"` uses a remote
  LangSmith sandbox VM instead of your host

## Install & run

```sh
uv sync
export ANTHROPIC_API_KEY=...   # or any provider langchain supports
uv run medad                   # interactive, in the current directory
uv run medad -n "add a hello.py that prints hi"   # headless one-shot
uv run medad --resume          # continue the last session
uv run medad -m anthropic:claude-opus-4-8         # explicit model
uv run medad -m openrouter:anthropic/claude-haiku-4.5   # via OpenRouter (OPENROUTER_API_KEY)
```

## Configuration

`~/.medad/config.toml` (global) merged with `<project>/.medad/config.toml`:

```toml
model = "anthropic:claude-opus-4-8"

[permissions]
allow_commands = ["git status", "git diff", "ls", "uv run pytest"]
auto_approve_edits = false

[[subagents]]
name = "reviewer"
description = "Reviews code changes for bugs and style issues"
system_prompt = "You are a meticulous code reviewer. Report findings as a list."
model = "anthropic:claude-haiku-4-5"   # optional; defaults to the main model
```

Anything not on the allowlist pauses the agent and asks. Chained or redirected
commands (`&&`, `|`, `;`, `$(...)`, `>` …) never auto-approve on a prefix
match — only an exact allowlist entry covers them. Headless mode runs without
approval gates — use it in trusted contexts only (or in a remote sandbox,
below).

### MCP servers

Each `[mcp.servers.<name>]` table is a
[langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
connection, passed through verbatim. Mounted tools show up like any other tool
and go through the approval gate in interactive mode.

```toml
[mcp.servers.github]
transport = "stdio"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]

[mcp.servers.docs]
transport = "streamable_http"
url = "https://example.com/mcp"
```

### Sandboxes

By default the agent's `execute` and file tools act on your machine. Point
them at a sandbox instead — this is what makes headless mode safe.

**Docker (local, no account):** commands run in a long-lived local container;
the only requirement is a working Docker install:

```toml
[sandbox]
backend = "docker"
image = "python:3.12-slim"   # optional; image needs python3 (see below)
mount_project = true         # optional; see below
name = "my-box"              # optional; default: medad-<project-dir-name>
```

With `mount_project` (the default) the project directory is bind-mounted at
its host path, so edits land in your working tree while the rest of the host
stays out of reach. Set it to `false` for full isolation — the agent then
works in `/workspace` inside the container. The container is reused across
runs; `docker rm -f <name>` resets it. Note that mount/image settings apply
when the container is first created, not to an existing one.

The image needs `python3` on PATH: the SDK derives the file tools
(`read`/`write`/`edit`/`ls`/`glob`/`grep`) from `execute` using small python3
snippets. Plain `execute` only needs a POSIX `sh`.

**LangSmith (remote VM):** requires `LANGSMITH_API_KEY`:

```toml
[sandbox]
backend = "langsmith"
name = "my-sandbox"     # optional; a named sandbox is reused across runs
```

Without `name`, a sandbox called `medad-<project-dir-name>` is created on
first use.

### Tracing (LangSmith)

medad's runtime is LangGraph, so full tracing is just environment variables —
every turn, tool call, and subagent run lands in LangSmith:

```sh
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=...
export LANGSMITH_PROJECT=medad   # optional; defaults to "default"
```

### Example skills

Copy any directory from [`examples/skills/`](examples/skills/) into
`~/.medad/skills/` (global) or `.medad/skills/` (project), then run
`/skills` to list and `/skill:<name> [task]` to invoke.

## Development

```sh
uv run pytest
```
