import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_client import MCPRegistry, MCPTool, _build_transport, _safe_id, _to_fastmcp_transport


# ── _safe_id ──────────────────────────────────────────────────────────────────

def test_safe_id_alphanumeric_unchanged():
    assert _safe_id("myserver123") == "myserver123"

def test_safe_id_hyphens_become_underscores():
    assert _safe_id("my-server") == "my_server"

def test_safe_id_dots_become_underscores():
    assert _safe_id("my.server") == "my_server"

def test_safe_id_slashes_become_underscores():
    assert _safe_id("a/b") == "a_b"


# ── MCPTool ───────────────────────────────────────────────────────────────────

def test_dispatch_name_format():
    tool = MCPTool("my-server", "get_weather", "", {})
    assert tool.dispatch_name == "mcp__my_server__get_weather"

def test_dispatch_name_starts_with_mcp_prefix():
    assert MCPTool("srv", "tool", "", {}).dispatch_name.startswith("mcp__")

def test_mcp_tool_enabled_by_default():
    assert MCPTool("srv", "tool", "desc", {}).enabled is True


# ── _build_transport ──────────────────────────────────────────────────────────

def test_build_transport_url_returns_string():
    transport, err = _build_transport("srv", {"url": "http://localhost:8000/mcp"})
    assert err is None
    assert transport == "http://localhost:8000/mcp"

def test_build_transport_url_strips_whitespace():
    transport, err = _build_transport("srv", {"url": "  http://localhost/mcp  "})
    assert err is None
    assert transport == "http://localhost/mcp"

def test_build_transport_empty_url_returns_error():
    transport, err = _build_transport("srv", {"url": "   "})
    assert transport is None
    assert "empty" in err

def test_build_transport_command_returns_list():
    transport, err = _build_transport("srv", {"command": "python", "args": ["/path/to/server.py"]})
    assert err is None
    assert transport == ["python", "/path/to/server.py"]

def test_build_transport_command_without_args():
    transport, err = _build_transport("srv", {"command": "/usr/bin/server"})
    assert err is None
    assert transport == ["/usr/bin/server"]

def test_build_transport_empty_command_returns_error():
    transport, err = _build_transport("srv", {"command": "   "})
    assert transport is None
    assert "empty" in err

def test_build_transport_args_not_list_returns_error():
    transport, err = _build_transport("srv", {"command": "python", "args": "notalist"})
    assert transport is None
    assert "list" in err

def test_build_transport_missing_both_url_and_command_returns_error():
    transport, err = _build_transport("srv", {})
    assert transport is None
    assert err is not None


# ── _to_fastmcp_transport ─────────────────────────────────────────────────────

def test_to_fastmcp_transport_url_passthrough():
    url = "http://localhost:8000/mcp"
    assert _to_fastmcp_transport(url) == url

def test_to_fastmcp_transport_python_script_creates_python_transport(tmp_path):
    from fastmcp.client.transports import PythonStdioTransport
    script = tmp_path / "server.py"
    script.touch()
    result = _to_fastmcp_transport(["python", str(script)])
    assert isinstance(result, PythonStdioTransport)

def test_to_fastmcp_transport_python3_script_creates_python_transport(tmp_path):
    from fastmcp.client.transports import PythonStdioTransport
    script = tmp_path / "server.py"
    script.touch()
    result = _to_fastmcp_transport(["python3", str(script)])
    assert isinstance(result, PythonStdioTransport)

def test_to_fastmcp_transport_generic_command_creates_stdio_transport():
    from fastmcp.client.transports import StdioTransport
    result = _to_fastmcp_transport(["/usr/bin/my-server", "--port", "9000"])
    assert isinstance(result, StdioTransport)

def test_to_fastmcp_transport_non_py_file_uses_stdio_transport():
    from fastmcp.client.transports import StdioTransport
    result = _to_fastmcp_transport(["python", "/path/to/server.js"])
    assert isinstance(result, StdioTransport)


# ── helpers ───────────────────────────────────────────────────────────────────

def _raw_tool(name: str, description: str = "desc", schema: dict | None = None) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.description = description
    t.inputSchema = schema or {}
    return t


def _registry_with_tools(tmp_path, server_cfg: dict, tools: list) -> MCPRegistry:
    """Build a registry whose load() is driven by a patched _run_async."""
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": server_cfg}))
    registry = MCPRegistry(config_path=cfg)
    # _run_async is called twice in load(): _close_all_clients + _fetch_tools per server
    side_effects = [None] + tools  # first call returns None (close_all), rest are tool lists
    with patch.object(registry, "_run_async", side_effect=side_effects):
        registry.load()
    return registry


# ── MCPRegistry.load ──────────────────────────────────────────────────────────

def test_load_no_config_file_is_noop(tmp_path):
    registry = MCPRegistry(config_path=tmp_path / "missing.json")
    with patch.object(registry, "_run_async", return_value=None):
        registry.load()
    assert registry.list_tools() == []
    assert registry.errors == []


def test_load_invalid_json_records_error(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text("{ bad json }")
    registry = MCPRegistry(config_path=cfg)
    with patch.object(registry, "_run_async", return_value=None):
        registry.load()
    assert any("mcp.json" in e for e in registry.errors)


def test_load_server_missing_url_and_command_records_error(tmp_path):
    registry = _registry_with_tools(tmp_path, {"srv": {}}, [])
    assert registry.list_tools() == []
    assert any("srv" in e for e in registry.errors)


def test_load_url_server_populates_tools(tmp_path):
    raw = _raw_tool("search", "Search the web")
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[raw]],
    )
    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "search"
    assert tools[0].server_name == "srv"


def test_load_command_server_populates_tools(tmp_path):
    raw = _raw_tool("echo")
    script = tmp_path / "server.py"
    script.touch()
    registry = _registry_with_tools(
        tmp_path,
        {"local": {"command": "python", "args": [str(script)]}},
        [[raw]],
    )
    assert len(registry.list_tools()) == 1
    assert registry.list_tools()[0].name == "echo"


def test_load_unreachable_server_records_error(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"srv": {"url": "http://localhost:9999/mcp"}}}))
    registry = MCPRegistry(config_path=cfg)
    with patch.object(registry, "_run_async", side_effect=[None, ConnectionRefusedError("refused")]):
        registry.load()
    assert registry.list_tools() == []
    assert any("srv" in e for e in registry.errors)


def test_load_multiple_servers(tmp_path):
    raw_a = _raw_tool("tool_a")
    raw_b = _raw_tool("tool_b")
    registry = _registry_with_tools(
        tmp_path,
        {
            "srv1": {"url": "http://localhost:8001/mcp"},
            "srv2": {"url": "http://localhost:8002/mcp"},
        },
        [[raw_a], [raw_b]],
    )
    names = {t.name for t in registry.list_tools()}
    assert names == {"tool_a", "tool_b"}


def test_load_clears_state_on_reload(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"srv": {"url": "http://localhost:9000/mcp"}}}))
    registry = MCPRegistry(config_path=cfg)

    with patch.object(registry, "_run_async", side_effect=[None, [_raw_tool("old_tool")]]):
        registry.load()
    assert len(registry.list_tools()) == 1

    with patch.object(registry, "_run_async", side_effect=[None, []]):
        registry.load()
    assert registry.list_tools() == []


# ── get_tool_definitions ──────────────────────────────────────────────────────

def test_get_tool_definitions_ollama_format(tmp_path):
    raw = _raw_tool("search", "Search", {"type": "object", "properties": {}})
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[raw]],
    )
    defs = registry.get_tool_definitions()
    assert len(defs) == 1
    fn = defs[0]["function"]
    assert fn["name"] == "mcp__srv__search"
    assert "srv" in fn["description"]
    assert fn["parameters"] == {"type": "object", "properties": {}}


def test_get_tool_definitions_excludes_disabled_tools(tmp_path):
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[_raw_tool("tool_x")]],
    )
    registry.set_tool_enabled("mcp__srv__tool_x", False)
    assert registry.get_tool_definitions() == []


def test_get_tool_definitions_empty_with_no_tools(tmp_path):
    registry = MCPRegistry(config_path=tmp_path / "missing.json")
    assert registry.get_tool_definitions() == []


# ── set_tool_enabled ──────────────────────────────────────────────────────────

def test_set_tool_enabled_toggles_to_false(tmp_path):
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[_raw_tool("tool_x")]],
    )
    registry.set_tool_enabled("mcp__srv__tool_x", False)
    assert registry.list_tools()[0].enabled is False


def test_set_tool_enabled_toggles_back_to_true(tmp_path):
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[_raw_tool("tool_x")]],
    )
    registry.set_tool_enabled("mcp__srv__tool_x", False)
    registry.set_tool_enabled("mcp__srv__tool_x", True)
    assert registry.list_tools()[0].enabled is True


def test_set_tool_enabled_unknown_key_is_noop(tmp_path):
    registry = MCPRegistry(config_path=tmp_path / "missing.json")
    registry.set_tool_enabled("mcp__ghost__tool", False)  # must not raise


# ── call_tool ─────────────────────────────────────────────────────────────────

def test_call_tool_unknown_dispatch_name_returns_error(tmp_path):
    registry = MCPRegistry(config_path=tmp_path / "missing.json")
    result = registry.call_tool("mcp__ghost__tool", {})
    assert "Unknown MCP tool" in result


def test_call_tool_returns_string_result(tmp_path):
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[_raw_tool("echo")]],
    )
    with patch.object(registry, "_run_async", return_value="hello world"):
        result = registry.call_tool("mcp__srv__echo", {"text": "hello"})
    assert result == "hello world"


def test_call_tool_exception_wrapped_as_error_string(tmp_path):
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[_raw_tool("boom")]],
    )
    with patch.object(registry, "_run_async", side_effect=RuntimeError("server exploded")):
        result = registry.call_tool("mcp__srv__boom", {})
    assert "MCP tool error" in result
    assert "server exploded" in result


def test_call_tool_timeout_returns_timeout_message(tmp_path):
    from concurrent.futures import TimeoutError as FuturesTimeoutError
    registry = _registry_with_tools(
        tmp_path,
        {"srv": {"url": "http://localhost:9000/mcp"}},
        [[_raw_tool("slow")]],
    )
    with patch.object(registry, "_run_async", side_effect=FuturesTimeoutError()):
        result = registry.call_tool("mcp__srv__slow", {})
    assert "timed out" in result
