from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Footer, Input, Static
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual import work

from agent import ReactAgent
from helpers import check_ollama, list_models
from widgets import AgentCard, CommandHints, ModelInfoBar, ModelSelectModal, OllamaErrorModal, ThinkingIndicator

SLASH_COMMANDS: dict[str, str] = {
    "/model": "Switch the active model",
}


LOGO = (Path(__file__).parent / "logo.txt").read_text().strip()


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
        with Horizontal(id="header"):
            yield Static(LOGO, id="logo")
            yield ModelInfoBar(self.agent.model)
        yield VerticalScroll(id="output-scroll")
        with Vertical(id="input-container"):
            yield CommandHints(id="cmd-hints", markup=True)
            yield Input(placeholder="Type a message or /command...", id="user-input")
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

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        hints = self.query_one(CommandHints)
        if value.startswith("/"):
            matches = [(cmd, desc) for cmd, desc in SLASH_COMMANDS.items()
                       if cmd.startswith(value)]
            hints.show(matches)
        else:
            hints.hide()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text or self._busy:
            return
        event.input.clear()
        self.query_one(CommandHints).hide()
        if user_text == "/model":
            self._show_model_selector()
            return
        self._process_input(user_text)

    def _show_model_selector(self) -> None:
        models = list_models()
        if not models:
            self.notify("No models found — is Ollama running?", severity="error")
            return

        def on_selected(model: str | None) -> None:
            if not model:
                return
            self.agent.model = model
            self.query_one(ModelInfoBar).set_model(model)
            self.notify(f"Switched to {model}", timeout=3)

        self.push_screen(ModelSelectModal(models), on_selected)

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
