from rich.text import Text
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Static, Markdown, Button, ListView, ListItem
from textual.containers import Container, Horizontal

from helpers import copy_to_clipboard, get_model_info


class ThinkingIndicator(Widget):
    FRAMES_RIGHT = ["ᗧ", "●"]
    FRAMES_LEFT  = ["ᗤ", "●"]
    DOT = "·"
    NUM_DOTS = 12

    def __init__(self) -> None:
        super().__init__(classes="thinking-card")
        self._pos = 0
        self._direction = 1   # +1 = right, -1 = left
        self._frame = 0       # 0 = open, 1 = closed

    def on_mount(self) -> None:
        self.set_interval(0.18, self._tick)

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % 2
        if self._frame == 0:
            self._pos += self._direction
            if self._pos >= self.NUM_DOTS - 1:
                self._direction = -1
            elif self._pos <= 0:
                self._direction = 1
        self.refresh()

    def render(self) -> Text:
        if self._direction == 1:
            pacman = self.FRAMES_RIGHT[self._frame]
            row = "  " * self._pos + pacman + (" " + self.DOT) * (self.NUM_DOTS - self._pos - 1)
        else:
            pacman = self.FRAMES_LEFT[self._frame]
            row = (self.DOT + " ") * self._pos + pacman + "  " * (self.NUM_DOTS - self._pos - 1)
        return Text("Thinking.. " + row)


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


class ModelInfoBar(Horizontal):
    def __init__(self, model: str) -> None:
        super().__init__(id="model-info-bar")
        self.border_title = model
        self._left, self._right = self._make_columns(model)

    def compose(self):
        yield Static(self._left, classes="info-col", markup=True)
        yield Static(self._right, classes="info-col", markup=True)

    def set_model(self, model: str) -> None:
        self.border_title = model
        self._left, self._right = self._make_columns(model)
        for col, text in zip(self.query(Static), (self._left, self._right)):
            col.update(text)

    @staticmethod
    def _make_columns(model: str) -> tuple[str, str]:
        info = get_model_info(model)
        k = "bold orange1"
        caps = "  ·  ".join(info["capabilities"]) if info["capabilities"] else "N/A"
        left = (
            f"[{k}]🏗  Arch:[/{k}] {info['arch']}\n\n"
            f"[{k}]⚖  Params:[/{k}] {info['params']}\n\n"
            f"[{k}]📐 Context:[/{k}] {info['context']}"
        )
        right = (
            f"[{k}]🔗 Embed:[/{k}] {info['embedding']}\n\n"
            f"[{k}]🗜  Quant:[/{k}] {info['quant']}\n\n"
            f"[{k}]✨ Caps:[/{k}] {caps}"
        )
        return left, right


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



class CopyButton(Static):
    def __init__(self) -> None:
        super().__init__("⧉", classes="copy-btn")
        self.tooltip = "Copy"

    def on_click(self) -> None:
        if self.parent is None:
            return
        card = self.parent.parent
        if isinstance(card, AgentCard):
            copy_to_clipboard(card._text)
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


class MicButton(Button):
    class Toggled(Message):
        def __init__(self, recording: bool) -> None:
            super().__init__()
            self.recording = recording

    def __init__(self) -> None:
        super().__init__("🎙", id="mic-btn")
        self._recording = False

    def _toggle(self) -> None:
        self._recording = not self._recording
        if self._recording:
            self.label = "⏹"
            self.add_class("recording")
        else:
            self.label = "🎙"
            self.remove_class("recording")
        self.post_message(self.Toggled(self._recording))

    def on_click(self) -> None:
        self._toggle()
