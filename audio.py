import io
import queue

import httpx
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write

WHISPER_URL = "http://127.0.0.1:8080"
SAMPLE_RATE = 16_000
CHANNELS = 1


class AudioRecorder:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._q = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time, status) -> None:
        self._q.put(indata.copy())

    def stop_and_encode(self) -> bytes:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        chunks = []
        while not self._q.empty():
            chunks.append(self._q.get())
        audio = np.concatenate(chunks) if chunks else np.zeros((1, CHANNELS), dtype="int16")
        buf = io.BytesIO()
        wav_write(buf, SAMPLE_RATE, audio)
        return buf.getvalue()


def transcribe(wav_bytes: bytes) -> str:
    resp = httpx.post(
        f"{WHISPER_URL}/inference",
        data={"temperature": "0.0", "response_format": "json"},
        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()
