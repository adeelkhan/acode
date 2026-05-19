import subprocess
import pytest
from unittest.mock import patch, MagicMock

from tools import _validate_command, shell_exec, web_fetch, web_search, get_weather


# ── _validate_command ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "rm -rf /tmp",
    "rm -fr /tmp",
    "rmdir somedir",
    "mkfs.ext4 /dev/sda",
    "dd if=/dev/zero of=/dev/sda",
    "sudo apt install curl",
    "su root",
    "shutdown now",
    "reboot",
    "poweroff",
    "halt",
    "init 0",
    "fdisk /dev/sda",
    "parted /dev/sda",
    "diskutil erase /dev/disk1",
    "cat ~/.ssh/id_rsa",
    "cat /Users/adeelkhan/.ssh/config",
    "cat ~/.aws/credentials",
    "cat /etc/passwd",
    "cat /etc/shadow",
    "cat /etc/sudoers",
    "cd ..",
])
def test_validate_command_blocks(cmd):
    assert _validate_command(cmd) is not None


@pytest.mark.parametrize("cmd", [
    "ls",
    "pwd",
    "echo hello",
    "python app.py",
    "cat README.md",
    "grep -r foo .",
])
def test_validate_command_allows(cmd):
    assert _validate_command(cmd) is None


def test_validate_command_returns_reason_string():
    result = _validate_command("sudo ls")
    assert isinstance(result, str)
    assert "Blocked" in result


# ── shell_exec ────────────────────────────────────────────────────────────────

def test_shell_exec_blocked_returns_error():
    result = shell_exec("sudo ls")
    assert result.startswith("Blocked:")


def test_shell_exec_success():
    mock_proc = MagicMock(stdout="hello\n", stderr="")
    with patch("tools.subprocess.run", return_value=mock_proc):
        result = shell_exec("echo hello")
    assert result == "hello\n"


def test_shell_exec_combines_stdout_and_stderr():
    mock_proc = MagicMock(stdout="out\n", stderr="err\n")
    with patch("tools.subprocess.run", return_value=mock_proc):
        result = shell_exec("some command")
    assert result == "out\nerr\n"


def test_shell_exec_no_output_returns_placeholder():
    mock_proc = MagicMock(stdout="", stderr="")
    with patch("tools.subprocess.run", return_value=mock_proc):
        result = shell_exec("silent command")
    assert result == "(no output)"


def test_shell_exec_truncates_at_4000_chars():
    mock_proc = MagicMock(stdout="x" * 5000, stderr="")
    with patch("tools.subprocess.run", return_value=mock_proc):
        result = shell_exec("big output")
    assert len(result) == 4000


def test_shell_exec_timeout():
    with patch("tools.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
        result = shell_exec("sleep 100")
    assert "timed out" in result


def test_shell_exec_unexpected_error():
    with patch("tools.subprocess.run", side_effect=OSError("permission denied")):
        result = shell_exec("bad command")
    assert "Shell error" in result


# ── web_fetch ─────────────────────────────────────────────────────────────────

def test_web_fetch_returns_response_text():
    mock_resp = MagicMock()
    mock_resp.text = "<html>Hello</html>"
    with patch("tools.requests.get", return_value=mock_resp):
        result = web_fetch("http://example.com")
    assert result == "<html>Hello</html>"


def test_web_fetch_truncates_at_4000_chars():
    mock_resp = MagicMock()
    mock_resp.text = "a" * 5000
    with patch("tools.requests.get", return_value=mock_resp):
        result = web_fetch("http://example.com")
    assert len(result) == 4000


def test_web_fetch_raises_on_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("404 Not Found")
    with patch("tools.requests.get", return_value=mock_resp):
        result = web_fetch("http://example.com/missing")
    assert "Error fetching" in result


def test_web_fetch_connection_error():
    with patch("tools.requests.get", side_effect=Exception("connection refused")):
        result = web_fetch("http://unreachable.example.com")
    assert "Error fetching" in result


# ── web_search ────────────────────────────────────────────────────────────────

_SEARCH_RESULTS = [
    {"title": "Python docs", "href": "https://python.org", "body": "Official Python documentation."}
]


def test_web_search_returns_formatted_results():
    with patch("tools.DDGS") as mock_cls:
        mock_cls.return_value.__enter__.return_value.text.return_value = _SEARCH_RESULTS
        result = web_search("python")
    assert "Python docs" in result
    assert "https://python.org" in result
    assert "Official Python documentation." in result


def test_web_search_result_fields_separated_by_dashes():
    with patch("tools.DDGS") as mock_cls:
        mock_cls.return_value.__enter__.return_value.text.return_value = _SEARCH_RESULTS
        result = web_search("python")
    assert "---" in result


def test_web_search_no_results():
    with patch("tools.DDGS") as mock_cls:
        mock_cls.return_value.__enter__.return_value.text.return_value = []
        result = web_search("xyzzy404notfound")
    assert result == "No results found."


def test_web_search_respects_max_results():
    with patch("tools.DDGS") as mock_cls:
        mock_text = mock_cls.return_value.__enter__.return_value.text
        mock_text.return_value = _SEARCH_RESULTS
        web_search("python", max_results=3)
    mock_text.assert_called_once_with("python", max_results=3)


def test_web_search_error():
    with patch("tools.DDGS", side_effect=Exception("network error")):
        result = web_search("test")
    assert "Search error" in result


# ── get_weather ───────────────────────────────────────────────────────────────

_WEATHER_JSON = {
    "current_condition": [{
        "weatherDesc": [{"value": "Sunny"}],
        "temp_C": "22", "temp_F": "72", "FeelsLikeC": "21",
        "humidity": "60", "windspeedKmph": "15",
    }],
    "nearest_area": [{
        "areaName": [{"value": "New York"}],
        "country": [{"value": "United States"}],
    }],
    "weather": [{"maxtempC": "25", "mintempC": "18"}],
}


def test_get_weather_includes_city_and_condition():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _WEATHER_JSON
    with patch("tools.requests.get", return_value=mock_resp):
        result = get_weather("New York")
    assert "New York" in result
    assert "Sunny" in result


def test_get_weather_includes_temperature():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _WEATHER_JSON
    with patch("tools.requests.get", return_value=mock_resp):
        result = get_weather("New York")
    assert "22°C" in result
    assert "72°F" in result


def test_get_weather_encodes_spaces_in_url():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _WEATHER_JSON
    with patch("tools.requests.get", return_value=mock_resp) as mock_get:
        get_weather("New York")
    called_url = mock_get.call_args[0][0]
    assert " " not in called_url
    assert "New+York" in called_url


def test_get_weather_error():
    with patch("tools.requests.get", side_effect=Exception("timeout")):
        result = get_weather("New York")
    assert "Weather error" in result
