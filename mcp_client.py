"""MCP client — loads server config, fetches tools, and dispatches calls.

Uses fastmcp 3.x as the underlying transport layer.  Supports:
  - HTTP/SSE servers  →  { "url": "http://host/mcp" }
  - Local Python scripts (stdio)  →  { "command": "python", "args": ["/path/to/server.py"] }
  - Arbitrary stdio binaries  →  { "command": "/path/to/bin", "args": [...] }

A single background asyncio event loop is kept alive for the lifetime of the
registry.  Each MCP server gets one persistent Client connection, opened lazily
on the first tool call and kept open so that stateful servers (e.g. puppeteer)
retain their session across calls.  If a call fails the client is closed and
re-opened once automatically.

Config file (mcp.json):
    {
      "mcpServers": {
        "remote":       { "url": "http://remote.example.com/mcp" },
        "local-http":   { "url": "http://localhost:8000/mcp" },
        "local-script": { "command": "python", "args": ["/path/to/server.py"] },
        "local-bin":    { "command": "/usr/local/bin/my-mcp-server" }
      }
    }
"""

import asyncio
import base64
import json
import re
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

# Internal transport representation before fastmcp objects are built:
#   str        → HTTP/SSE URL
#   list[str]  → [command, *args] for stdio
_RawTransport = str | list[str]

MCP_CONFIG_PATH = Path(__file__).parent / "mcp.json"
TOOL_CALL_TIMEOUT = 30


def _safe_id(s: str) -> str:
    """Replace characters that are invalid in tool-call names with underscores."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


def _build_transport(server_name: str, server_cfg: dict) -> tuple[_RawTransport | None, str | None]:
    """Parse a server config entry into a raw transport descriptor.

    Returns (transport, None) on success or (None, error_message) on failure.
    """
    if "url" in server_cfg:
        url = server_cfg["url"].strip()
        if not url:
            return None, f"{server_name}: 'url' is empty"
        return url, None

    if "command" in server_cfg:
        cmd = server_cfg["command"].strip()
        if not cmd:
            return None, f"{server_name}: 'command' is empty"
        args = server_cfg.get("args", [])
        if not isinstance(args, list):
            return None, f"{server_name}: 'args' must be a list"
        return [cmd] + [str(a) for a in args], None

    return None, f"{server_name}: config must have 'url' (HTTP) or 'command' (stdio)"


def _save_image_content(item: Any, args: dict) -> str:
    """Decode an ImageContent item and save it to the cwd. Returns a human-readable path string."""
    ext = "png" if "png" in getattr(item, "mimeType", "") else "bin"
    stem = str(args.get("name", "screenshot")).replace(" ", "_")
    dest = Path.cwd() / f"{stem}.{ext}"
    dest.write_bytes(base64.b64decode(item.data))
    return f"Image saved to {dest}"


def _to_fastmcp_transport(raw: _RawTransport):
    """Convert a raw transport descriptor into a fastmcp transport object.

    For Python scripts the venv interpreter is used automatically via
    PythonStdioTransport; other commands go through the generic StdioTransport.
    URL strings are passed through unchanged (fastmcp's Client handles them).
    """
    if isinstance(raw, str):
        return raw  # HTTP/SSE URL — Client's infer_transport handles it

    from fastmcp.client.transports import PythonStdioTransport, StdioTransport

    cmd, *rest = raw
    if cmd in ("python", "python3") and rest and str(rest[0]).endswith(".py"):
        # Use PythonStdioTransport so the active venv's interpreter is picked up
        extra_args = rest[1:] if len(rest) > 1 else None
        return PythonStdioTransport(script_path=rest[0], args=extra_args)

    return StdioTransport(command=cmd, args=rest)


class MCPTool:
    """Metadata for a single tool provided by an MCP server."""

    __slots__ = ("server_name", "name", "description", "input_schema", "enabled")

    def __init__(
        self,
        server_name: str,
        name: str,
        description: str,
        input_schema: dict,
    ) -> None:
        self.server_name = server_name
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.enabled = True

    @property
    def dispatch_name(self) -> str:
        """Unique tool name used in LLM tool calls, e.g. 'mcp__myserver__mytool'."""
        return f"mcp__{_safe_id(self.server_name)}__{_safe_id(self.name)}"


class MCPRegistry:
    """Manages MCP server connections, tool listings, and tool dispatch.

    A single daemon thread runs a persistent asyncio event loop.  All async
    work is submitted via asyncio.run_coroutine_threadsafe so the existing
    thread-based worker architecture in app.py is unchanged.

    Each server gets one Client connection, opened lazily and kept alive so
    stateful servers (e.g. puppeteer) retain browser sessions between calls.
    """

    def __init__(self, config_path: Path = MCP_CONFIG_PATH) -> None:
        self._config_path = config_path
        self._transports: dict[str, Any] = {}    # server_name → fastmcp transport object
        self._tools: dict[str, MCPTool] = {}      # dispatch_name → MCPTool
        self._errors: list[str] = []
        self._open_clients: dict[str, Any] = {}  # server_name → open Client (kept alive)
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever, daemon=True, name="mcp-event-loop")
        self._loop_thread.start()

    # ── async bridge ──────────────────────────────────────────────────────────

    def _run_async(self, coro, timeout: int = TOOL_CALL_TIMEOUT):
        """Submit a coroutine to the background loop and block until done."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ── loading ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Read config and fetch tool listings from every configured MCP server."""
        self._run_async(self._close_all_clients())
        self._transports.clear()
        self._tools.clear()
        self._errors.clear()

        if not self._config_path.exists():
            return

        try:
            config = json.loads(self._config_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            self._errors.append(f"Failed to read mcp.json: {exc}")
            return

        for server_name, server_cfg in config.get("mcpServers", {}).items():
            raw, err = _build_transport(server_name, server_cfg)
            if err or raw is None:
                self._errors.append(err or f"{server_name}: unknown error")
                continue
            transport = _to_fastmcp_transport(raw)
            self._transports[server_name] = transport
            try:
                raw_tools = self._run_async(self._fetch_tools(transport))
                for t in raw_tools:
                    tool = MCPTool(
                        server_name=server_name,
                        name=t.name,
                        description=t.description or "",
                        input_schema=t.inputSchema or {},
                    )
                    self._tools[tool.dispatch_name] = tool
            except Exception as exc:
                self._errors.append(f"{server_name}: {exc}")

    async def _fetch_tools(self, transport) -> list:
        from fastmcp import Client
        async with Client(transport) as client:
            return await client.list_tools()

    # ── persistent client management ──────────────────────────────────────────

    async def _get_client(self, server_name: str):
        """Return the open Client for server_name, opening it if needed."""
        if server_name not in self._open_clients:
            from fastmcp import Client
            client = Client(self._transports[server_name])
            await client.__aenter__()
            self._open_clients[server_name] = client
        return self._open_clients[server_name]

    async def _close_client(self, server_name: str) -> None:
        client = self._open_clients.pop(server_name, None)
        if client:
            try:
                await client.__aexit__(None, None, None)
            except Exception:
                pass

    async def _close_all_clients(self) -> None:
        for name in list(self._open_clients):
            await self._close_client(name)

    # ── tool definitions for the LLM ──────────────────────────────────────────

    def get_tool_definitions(self) -> list[dict]:
        """Return enabled tools in Ollama tool format."""
        defs = []
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            defs.append({
                "type": "function",
                "function": {
                    "name": tool.dispatch_name,
                    "description": f"[{tool.server_name}] {tool.description}",
                    "parameters": tool.input_schema,
                },
            })
        return defs

    # ── tool dispatch ─────────────────────────────────────────────────────────

    async def _execute_tool(self, server_name: str, tool_name: str, args: dict) -> str:
        """Call tool_name on server_name, reconnecting once on failure."""
        result: Any = None
        for attempt in range(2):
            try:
                client = await self._get_client(server_name)
                result = await client.call_tool(tool_name, args)
                break
            except Exception:
                if attempt == 0:
                    await self._close_client(server_name)
                else:
                    raise
        content = result.content if hasattr(result, "content") else result
        if isinstance(content, list):
            parts = []
            for item in content:
                if hasattr(item, "text"):
                    parts.append(item.text)
                elif hasattr(item, "data") and hasattr(item, "mimeType"):
                    parts.append(_save_image_content(item, args))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(result)

    def call_tool(self, dispatch_name: str, args: dict) -> str:
        """Call an MCP tool by its dispatch name and return the result as a string."""
        tool = self._tools.get(dispatch_name)
        if not tool:
            return f"Unknown MCP tool: {dispatch_name}"
        if tool.server_name not in self._transports:
            return f"MCP server '{tool.server_name}' not found"
        try:
            return self._run_async(self._execute_tool(tool.server_name, tool.name, args))
        except FuturesTimeoutError:
            return f"MCP tool timed out after {TOOL_CALL_TIMEOUT}s"
        except Exception as exc:
            return f"MCP tool error: {exc}"

    # ── state management ──────────────────────────────────────────────────────

    def list_tools(self) -> list[MCPTool]:
        """Return all discovered tools (enabled and disabled)."""
        return list(self._tools.values())

    def set_tool_enabled(self, dispatch_name: str, enabled: bool) -> None:
        """Enable or disable a tool by its dispatch name."""
        if dispatch_name in self._tools:
            self._tools[dispatch_name].enabled = enabled

    @property
    def errors(self) -> list[str]:
        return list(self._errors)
