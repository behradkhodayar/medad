"""MCP integration: mount tools from MCP servers declared in config.

Each `[mcp.servers.<name>]` table in config.toml is passed through verbatim
as a langchain-mcp-adapters connection::

    [mcp.servers.github]
    transport = "stdio"
    command = "npx"
    args = ["-y", "@modelcontextprotocol/server-github"]

    [mcp.servers.docs]
    transport = "streamable_http"
    url = "https://example.com/mcp"

The adapter's tools are async-only, but medad drives the graph with the sync
`stream()` API, so each tool gets a sync bridge that runs its coroutine via
`asyncio.run` — safe because no event loop ever runs on the REPL thread.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from medad.config import Config


def load_mcp_tools(cfg: Config) -> list[BaseTool]:
    """Connect to the configured MCP servers and return their tools."""
    if not cfg.mcp_servers:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(cfg.mcp_servers)
    try:
        tools = asyncio.run(client.get_tools())
    except Exception as exc:  # noqa: BLE001 - surface which server config is at fault
        raise RuntimeError(
            f"failed to load MCP tools from servers {sorted(cfg.mcp_servers)}: {exc}"
        ) from exc
    return [_ensure_sync(tool) for tool in tools]


def _ensure_sync(tool: BaseTool) -> BaseTool:
    """Give a coroutine-only StructuredTool a sync path."""
    if not isinstance(tool, StructuredTool) or tool.func is not None or tool.coroutine is None:
        return tool
    coroutine = tool.coroutine

    def run_sync(**kwargs: Any) -> Any:
        return asyncio.run(coroutine(**kwargs))

    tool.func = run_sync
    return tool
