"""Animated progress tracker widget for pipeline steps."""
from __future__ import annotations

from typing import Iterable

from textual import events
from textual.reactive import reactive
from textual.widget import Widget
from rich.console import Group, RenderableType
from rich.text import Text


class ProgressTracker(Widget):
    """Displays last/current/next actions plus detailed status with animation."""

    DEFAULT_CSS = """
    ProgressTracker {
        height: 3;
        border: solid $primary;
        padding: 0 1;
    }

    ProgressTracker.-muted {
        color: $text-muted;
    }
    """

    top_transition: float = reactive(1.0)
    detail_transition: float = reactive(1.0)
    spinner_index: int = reactive(0)

    def __init__(self, id: str | None = None, **kwargs) -> None:
        super().__init__(id=id, **kwargs)
        self._task_names: list[str] = []
        self._prev_top_line = "Waiting to start"
        self._target_top_line = "Waiting to start"
        self._prev_detail_line = "Ready."
        self._target_detail_line = "Ready."
        self._detail_mode: str = "spinner"
        self._progress_fraction: float = 0.0
        self._spinner_frames: list[str] = [
            "⠋",
            "⠙",
            "⠹",
            "⠸",
            "⠼",
            "⠴",
            "⠦",
            "⠧",
            "⠇",
            "⠏",
        ]

    def on_mount(self) -> None:
        """Start spinner refresh timer."""
        self.set_interval(0.1, self._advance_spinner)

    def _advance_spinner(self) -> None:
        """Advance spinner animation frame."""
        if self._detail_mode == "spinner":
            self.spinner_index = (self.spinner_index + 1) % len(self._spinner_frames)
        else:
            # Avoid churn when not spinning
            return
        self.refresh()

    def set_chain(self, task_names: Iterable[str]) -> None:
        """Set the full task chain for positioning labels."""
        self._task_names = list(task_names)
        if self._task_names:
            self._set_top_line(self._format_top_line(-1, 0))
        else:
            self._set_top_line("Waiting to start")
        self._set_detail_line("Preparing to run pipeline", mode="spinner")

    def start_task(self, index: int, status: str) -> None:
        """Mark a task as active and animate the top line."""
        self._set_top_line(self._format_top_line(index - 1, index))
        self._set_detail_line(status, mode="spinner")

    def update_detail(self, detail: str, *, progress: float | None = None) -> None:
        """Update the detail line with optional bounded progress."""
        if progress is not None:
            self._progress_fraction = max(0.0, min(1.0, progress))
            mode = "progress"
        else:
            mode = "spinner"
        self._set_detail_line(detail, mode=mode, animate=False)

    def finish_task(self, index: int, detail: str | None = None) -> None:
        """Indicate a task finished and prepare for the next one."""
        message = detail or "Task complete"
        self._set_detail_line(message, mode="progress")
        self._progress_fraction = 1.0
        next_index = index + 1
        if next_index < len(self._task_names):
            self._set_top_line(self._format_top_line(index, next_index))
        else:
            self._set_top_line(self._format_top_line(index, None))

    def reset(self) -> None:
        """Reset to initial waiting state."""
        self._task_names = []
        self._progress_fraction = 0.0
        self._prev_top_line = "Waiting to start"
        self._target_top_line = "Waiting to start"
        self._prev_detail_line = "Ready."
        self._target_detail_line = "Ready."
        self._detail_mode = "spinner"
        self.top_transition = 1.0
        self.detail_transition = 1.0
        self.refresh()

    def _format_top_line(self, last_index: int | None, current_index: int | None) -> str:
        """Format top line as [last][current][next] labels."""
        segments: list[str] = []
        labels = ["", "", ""]

        if current_index is None and last_index is None:
            labels = ["", "Waiting", ""]
        else:
            if last_index is not None and 0 <= last_index < len(self._task_names):
                labels[0] = f"[1] {self._task_names[last_index]}"
            if current_index is not None and 0 <= current_index < len(self._task_names):
                labels[1] = f"[2] {self._task_names[current_index]}"
            elif current_index is None:
                labels[1] = "[2] Complete"
            next_index = (current_index or 0) + 1 if current_index is not None else None
            if next_index is not None and next_index < len(self._task_names):
                labels[2] = f"[3] {self._task_names[next_index]}"
        segments = [segment or "[—] Waiting" for segment in labels]
        return "..........".join(segments)

    def _set_top_line(self, new_line: str) -> None:
        self._prev_top_line = self._target_top_line
        self._target_top_line = new_line
        self.top_transition = 0.0
        self.animate("top_transition", 1.0, duration=0.45, easing="in_out_cubic")

    def _set_detail_line(self, new_line: str, *, mode: str, animate: bool = True) -> None:
        self._detail_mode = mode
        self._prev_detail_line = self._target_detail_line
        self._target_detail_line = new_line
        if animate:
            self.detail_transition = 0.0
            self.animate("detail_transition", 1.0, duration=0.35, easing="in_out_cubic")
        self.refresh()

    def _compose_line(self, prev: str, target: str, progress: float, width: int) -> str:
        """Slide previous text left while new text enters from right."""
        prev_padded = prev.ljust(max(width, len(prev)))
        target_padded = target.ljust(max(width, len(target)))
        shift = min(width, int(progress * width))
        combined = (prev_padded[shift:] + " " + target_padded)[:width]
        return combined

    def _render_detail(self, base_line: str, width: int) -> Text:
        """Render detail line with spinner or progress indicator."""
        text = base_line
        if self._detail_mode == "spinner":
            frame = self._spinner_frames[self.spinner_index]
            text = f"{text} {frame}"
        else:
            bar = self._progress_bar(width=max(10, width // 3))
            text = f"{text} {bar}"
        trimmed = text[:width]
        return Text(trimmed)

    def _progress_bar(self, width: int = 20) -> str:
        """Build a simple bounded progress bar."""
        filled = int(self._progress_fraction * width)
        empty = max(0, width - filled)
        return f"[{('█' * filled) + (' ' * empty)}]"

    def render(self) -> RenderableType:
        width = max(40, self.size.width or 0)
        top_line = self._compose_line(
            self._prev_top_line, self._target_top_line, self.top_transition, width
        )
        detail_base = self._compose_line(
            self._prev_detail_line, self._target_detail_line, self.detail_transition, width
        )
        detail_line = self._render_detail(detail_base, width)
        top_text = Text(top_line)
        return Group(top_text, detail_line)

    async def on_resize(self, event: events.Resize) -> None:
        """Refresh on resize to avoid stale truncation."""
        self.refresh()
