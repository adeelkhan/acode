---
name: project-audio-branch-status
description: Status of feat/audio-tts-input branch — audio feature partially reverted at branch tip
metadata:
  type: project
---

The `feat/audio-tts-input` branch has 4 commits ahead of main:
1. `22b4c5b` — added audio.py, MicButton, AudioRecorder, whisper-server subprocess
2. `c7a7469` — added _disable_mic() logic for missing binary/model
3. `7ade5cc` — replaced SubmittableTextArea back to Input, removed MicButton from compose
4. `cf188d3` — added requirements.txt and CI portaudio install

The working tree (main) does NOT have audio.py, SubmittableTextArea, or MicButton. The branch tip partially reverted the audio UI but kept the CI dependency setup.

**Why:** The audio feature was introduced then scaled back — likely pending whisper-server portability work. The branch is not yet merged to main.

**How to apply:** When reviewing this branch, note that audio.py, test_audio.py, test_app.py (mic tests), and SubmittableTextArea tests exist only in branch commits, not the working tree.
