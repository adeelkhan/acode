from unittest.mock import MagicMock, patch

import pytest

import audio


def test_transcribe_posts_to_correct_endpoint():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"text": "hello"}
    mock_resp.raise_for_status = MagicMock()
    with patch("audio.httpx.post", return_value=mock_resp) as mock_post:
        audio.transcribe(b"fake-wav")
    url = mock_post.call_args[0][0]
    assert url == "http://127.0.0.1:8080/inference"


def test_transcribe_sends_file_field():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"text": "hello"}
    mock_resp.raise_for_status = MagicMock()
    with patch("audio.httpx.post", return_value=mock_resp) as mock_post:
        audio.transcribe(b"fake-wav")
    files = mock_post.call_args[1]["files"]
    assert "file" in files
    assert files["file"][0] == "audio.wav"


def test_transcribe_returns_stripped_text():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"text": "  hello world  "}
    mock_resp.raise_for_status = MagicMock()
    with patch("audio.httpx.post", return_value=mock_resp):
        result = audio.transcribe(b"fake-wav")
    assert result == "hello world"


def test_transcribe_returns_empty_string_on_missing_key():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_resp.raise_for_status = MagicMock()
    with patch("audio.httpx.post", return_value=mock_resp):
        result = audio.transcribe(b"fake-wav")
    assert result == ""


def test_transcribe_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
    with patch("audio.httpx.post", return_value=mock_resp):
        with pytest.raises(Exception, match="500"):
            audio.transcribe(b"fake-wav")


def test_audio_recorder_stop_encode_returns_bytes_when_empty():
    recorder = audio.AudioRecorder()
    result = recorder.stop_and_encode()
    assert isinstance(result, bytes)
    assert len(result) > 0   # WAV header is always present
