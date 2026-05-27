from unittest.mock import MagicMock, patch

from app import AcodeApp


def _bare_app() -> AcodeApp:
    """Instantiate AcodeApp without running Textual's __init__."""
    app = AcodeApp.__new__(AcodeApp)
    app._whisper_proc = None
    app._busy = False
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

    # First call (binary check) → True, second call (model check) → False
    with patch("app.os.path.exists", side_effect=[True, False]):
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


# ── _busy race condition ───────────────────────────────────────────────────────

def test_busy_is_set_before_process_input_is_called():
    """_busy must be True on the main thread when _process_input is invoked."""
    app = _bare_app()
    busy_at_call_time = []

    def capture_busy(_):
        busy_at_call_time.append(app._busy)

    app._process_input = MagicMock(side_effect=capture_busy)
    app.query_one = MagicMock()

    event = MagicMock()
    event.text = "hello"
    app.on_submittable_text_area_submitted(event)

    assert busy_at_call_time == [True]


def test_submit_while_busy_does_not_call_process_input():
    app = _bare_app()
    app._busy = True
    app._process_input = MagicMock()
    app.query_one = MagicMock()

    event = MagicMock()
    event.text = "hello"
    app.on_submittable_text_area_submitted(event)

    app._process_input.assert_not_called()


def test_model_command_does_not_set_busy():
    """Slash commands bypass the agent; _busy must not be left True."""
    app = _bare_app()
    app._show_model_selector = MagicMock()
    app.query_one = MagicMock()

    event = MagicMock()
    event.text = "/model"
    app.on_submittable_text_area_submitted(event)

    assert app._busy is False
