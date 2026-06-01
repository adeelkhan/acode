import json
from typing import Callable
import ollama
from tools import TOOL_DEFINITIONS, TOOL_DISPATCH

import os

from mcp_client import MCPRegistry


class _ToolFunction:
    """Minimal stand-in for ollama's tool-call function object."""
    __slots__ = ("name", "arguments")

    def __init__(self, name: str, arguments: dict) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    """Minimal stand-in for ollama's tool-call object."""
    __slots__ = ("function",)

    def __init__(self, name: str, arguments: dict) -> None:
        self.function = _ToolFunction(name, arguments)

_CWD = os.getcwd()

SYSTEM_PROMPT = f"""You are a concise, accurate AI assistant with access to tools.

Response rules (MUST follow, no exceptions):
1. Answer only what the user asked. Do not add unsolicited context, caveats, disclaimers, or suggestions.
2. Be brief. Use the minimum words needed to fully answer the question.
3. Never pad responses with phrases like "Certainly!", "Great question!", "Of course!", or closing remarks.
4. Use tools when needed to answer accurately. After gathering information, give a direct final answer — do not narrate the tool-use process.

Available tools:
- web_fetch: Fetch content from a URL
- web_search: Search the web via DuckDuckGo
- get_weather: Get current weather for a location
- shell_exec: Run shell commands — STRICT RULES APPLY (see below)

Shell execution rules (MUST follow, no exceptions):
1. You may only operate within the current working directory: {_CWD}
2. Never use `cd` to navigate outside this directory.
3. Never use absolute paths that point outside {_CWD}.
4. Never run destructive commands such as `rm -rf`, `rmdir`, `mkfs`, `dd`, `shutdown`, `reboot`, or anything that modifies system files.
5. Never read or write sensitive files (e.g. ~/.ssh, ~/.aws, /etc/passwd).
6. If a user request requires operating outside these boundaries, refuse and explain why.
"""


class ReactAgent:
    def __init__(self, model: str = "minimax-m2.5:cloud"):
        self.model = model
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.mcp_registry: MCPRegistry | None = None

    def run(self, user_input: str, on_event: Callable[[str, str], None]) -> str:
        """
        Run the ReAct loop for one user turn.
        on_event(kind, text) is called for each event:
          kind = "llm"  -> LLM text chunk
          kind = "tool_call" -> tool being invoked
          kind = "tool_result" -> tool output
          kind = "error" -> error message
        Returns the final assistant response text.
        """
        self.history.append({"role": "user", "content": user_input})

        max_iterations = 10
        final_response = ""

        extra_tools = self.mcp_registry.get_tool_definitions() if self.mcp_registry else []

        for _ in range(max_iterations):
            on_event("thinking", "Thinking...")
            response = ollama.chat(
                model=self.model,
                messages=self.history,
                tools=TOOL_DEFINITIONS + extra_tools,
            )

            message = response.message
            tool_calls = message.tool_calls or self._parse_content_as_tool_calls(message.content)

            if not tool_calls:
                # Final answer from LLM
                final_response = message.content or ""
                on_event("llm", final_response)
                self.history.append({"role": "assistant", "content": final_response})
                break

            # Add assistant message with tool calls to history
            self.history.append(self._llm_response_to_dict(message))

            # Execute each tool call
            for tc in tool_calls:
                name = tc.function.name
                args = tc.function.arguments or {}

                on_event("tool_call", f"Calling tool: {name}({json.dumps(args)})")

                dispatch = TOOL_DISPATCH.get(name)
                if dispatch:
                    try:
                        result = dispatch(args)
                    except Exception as e:
                        result = f"Tool error: {e}"
                elif name.startswith("mcp__") and self.mcp_registry:
                    result = self.mcp_registry.call_tool(name, args)
                else:
                    result = f"Unknown tool: {name}"

                on_event("tool_result", f"[{name}] → {result[:500]}{'...' if len(result) > 500 else ''}")

                self.history.append({
                    "role": "tool",
                    "content": result,
                })

        if not final_response:
            on_event("error", "Agent did not produce a response after reaching the iteration limit.")

        return final_response

    @staticmethod
    def _parse_content_as_tool_calls(content: str | None) -> list | None:
        """Fallback for models that return tool calls as JSON text in content."""
        if not content:
            return None
        try:
            data = json.loads(content.strip())
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                return [_ToolCall(data["name"], data["arguments"])]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    @staticmethod
    def _llm_response_to_dict(message) -> dict:
        d: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            d["tool_calls"] = [
                {
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in message.tool_calls
            ]
        return d

    def reset(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
