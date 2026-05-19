from unittest.mock import patch, MagicMock

from helpers import check_ollama, get_model_info


def _model(name: str) -> MagicMock:
    m = MagicMock()
    m.model = name
    return m


def _show_response(
    family="llama",
    parameter_count=None,
    parameter_size=None,
    context_length=131072,
    embedding_length=4096,
    quantization_level="Q4_K_M",
    capabilities=None,
) -> MagicMock:
    resp = MagicMock()
    resp.details.family = family
    resp.details.parameter_size = parameter_size
    resp.details.quantization_level = quantization_level
    resp.capabilities = capabilities if capabilities is not None else ["completion"]
    resp.modelinfo = {
        "general.architecture": family,
        "general.parameter_count": parameter_count,
        f"{family}.context_length": context_length,
        f"{family}.embedding_length": embedding_length,
    }
    return resp


# ── check_ollama ──────────────────────────────────────────────────────────────

def test_check_ollama_server_unreachable():
    with patch("helpers.ollama.list", side_effect=Exception("connection refused")):
        ok, title, msg = check_ollama("llama3")
    assert not ok
    assert title == "Backend Server Missing"
    assert "ollama serve" in msg


def test_check_ollama_model_not_available():
    with patch("helpers.ollama.list") as mock_list:
        mock_list.return_value.models = [_model("mistral:latest")]
        ok, title, msg = check_ollama("llama3")
    assert not ok
    assert title == "Model Not Available"
    assert "ollama pull llama3" in msg


def test_check_ollama_exact_match():
    with patch("helpers.ollama.list") as mock_list:
        mock_list.return_value.models = [_model("llama3:latest")]
        ok, _, _ = check_ollama("llama3:latest")
    assert ok


def test_check_ollama_prefix_match():
    with patch("helpers.ollama.list") as mock_list:
        mock_list.return_value.models = [_model("llama3:8b")]
        ok, _, _ = check_ollama("llama3")
    assert ok


def test_check_ollama_returns_empty_strings_on_success():
    with patch("helpers.ollama.list") as mock_list:
        mock_list.return_value.models = [_model("llama3:latest")]
        ok, title, msg = check_ollama("llama3:latest")
    assert ok
    assert title == ""
    assert msg == ""


# ── get_model_info ────────────────────────────────────────────────────────────

def test_get_model_info_billion_param_count():
    resp = _show_response(family="qwen2", parameter_count=7_000_000_000)
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("qwen2:7b")
    assert info["params"] == "7B"
    assert info["arch"] == "qwen2"


def test_get_model_info_trillion_param_count():
    resp = _show_response(parameter_count=1_000_000_000_000)
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("big-model")
    assert info["params"] == "1T"


def test_get_model_info_local_gguf_uses_string_size():
    # Local GGUF models have no integer parameter_count; fall back to parameter_size string
    resp = _show_response(family="mistral", parameter_count=None, parameter_size="24.0B")
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("devstral-small-2:latest")
    assert info["params"] == "24.0B"


def test_get_model_info_context_formatted_in_k():
    resp = _show_response(parameter_count=7_000_000_000, context_length=131072)
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("model")
    assert info["context"] == "128K"


def test_get_model_info_small_context_not_formatted():
    resp = _show_response(parameter_count=7_000_000_000, context_length=512)
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("model")
    assert info["context"] == "512"


def test_get_model_info_embedding_length():
    resp = _show_response(parameter_count=7_000_000_000, embedding_length=4096)
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("model")
    assert info["embedding"] == "4096"


def test_get_model_info_capabilities_list():
    resp = _show_response(capabilities=["completion", "tools"])
    with patch("helpers.ollama.show", return_value=resp):
        info = get_model_info("model")
    assert info["capabilities"] == ["completion", "tools"]


def test_get_model_info_exception_returns_all_na():
    with patch("helpers.ollama.show", side_effect=Exception("not found")):
        info = get_model_info("missing-model")
    assert info == dict(arch="N/A", params="N/A", context="N/A",
                        embedding="N/A", quant="N/A", capabilities=[])
