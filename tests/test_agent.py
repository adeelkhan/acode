from unittest.mock import patch, MagicMock

from agent import ReactAgent


# ── helpers ───────────────────────────────────────────────────────────────────

def _chat_response(content: str, tool_calls=None) -> MagicMock:
    resp = MagicMock()
    resp.message.content = content
    resp.message.tool_calls = tool_calls
    return resp


def _tool_call(name: str, arguments: dict) -> MagicMock:
    tc = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def _collect_events(agent, user_input: str) -> list[tuple[str, str]]:
    events = []
    agent.run(user_input, on_event=lambda k, t: events.append((k, t)))
    return events


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_agent_initial_history_has_system_prompt():
    agent = ReactAgent(model="test-model")
    assert len(agent.history) == 1
    assert agent.history[0]["role"] == "system"


def test_agent_stores_model_name():
    agent = ReactAgent(model="qwen2:7b")
    assert agent.model == "qwen2:7b"


# ── _parse_content_as_tool_calls ──────────────────────────────────────────────

def test_parse_content_none_returns_none():
    assert ReactAgent._parse_content_as_tool_calls(None) is None


def test_parse_content_empty_string_returns_none():
    assert ReactAgent._parse_content_as_tool_calls("") is None


def test_parse_content_valid_json_returns_tool_call():
    content = '{"name": "web_search", "arguments": {"query": "hello"}}'
    result = ReactAgent._parse_content_as_tool_calls(content)
    assert result is not None
    assert len(result) == 1
    assert result[0].function.name == "web_search"
    assert result[0].function.arguments == {"query": "hello"}


def test_parse_content_invalid_json_returns_none():
    assert ReactAgent._parse_content_as_tool_calls("not json at all") is None


def test_parse_content_json_missing_name_key_returns_none():
    assert ReactAgent._parse_content_as_tool_calls('{"arguments": {}}') is None


def test_parse_content_json_missing_arguments_key_returns_none():
    assert ReactAgent._parse_content_as_tool_calls('{"name": "web_search"}') is None


def test_parse_content_json_array_returns_none():
    assert ReactAgent._parse_content_as_tool_calls('[{"name": "x", "arguments": {}}]') is None


# ── _llm_response_to_dict ─────────────────────────────────────────────────────

def test_llm_response_to_dict_no_tool_calls():
    msg = MagicMock()
    msg.content = "Hello!"
    msg.tool_calls = None
    result = ReactAgent._llm_response_to_dict(msg)
    assert result == {"role": "assistant", "content": "Hello!"}


def test_llm_response_to_dict_none_content_becomes_empty_string():
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = None
    result = ReactAgent._llm_response_to_dict(msg)
    assert result["content"] == ""


def test_llm_response_to_dict_with_tool_calls():
    tc = _tool_call("web_search", {"query": "test"})
    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [tc]
    result = ReactAgent._llm_response_to_dict(msg)
    assert "tool_calls" in result
    assert result["tool_calls"][0]["function"]["name"] == "web_search"
    assert result["tool_calls"][0]["function"]["arguments"] == {"query": "test"}


def test_llm_response_to_dict_multiple_tool_calls():
    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [
        _tool_call("web_search", {"query": "a"}),
        _tool_call("get_weather", {"location": "London"}),
    ]
    result = ReactAgent._llm_response_to_dict(msg)
    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][1]["function"]["name"] == "get_weather"


# ── run — event sequences ─────────────────────────────────────────────────────

def test_run_simple_response_emits_thinking_then_llm():
    agent = ReactAgent(model="test")
    with patch("agent.ollama.chat", return_value=_chat_response("Hi there!")):
        events = _collect_events(agent, "hello")
    kinds = [k for k, _ in events]
    assert kinds == ["thinking", "llm"]


def test_run_simple_response_llm_text_matches():
    agent = ReactAgent(model="test")
    with patch("agent.ollama.chat", return_value=_chat_response("Hi there!")):
        events = _collect_events(agent, "hello")
    llm_texts = [t for k, t in events if k == "llm"]
    assert llm_texts == ["Hi there!"]


def test_run_tool_call_emits_correct_event_sequence():
    agent = ReactAgent(model="test")
    tc = _tool_call("web_search", {"query": "python"})
    responses = [_chat_response("", tool_calls=[tc]), _chat_response("Here are results.")]
    with patch("agent.ollama.chat", side_effect=responses):
        with patch("agent.TOOL_DISPATCH", {"web_search": lambda _: "search result"}):
            events = _collect_events(agent, "search python")
    kinds = [k for k, _ in events]
    assert kinds == ["thinking", "tool_call", "tool_result", "thinking", "llm"]


def test_run_tool_call_text_contains_tool_name():
    agent = ReactAgent(model="test")
    tc = _tool_call("get_weather", {"location": "London"})
    responses = [_chat_response("", tool_calls=[tc]), _chat_response("It's sunny.")]
    with patch("agent.ollama.chat", side_effect=responses):
        with patch("agent.TOOL_DISPATCH", {"get_weather": lambda _: "Sunny, 22°C"}):
            events = _collect_events(agent, "weather in London")
    tool_call_texts = [t for k, t in events if k == "tool_call"]
    assert any("get_weather" in t for t in tool_call_texts)


def test_run_unknown_tool_emits_tool_result_with_error():
    agent = ReactAgent(model="test")
    tc = _tool_call("nonexistent_tool", {})
    responses = [_chat_response("", tool_calls=[tc]), _chat_response("Done.")]
    with patch("agent.ollama.chat", side_effect=responses):
        events = _collect_events(agent, "do something")
    tool_results = [t for k, t in events if k == "tool_result"]
    assert any("Unknown tool" in t for t in tool_results)


def test_run_tool_dispatch_exception_emits_tool_error():
    agent = ReactAgent(model="test")
    tc = _tool_call("web_search", {"query": "test"})
    responses = [_chat_response("", tool_calls=[tc]), _chat_response("Done.")]

    def boom(_):
        raise RuntimeError("network down")

    with patch("agent.ollama.chat", side_effect=responses):
        with patch("agent.TOOL_DISPATCH", {"web_search": boom}):
            events = _collect_events(agent, "search")
    tool_results = [t for k, t in events if k == "tool_result"]
    assert any("Tool error" in t for t in tool_results)


# ── run — history management ──────────────────────────────────────────────────

def test_run_appends_user_message_to_history():
    agent = ReactAgent(model="test")
    with patch("agent.ollama.chat", return_value=_chat_response("reply")):
        agent.run("hello", on_event=lambda _k, _t: None)
    assert any(m["role"] == "user" and m["content"] == "hello" for m in agent.history)


def test_run_appends_assistant_response_to_history():
    agent = ReactAgent(model="test")
    with patch("agent.ollama.chat", return_value=_chat_response("my reply")):
        agent.run("hi", on_event=lambda _k, _t: None)
    assert any(m["role"] == "assistant" and m["content"] == "my reply" for m in agent.history)


def test_run_appends_tool_result_to_history():
    agent = ReactAgent(model="test")
    tc = _tool_call("web_search", {"query": "test"})
    responses = [_chat_response("", tool_calls=[tc]), _chat_response("Done.")]
    with patch("agent.ollama.chat", side_effect=responses):
        with patch("agent.TOOL_DISPATCH", {"web_search": lambda _: "tool output"}):
            agent.run("search", on_event=lambda _k, _t: None)
    assert any(m["role"] == "tool" and m["content"] == "tool output" for m in agent.history)


# ── run — iteration limit ─────────────────────────────────────────────────────

def test_run_emits_error_when_iteration_limit_reached():
    agent = ReactAgent(model="test")
    tc = _tool_call("web_search", {"query": "loop"})
    # Always return a tool call — agent will never produce a final answer
    infinite_tool_response = _chat_response("", tool_calls=[tc])
    with patch("agent.ollama.chat", return_value=infinite_tool_response):
        with patch("agent.TOOL_DISPATCH", {"web_search": lambda _: "result"}):
            events = _collect_events(agent, "loop forever")
    error_events = [t for k, t in events if k == "error"]
    assert error_events, "expected an error event after iteration limit"
    assert "iteration" in error_events[-1].lower()


def test_run_returns_empty_string_when_iteration_limit_reached():
    agent = ReactAgent(model="test")
    tc = _tool_call("web_search", {"query": "loop"})
    infinite_tool_response = _chat_response("", tool_calls=[tc])
    with patch("agent.ollama.chat", return_value=infinite_tool_response):
        with patch("agent.TOOL_DISPATCH", {"web_search": lambda _: "result"}):
            result = agent.run("loop forever", on_event=lambda _k, _t: None)
    assert result == ""


# ── reset ─────────────────────────────────────────────────────────────────────

def test_reset_removes_conversation_messages():
    agent = ReactAgent(model="test")
    agent.history.append({"role": "user", "content": "hello"})
    agent.history.append({"role": "assistant", "content": "hi"})
    agent.reset()
    assert len(agent.history) == 1


def test_reset_preserves_system_prompt():
    agent = ReactAgent(model="test")
    agent.history.append({"role": "user", "content": "hello"})
    agent.reset()
    assert agent.history[0]["role"] == "system"


def test_reset_allows_fresh_conversation():
    agent = ReactAgent(model="test")
    with patch("agent.ollama.chat", return_value=_chat_response("first")):
        agent.run("turn one", on_event=lambda _k, _t: None)
    assert len(agent.history) > 2  # has accumulated messages

    agent.reset()

    with patch("agent.ollama.chat", return_value=_chat_response("second")):
        agent.run("turn two", on_event=lambda _k, _t: None)
    # fresh turn: only system + user + assistant, no leftover from turn one
    roles = [m["role"] for m in agent.history]
    assert roles == ["system", "user", "assistant"]
