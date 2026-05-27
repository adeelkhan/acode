---
name: local-stt-research
description: Research findings on local/offline STT server options for a Python Textual TUI app on macOS — server options, API shapes, and mic capture patterns
metadata:
  type: project
---

User is building a Python Textual TUI app where users press a button to record mic audio, send it to a local STT server, and get back text to insert into an input box. macOS only. No cloud APIs.

**Key candidates evaluated (2025-2026):**

1. **whisper.cpp server** — C++ binary with `--convert` flag; POST `/inference` multipart/form-data with `file` field; Metal/CoreML gives 3x speedup on Apple Silicon; latency-tunable via `-ac 750`; requires cmake build.

2. **speaches (fka faster-whisper-server)** — OpenAI-compatible Python server; POST `/v1/audio/transcriptions` multipart/form-data; run via `uvicorn --factory speaches.main:create_app`; macOS Docker image available (CPU), native Python install possible but macOS support is unofficial (GitHub issue #499).

3. **WhisperLiveKit** — WebSocket-based real-time streaming; `pip install whisperlivekit` + `whisperlivekit-server --model tiny.en`; client sends webm/opus chunks; better for continuous transcription than push-to-talk.

4. **Vosk WebSocket server** — Kaldi-based; WS on port 2700; client sends binary PCM + JSON config `{"config": {"sample_rate": 16000}}`; much lower accuracy than Whisper but very fast and truly offline; Docker: `docker run -d -p 2700:2700 alphacep/kaldi-en:latest`.

5. **macos-speech-server** — Swift project using Apple Neural Engine / FluidAudio; POST `/v1/audio/transcriptions` multipart; also serves Wyoming protocol; zero Python dependencies on server side; requires `swift build`.

**Recommended for this use case:** whisper.cpp server (push-to-talk, macOS, low latency, no Python server deps, Metal acceleration).

**Client-side mic capture:** `sounddevice` (PortAudio bindings) + `scipy.io.wavfile` to produce WAV bytes; send via `httpx` or `requests` multipart POST.

**Why:** Research was done to inform STT feature in the Textual TUI app on branch `feat/audio-tts-input`.
