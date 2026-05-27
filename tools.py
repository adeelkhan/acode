import os
import re
import subprocess
import requests
from duckduckgo_search import DDGS

_CWD = os.getcwd()

# NOTE: This blocklist is best-effort defense-in-depth, not a security boundary.
# A sufficiently creative prompt can bypass pattern matching; treat shell_exec
# as a convenience tool for a trusted user, not an untrusted-input sandbox.
_BLOCKED: list[tuple[str, str]] = [
    (r"\brm\b.*-[a-zA-Z]*[rR][a-zA-Z]*",            "recursive rm"),
    (r"\brmdir\b",                                    "rmdir"),
    (r"\bmkfs\b",                                     "mkfs"),
    (r"\bdd\b.*\bof=",                                "dd write"),
    (r"\b(shutdown|reboot|poweroff|halt|init\s+0)\b", "system shutdown/reboot"),
    (r"\b(fdisk|parted|diskutil\s+erase)\b",          "disk partitioning"),
    (r"\bsudo\b",                                     "sudo escalation"),
    (r"\bsu\s",                                       "su escalation"),
    # Chained dangerous commands (e.g. "echo x; rm -rf /tmp")
    (r"[|;&]\s*(rm|sudo|su\s|shutdown|reboot|poweroff|halt)\b", "chained dangerous command"),
    (r"(~|/Users/\w+|/home/\w+)/\.ssh",              "SSH directory"),
    (r"(~|/Users/\w+|/home/\w+)/\.aws",              "AWS credentials"),
    (r"/etc/(passwd|shadow|sudoers)",                 "sensitive system file"),
    (r"cd\s+(/(?!" + re.escape(_CWD.lstrip("/")) + r")|\.\.)", "cd outside project"),
]


def _validate_command(command: str) -> str | None:
    """Return an error string if the command is blocked, else None."""
    for pattern, reason in _BLOCKED:
        if re.search(pattern, command, re.IGNORECASE):
            return f"Blocked: {reason}. Shell commands are restricted to {_CWD}."
    return None


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch the content of a URL and return it as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo and return a list of results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather and forecast for a city or location using wttr.in (no API key required).",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name or location, e.g. 'New York' or 'London'"},
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Execute a shell command and return its output. Use with care.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute"},
                },
                "required": ["command"],
            },
        },
    },
]


def web_fetch(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.text[:4000]
    except Exception as e:
        return f"Error fetching {url}: {e}"


def web_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"Title: {r.get('title', '')}")
            lines.append(f"URL: {r.get('href', '')}")
            lines.append(f"Snippet: {r.get('body', '')}")
            lines.append("---")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


def get_weather(location: str) -> str:
    try:
        url = f"https://wttr.in/{location.replace(' ', '+')}?format=j1"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "curl/7.0"})
        resp.raise_for_status()
        data = resp.json()
        current = data["current_condition"][0]
        area = data["nearest_area"][0]
        city = area["areaName"][0]["value"]
        country = area["country"][0]["value"]
        desc = current["weatherDesc"][0]["value"]
        temp_c = current["temp_C"]
        temp_f = current["temp_F"]
        feels_c = current["FeelsLikeC"]
        humidity = current["humidity"]
        wind_kmph = current["windspeedKmph"]
        today = data["weather"][0]
        max_c = today["maxtempC"]
        min_c = today["mintempC"]
        return (
            f"Weather in {city}, {country}:\n"
            f"  Condition : {desc}\n"
            f"  Temp      : {temp_c}°C / {temp_f}°F  (feels like {feels_c}°C)\n"
            f"  High/Low  : {max_c}°C / {min_c}°C\n"
            f"  Humidity  : {humidity}%\n"
            f"  Wind      : {wind_kmph} km/h"
        )
    except Exception as e:
        return f"Weather error: {e}"


def shell_exec(command: str) -> str:
    error = _validate_command(command)
    if error:
        return error
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=_CWD,
        )
        output = result.stdout + result.stderr
        return output[:4000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Shell error: {e}"


TOOL_DISPATCH = {
    "web_fetch": lambda args: web_fetch(**args),
    "web_search": lambda args: web_search(**args),
    "get_weather": lambda args: get_weather(**args),
    "shell_exec": lambda args: shell_exec(**args),
}
