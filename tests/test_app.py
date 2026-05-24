from unittest.mock import MagicMock, patch

from app import AcodeApp


def _bare_app() -> AcodeApp:
    """Instantiate AcodeApp without running Textual's __init__."""
    app = AcodeApp.__new__(AcodeApp)
    app._whisper_proc = None
    return app


# ── _disable_mic ──────────────────────────────────────────────────────────────

def test_disable_mic_sets_disabled_flag():
    app = _bare_app()
    mock_btn = MagicMock()
    app.query_one = MagicMock(return_value=mock_btn)

    app._disable_mic("binary not found")

    assert mock_btn.disabled is True


def test_disable_mic_sets_tooltip_to_reason():
    app = _bare_app()
    mock_btn = MagicMock()
    app.query_one = MagicMock(return_value=mock_btn)

    app._disable_mic("model file missing")

    assert mock_btn.tooltip == "model file missing"


def test_disable_mic_queries_mic_btn_id():
    app = _bare_app()
    mock_btn = MagicMock()
    app.query_one = MagicMock(return_value=mock_btn)

    app._disable_mic("reason")

    app.query_one.assert_called_once_with("#mic-btn")


# ── _start_whisper_server ─────────────────────────────────────────────────────

def test_start_whisper_server_disables_mic_when_binary_missing():
    app = _bare_app()
    app._disable_mic = MagicMock()

    with patch("app.os.path.exists", return_value=False):
        app._start_whisper_server()

    app._disable_mic.assert_called_once_with("whisper-server binary not found")


def test_start_whisper_server_disables_mic_when_model_missing():
    app = _bare_app()
    app._disable_mic = MagicMock()

    def exists(path):
        return "whisper-server" in path  # binary found, model not found

    with patch("app.os.path.exists", side_effect=exists):
        app._start_whisper_server()

    app._disable_mic.assert_called_once_with("Whisper model file not found")


def test_start_whisper_server_spawns_process_when_both_present():
    app = _bare_app()
    app._disable_mic = MagicMock()
    mock_proc = MagicMock()

    with patch("app.os.path.exists", return_value=True), \
         patch("app.subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch("app.atexit.register"):
        app._start_whisper_server()

    mock_popen.assert_called_once()
    assert app._whisper_proc is mock_proc


def test_start_whisper_server_registers_atexit_on_success():
    app = _bare_app()
    app._disable_mic = MagicMock()
    mock_proc = MagicMock()

    with patch("app.os.path.exists", return_value=True), \
         patch("app.subprocess.Popen", return_value=mock_proc), \
         patch("app.atexit.register") as mock_atexit:
        app._start_whisper_server()

    mock_atexit.assert_called_once_with(mock_proc.terminate)


def test_start_whisper_server_does_not_spawn_when_binary_missing():
    app = _bare_app()
    app._disable_mic = MagicMock()

    with patch("app.os.path.exists", return_value=False), \
         patch("app.subprocess.Popen") as mock_popen:
        app._start_whisper_server()

    mock_popen.assert_not_called()
