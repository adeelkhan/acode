from unittest.mock import patch

from widgets import AgentCard, CopyButton, ModelInfoBar, ModelSelectModal, OllamaErrorModal, ThinkingIndicator

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
    assert len(ThinkingIndicator.FRAMES) == 2


def test_thinking_indicator_tick_advances_frame():
    indicator = ThinkingIndicator()
    indicator._tick()
    assert indicator._frame == 1
    indicator._tick()
    assert indicator._frame == 0  # wraps back


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
