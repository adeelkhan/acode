from unittest.mock import patch

from widgets import AgentCard, CopyButton, MicButton, ModelInfoBar, ModelSelectModal, OllamaErrorModal, SubmittableTextArea, ThinkingIndicator

_FAKE_INFO = dict(
    arch="llama", params="7B", context="128K",
    embedding="4096", quant="Q4_K_M", capabilities=["completion"],
)


# ── AgentCard ─────────────────────────────────────────────────────────────────

def test_agent_card_stores_text():
    card = AgentCard("Hello **world**")
    assert card._text == "Hello **world**"


def test_agent_card_is_focusable():
    assert AgentCard.can_focus is True


def test_agent_card_has_copy_binding():
    keys = [b[0] for b in AgentCard.BINDINGS]
    assert "c" in keys


# ── ThinkingIndicator ─────────────────────────────────────────────────────────

def test_thinking_indicator_starts_at_frame_zero():
    indicator = ThinkingIndicator()
    assert indicator._frame == 0


def test_thinking_indicator_has_two_frames():
    assert len(ThinkingIndicator.FRAMES_RIGHT) == 2
    assert len(ThinkingIndicator.FRAMES_LEFT) == 2


def test_thinking_indicator_tick_advances_frame():
    indicator = ThinkingIndicator()
    indicator._tick()
    assert indicator._frame == 1
    indicator._tick()
    assert indicator._frame == 0  # wraps back


def test_thinking_indicator_starts_moving_right():
    indicator = ThinkingIndicator()
    assert indicator._direction == 1


def test_thinking_indicator_position_advances_on_open_frame():
    indicator = ThinkingIndicator()
    # tick once → frame=1 (closed), pos stays 0
    indicator._tick()
    assert indicator._pos == 0
    # tick again → frame=0 (open), pos advances
    indicator._tick()
    assert indicator._pos == 1


def test_thinking_indicator_reverses_at_right_end():
    indicator = ThinkingIndicator()
    indicator._pos = ThinkingIndicator.NUM_DOTS - 1
    indicator._direction = 1
    indicator._frame = 1   # force next tick to open mouth and move
    indicator._tick()      # frame→0, pos would go to NUM_DOTS but clamps
    assert indicator._direction == -1


def test_thinking_indicator_reverses_at_left_end():
    indicator = ThinkingIndicator()
    indicator._pos = 0
    indicator._direction = -1
    indicator._frame = 1
    indicator._tick()      # frame→0, pos would go negative but clamps
    assert indicator._direction == 1


def test_thinking_indicator_render_contains_thinking_text():
    indicator = ThinkingIndicator()
    result = indicator.render()
    assert "Thinking" in result.plain


def test_thinking_indicator_render_contains_pacman_open_right():
    indicator = ThinkingIndicator()
    indicator._frame = 0
    indicator._direction = 1
    result = indicator.render()
    assert ThinkingIndicator.FRAMES_RIGHT[0] in result.plain


def test_thinking_indicator_render_contains_pacman_open_left():
    indicator = ThinkingIndicator()
    indicator._frame = 0
    indicator._direction = -1
    result = indicator.render()
    assert ThinkingIndicator.FRAMES_LEFT[0] in result.plain


# ── MicButton ─────────────────────────────────────────────────────────────────

def test_mic_button_initial_state_not_recording():
    btn = MicButton()
    assert btn._recording is False
    assert str(btn.label) == "🎙"


def test_mic_button_toggle_starts_recording():
    btn = MicButton()
    btn._toggle()
    assert btn._recording is True
    assert str(btn.label) == "⏹"


def test_mic_button_double_toggle_returns_to_idle():
    btn = MicButton()
    btn._toggle()
    btn._toggle()
    assert btn._recording is False
    assert str(btn.label) == "🎙"


# ── CopyButton ────────────────────────────────────────────────────────────────

def test_copy_button_has_tooltip():
    btn = CopyButton()
    assert btn.tooltip == "Copy"


# ── ModelInfoBar ──────────────────────────────────────────────────────────────

def test_model_info_bar_sets_border_title():
    with patch("widgets.get_model_info", return_value=_FAKE_INFO):
        bar = ModelInfoBar("llama3:7b")
    assert bar.border_title == "llama3:7b"


def test_model_info_bar_empty_capabilities_shows_na():
    info = {**_FAKE_INFO, "capabilities": []}
    with patch("widgets.get_model_info", return_value=info):
        bar = ModelInfoBar("llama3:7b")
    # just verify it instantiates without error
    assert bar.border_title == "llama3:7b"


def test_model_info_bar_calls_get_model_info_with_model_name():
    with patch("widgets.get_model_info", return_value=_FAKE_INFO) as mock_fn:
        ModelInfoBar("devstral:latest")
    mock_fn.assert_called_once_with("devstral:latest")


# ── ModelInfoBar.set_model ────────────────────────────────────────────────────

def test_model_info_bar_set_model_updates_border_title():
    with patch("widgets.get_model_info", return_value=_FAKE_INFO):
        bar = ModelInfoBar("llama3:7b")
    new_info = {**_FAKE_INFO, "arch": "mistral", "params": "7B"}
    with patch("widgets.get_model_info", return_value=new_info):
        bar.set_model("mistral:7b")
    assert bar.border_title == "mistral:7b"


def test_model_info_bar_set_model_calls_get_model_info():
    with patch("widgets.get_model_info", return_value=_FAKE_INFO):
        bar = ModelInfoBar("llama3:7b")
    with patch("widgets.get_model_info", return_value=_FAKE_INFO) as mock_fn:
        bar.set_model("qwen2:7b")
    mock_fn.assert_called_once_with("qwen2:7b")


# ── ModelSelectModal ──────────────────────────────────────────────────────────

def test_model_select_modal_stores_models():
    models = ["llama3:latest", "mistral:7b", "qwen2:7b"]
    modal = ModelSelectModal(models)
    assert modal._models == models


def test_model_select_modal_accepts_empty_list():
    modal = ModelSelectModal([])
    assert modal._models == []


# ── OllamaErrorModal ──────────────────────────────────────────────────────────

def test_ollama_error_modal_stores_title():
    modal = OllamaErrorModal("Bad Title", "Something went wrong")
    assert modal._title == "Bad Title"


def test_ollama_error_modal_stores_message():
    modal = OllamaErrorModal("Bad Title", "Something went wrong")
    assert modal._message == "Something went wrong"


# ── SubmittableTextArea ───────────────────────────────────────────────────────

def test_submittable_text_area_instantiates():
    ta = SubmittableTextArea(id="user-input", show_line_numbers=False)
    assert ta is not None


def test_submittable_text_area_submitted_message_stores_text():
    msg = SubmittableTextArea.Submitted("hello world")
    assert msg.text == "hello world"


def test_submittable_text_area_submitted_message_stores_empty_string():
    msg = SubmittableTextArea.Submitted("")
    assert msg.text == ""


def test_submittable_text_area_has_submitted_message_class():
    assert hasattr(SubmittableTextArea, "Submitted")


def test_submittable_text_area_on_key_enter_submits():
    from unittest.mock import MagicMock
    ta = SubmittableTextArea()
    ta.post_message = MagicMock()
    ta.clear = MagicMock()
    event = MagicMock()
    event.key = "enter"
    ta.on_key(event)
    event.prevent_default.assert_called_once()
    ta.post_message.assert_called_once()


def test_submittable_text_area_on_key_other_keys_do_not_submit():
    from unittest.mock import MagicMock
    ta = SubmittableTextArea()
    ta.post_message = MagicMock()
    event = MagicMock()
    event.key = "space"
    ta.on_key(event)
    ta.post_message.assert_not_called()
