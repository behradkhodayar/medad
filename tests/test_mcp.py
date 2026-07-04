"""MCP mounting: a real stdio server is spawned and its tools invoked sync."""

import sys
from pathlib import Path

import pytest
from langchain_core.tools import StructuredTool

from medad.config import load_config
from medad.mcp import _ensure_sync, load_mcp_tools

SERVER = '''
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("adder")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


mcp.run()
'''


@pytest.fixture
def mcp_config(tmp_path: Path):
    server_py = tmp_path / "server.py"
    server_py.write_text(SERVER)
    (tmp_path / ".medad").mkdir()
    (tmp_path / ".medad" / "config.toml").write_text(
        f'''
[mcp.servers.adder]
transport = "stdio"
command = "{sys.executable}"
args = ["{server_py}"]
'''
    )
    return load_config(tmp_path)


def test_no_servers_no_tools(tmp_path: Path):
    assert load_mcp_tools(load_config(tmp_path)) == []


def test_config_parses_mcp_servers(mcp_config):
    assert list(mcp_config.mcp_servers) == ["adder"]
    assert mcp_config.mcp_servers["adder"]["transport"] == "stdio"


def test_stdio_server_tools_mount_and_run_sync(mcp_config):
    tools = load_mcp_tools(mcp_config)
    names = [t.name for t in tools]
    assert "add" in names
    add = next(t for t in tools if t.name == "add")
    # The REPL drives the graph synchronously; the bridge must make this work.
    result = add.invoke({"a": 2, "b": 3})
    blocks = result if isinstance(result, list) else [{"text": result}]
    assert [b.get("text") for b in blocks] == ["5"]


def test_ensure_sync_bridges_coroutine_only_tools():
    async def double(x: int) -> int:
        return x * 2

    tool = StructuredTool.from_function(coroutine=double, name="double", description="d")
    with pytest.raises(NotImplementedError):
        tool.invoke({"x": 2})
    bridged = _ensure_sync(tool)
    assert bridged.invoke({"x": 2}) == 4
