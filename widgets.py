from textual.screen import ModalScreen
from textual.widgets import Static, Markdown, Button, ListView, ListItem
from textual.containers import Container, Horizontal

from helpers import copy_to_clipboard, get_model_info


class CommandHints(Static):
    """Hint strip shown above the input when the user types a slash command."""

    def show(self, commands: list[tuple[str, str]]) -> None:
        if not commands:
            self.display = False
            return
        parts = "    ".join(
            f"[bold cyan]{cmd}[/bold cyan] [dim]{desc}[/dim]"
            for cmd, desc in commands
        )
        self.update(parts)
        self.display = True

    def hide(self) -> None:
        self.display = False


class ModelInfoBar(Static):
    def __init__(self, model: str) -> None:
        super().__init__(self._make_content(model), id="model-info-bar", markup=True)
        self.border_title = model

    def set_model(self, model: str) -> None:
        self.update(self._make_content(model))
        self.border_title = model

    @staticmethod
    def _make_content(model: str) -> str:
        info = get_model_info(model)
        k = "bold orange1"
        caps = "  ·  ".join(info["capabilities"]) if info["capabilities"] else "N/A"
        return (
            f"[{k}]Arch:[/{k}] {info['arch']}    "
            f"[{k}]Params:[/{k}] {info['params']}    "
            f"[{k}]Context:[/{k}] {info['context']}    "
            f"[{k}]Embed:[/{k}] {info['embedding']}    "
            f"[{k}]Quant:[/{k}] {info['quant']}\n"
            f"[{k}]Capabilities:[/{k}] {caps}"
        )


class ModelSelectModal(ModalScreen):
    def __init__(self, models: list[str]) -> None:
        super().__init__()
        self._models = models

    def compose(self):
        with Container(id="model-select-dialog"):
            yield ListView(
                *[ListItem(Static(m), name=m) for m in self._models],
                id="model-list",
            )

    def on_mount(self) -> None:
        self.query_one("#model-select-dialog").border_title = "Switch Model"
        self.query_one(ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.name)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class OllamaErrorModal(ModalScreen):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self):
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

    def compose(self):
        yield Markdown(self._text)
        with Horizontal(classes="copy-btn-row"):
            yield CopyButton()

    def action_copy_content(self) -> None:
        copy_to_clipboard(self._text)
        self.notify("Copied to clipboard", timeout=2)
