import subprocess
import ollama
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Static, Markdown, Button
from textual.containers import VerticalScroll, Vertical, Container, Horizontal
from textual import work
from agent import ReactAgent


def copy_to_clipboard(text: str) -> None:
    subprocess.run("pbcopy", input=text.encode(), check=True)


def check_ollama(model: str) -> tuple[bool, str, str]:
    """Returns (ok, title, error_message). Checks server reachability and model availability."""
    try:
        available = [m.model for m in ollama.list().models]
    except Exception:
        return False, "Backend Server Missing", (
            "Could not connect to the Ollama server.\n\n"
            "Make sure Ollama is installed and running:\n"
            "    ollama serve"
        )
    if not any(m == model or m.startswith(model.split(":")[0]) for m in available):
        return False, "Model Not Available", (
            f"Model '{model}' is not pulled on this machine.\n\n"
            f"Pull it first with:\n"
            f"    ollama pull {model}"
        )
    return True, "", ""


def get_model_info(model: str) -> dict:
    try:
        resp = ollama.show(model)
        details = resp.details
        mi = resp.modelinfo or {}
        arch = getattr(details, "family", "") or mi.get("general.architecture", "N/A")

        raw_count = mi.get("general.parameter_count", 0)
        if raw_count and isinstance(raw_count, int):
            if raw_count >= 1_000_000_000_000:
                params = f"{raw_count / 1e12:.1f}T".rstrip("0").rstrip(".")
            elif raw_count >= 1_000_000_000:
                params = f"{raw_count / 1e9:.0f}B"
            else:
                params = str(raw_count)
        else:
            params = getattr(details, "parameter_size", None) or "N/A"

        ctx_raw = mi.get(f"{arch}.context_length", 0)
        context = f"{ctx_raw // 1024}K" if ctx_raw >= 1024 else (str(ctx_raw) if ctx_raw else "N/A")

        emb_raw = mi.get(f"{arch}.embedding_length", 0)
        embedding = str(emb_raw) if emb_raw else "N/A"

        quant = getattr(details, "quantization_level", None) or "N/A"
        caps = [str(c) for c in (resp.capabilities or [])]

        return dict(arch=arch, params=params, context=context, embedding=embedding,
                    quant=quant, capabilities=caps)
    except Exception:
        return dict(arch="N/A", params="N/A", context="N/A", embedding="N/A",
                    quant="N/A", capabilities=[])


class ModelInfoBar(Static):
    def __init__(self, model: str) -> None:
        info = get_model_info(model)
        k = "bold orange1"
        caps = "  ·  ".join(info["capabilities"]) if info["capabilities"] else "N/A"
        content = (
            f"[{k}]Arch:[/{k}] {info['arch']}    "
            f"[{k}]Params:[/{k}] {info['params']}    "
            f"[{k}]Context:[/{k}] {info['context']}    "
            f"[{k}]Embed:[/{k}] {info['embedding']}    "
            f"[{k}]Quant:[/{k}] {info['quant']}\n"
            f"[{k}]Capabilities:[/{k}] {caps}"
        )
        super().__init__(content, id="model-info-bar", markup=True)
        self.border_title = model


class OllamaErrorModal(ModalScreen):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="error-dialog"):
            yield Static(self._message, id="error-msg")
            with Horizontal(id="ok-row"):
                yield Button("OK", id="ok-btn", variant="warning")

    def on_mount(self) -> None:
        self.query_one("#error-dialog").border_title = self._title

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.exit()


class ThinkingIndicator(Static):
    FRAMES = ["⏳", "⌛"]

    def __init__(self) -> None:
        super().__init__(self.FRAMES[0] + " Thinking...", classes="thinking-card", markup=True)
        self._frame = 0

    def on_mount(self) -> None:
        self.set_interval(0.45, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(self.FRAMES)
        self.update(f"{self.FRAMES[self._frame]} Thinking...")


class CopyButton(Static):
    def __init__(self) -> None:
        super().__init__("⧉", classes="copy-btn")
        self.tooltip = "Copy"

    def on_click(self) -> None:
        if isinstance(self.parent, AgentCard):
            copy_to_clipboard(self.parent._text)
            self.app.notify("Copied to clipboard", timeout=2)


class AgentCard(Container):
    """Focusable card that renders LLM output as Markdown and supports copy."""

    can_focus = True

    BINDINGS = [("c", "copy_content", "Copy response")]

    def __init__(self, text: str) -> None:
        super().__init__(classes="agent-card")
        self._text = text

    def compose(self) -> ComposeResult:
        yield Markdown(self._text)
        with Horizontal(classes="copy-btn-row"):
            yield CopyButton()

    def action_copy_content(self) -> None:
        copy_to_clipboard(self._text)
        self.notify("Copied to clipboard", timeout=2)


LOGO = """
 █████╗  ██████╗ ██████╗ ██████╗ ███████╗
██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝
███████║██║     ██║   ██║██║  ██║█████╗
██╔══██║██║     ██║   ██║██║  ██║██╔══╝
██║  ██║╚██████╗╚██████╔╝██████╔╝███████╗
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
""".strip()


class AcodeApp(App):
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+r", "reset", "Reset conversation"),
    ]

    def __init__(self, model: str = "minimax-m2.5:cloud"):
        super().__init__()
        self.agent = ReactAgent(model=model)
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield ModelInfoBar(self.agent.model)
        yield VerticalScroll(id="output-scroll")
        with Vertical(id="input-container"):
            yield Input(placeholder="Type your message and press Enter...", id="user-input")
        yield Footer()

    def on_mount(self) -> None:
        ok, title, error = check_ollama(self.agent.model)
        if not ok:
            self.push_screen(OllamaErrorModal(title, error))
            return
        self._add_card(
            "[bold cyan]Welcome![/bold cyan] Type a message to start. "
            "Click any agent response and press [bold]c[/bold] to copy it.",
            css_class="welcome-card",
        )
        self.query_one("#user-input", Input).focus()

    # ── card helpers ──────────────────────────────────────────────────────────

    def _add_card(self, text: str, css_class: str, card_id: str | None = None) -> None:
        scroll = self.query_one("#output-scroll", VerticalScroll)
        card = Static(text, classes=css_class, markup=True)
        if card_id:
            card.id = card_id
        scroll.mount(card)
        scroll.scroll_end(animate=False)

    def _add_agent_card(self, text: str) -> None:
        scroll = self.query_one("#output-scroll", VerticalScroll)
        card = AgentCard(text)
        scroll.mount(card)
        scroll.scroll_end(animate=False)

    def _add_thinking(self) -> None:
        scroll = self.query_one("#output-scroll", VerticalScroll)
        indicator = ThinkingIndicator()
        indicator.id = "thinking-indicator"
        scroll.mount(indicator)
        scroll.scroll_end(animate=False)

    def _remove_thinking(self) -> None:
        try:
            self.query_one("#thinking-indicator").remove()
        except Exception:
            pass

    # ── input handling ────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text or self._busy:
            return
        event.input.clear()
        self._process_input(user_text)

    @work(thread=True)
    def _process_input(self, user_text: str) -> None:
        self._busy = True
        self.call_from_thread(
            self._add_card,
            f"[bold green]You[/bold green]\n{user_text}",
            css_class="user-card",
        )

        def on_event(kind: str, text: str) -> None:
            if kind == "thinking":
                self.call_from_thread(self._add_thinking)
            elif kind == "tool_call":
                self.call_from_thread(self._remove_thinking)
                self.call_from_thread(
                    self._add_card,
                    f"[bold yellow]⚙ Tool Call[/bold yellow]\n{text}",
                    css_class="tool-card",
                )
            elif kind == "tool_result":
                self.call_from_thread(
                    self._add_card,
                    f"[dim]↳ Result[/dim]\n{text}",
                    css_class="tool-result-card",
                )
            elif kind == "llm":
                self.call_from_thread(self._remove_thinking)
                self.call_from_thread(self._add_agent_card, text)
            elif kind == "error":
                self.call_from_thread(self._remove_thinking)
                self.call_from_thread(
                    self._add_card,
                    f"[bold red]Error[/bold red]\n{text}",
                    css_class="error-card",
                )

        try:
            self.agent.run(user_text, on_event=on_event)
        except Exception as e:
            self.call_from_thread(self._remove_thinking)
            self.call_from_thread(
                self._add_card,
                f"[bold red]Agent error[/bold red]\n{e}",
                css_class="error-card",
            )
        finally:
            self._busy = False
            self.call_from_thread(self.query_one("#user-input", Input).focus)

    # ── actions ───────────────────────────────────────────────────────────────

    def action_reset(self) -> None:
        self.agent.reset()
        scroll = self.query_one("#output-scroll", VerticalScroll)
        scroll.remove_children()
        self._add_card("[bold cyan]Conversation reset.[/bold cyan]", css_class="welcome-card")

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "minimax-m2.5:cloud"
    AcodeApp(model=model).run()
