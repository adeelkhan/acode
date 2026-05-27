---
name: project-acode-context
description: Core architecture, tech stack, and testing conventions for the acode TUI project
metadata:
  type: project
---

acode is a Python TUI application (Textual framework) that wraps a ReAct agent backed by Ollama local LLMs. It provides a terminal chat interface with tool use (web search, shell exec, weather, web fetch).

**Stack:** Python 3.14, Textual (TUI), Ollama (LLM backend), httpx (audio transcription), sounddevice + scipy + numpy (audio recording), DuckDuckGo search, requests.

**Module layout:**
- `app.py` — AcodeApp (Textual App), worker threads for agent + STT
- `widgets.py` — ThinkingIndicator, CommandHints, ModelInfoBar, ModelSelectModal, OllamaErrorModal, AgentCard, CopyButton (+ SubmittableTextArea, MicButton on audio branch)
- `agent.py` — ReactAgent: ReAct loop against Ollama, tool dispatch
- `helpers.py` — copy_to_clipboard (pbcopy), check_ollama, list_models, get_model_info
- `tools.py` — web_fetch, web_search, get_weather, shell_exec + blocklist regex
- `audio.py` — AudioRecorder (sounddevice), transcribe() via whisper-server HTTP (audio branch only)

**Testing:** pytest, unittest.mock. 113 tests pass on main. Test files mirror module names in `tests/`. No Textual pilot/integration tests — widget state is tested by direct instantiation.

**Branch situation:** `feat/audio-tts-input` adds audio/STT feature (audio.py, MicButton, SubmittableTextArea, whisper-server subprocess management). The branch tip partially reverts back to plain Input but the audio commits remain in history.

**Why:** [[project-audio-branch-status]]
