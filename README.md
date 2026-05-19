# acode — Agentic ReAct Terminal

A terminal user interface (TUI) for conversational AI powered by local LLMs via [Ollama](https://ollama.com). Built with a ReAct (Reason + Act) agentic loop that can use tools to answer questions requiring real-time information or system interaction.

## Screenshot

![acode screenshot](screen_shot.png?raw=true)

## Features

- **ReAct agentic loop** — the agent reasons, calls tools, observes results, and iterates until it has a final answer
- **Markdown rendering** — LLM responses are rendered with full formatting (headers, bold, code blocks, lists)
- **Model info bar** — shows architecture, parameter count, context length, embedding size, quantization, and capabilities for the active model
- **Runtime model switching** — type `/model` to open a list of available Ollama models and switch without restarting
- **Clipboard copy** — click any agent response card and press `c`, or click the `⧉` button to copy to clipboard
- **Animated thinking indicator** — flipping ⏳/⌛ shows while the model is inferring
- **In-memory conversation history** — context is preserved across turns within a session
- **Tool fallback** — works with models that return tool calls as JSON text (e.g. `qwen2.5-coder`)
- **Shell security** — `shell_exec` is restricted to the project directory; destructive commands and sensitive paths are blocked at both the prompt and code level

## Tools

| Tool | Description |
|------|-------------|
| `web_search` | Search the web via DuckDuckGo |
| `web_fetch` | Fetch and return the content of a URL |
| `get_weather` | Current weather for any location (via wttr.in, no API key needed) |
| `shell_exec` | Execute shell commands within the project directory |

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with at least one model pulled
- macOS (clipboard copy uses `pbcopy`)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd acode

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install textual ollama requests duckduckgo-search
```

## Usage

```bash
# Run with the default model (minimax-m2.5:cloud)
python app.py

# Run with a specific model
python app.py mistral:latest
python app.py qwen2.5-coder:7b
```

## Key Bindings

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `c` | Copy focused agent response to clipboard |
| `Ctrl+R` | Reset conversation history |
| `Ctrl+Q` | Quit |

## Slash Commands

| Command | Action |
|---------|--------|
| `/model` | Open model selector — pick any model from `ollama list` |

## Project Structure

```
acode/
├── app.py        # Textual TUI — layout, event handling, slash commands
├── app.tcss      # Textual CSS — styles for all card types and modals
├── agent.py      # ReactAgent — ReAct loop, Ollama integration
├── tools.py      # Tool implementations and definitions
├── helpers.py    # Utility functions — Ollama checks, model info
├── widgets.py    # All Textual widget classes
├── logo.txt      # ASCII logo
└── tests/        # Pytest test suite (106 tests)
```

## Recommended Models

Models with native tool-calling support work best:

- `minimax-m2.5:cloud` — default, strong tool use
- `qwen2.5-coder:7b` — good for coding tasks (JSON tool call fallback active)
- `mistral:latest` — general purpose

## Running Tests

```bash
source venv/bin/activate
pytest -v
```
