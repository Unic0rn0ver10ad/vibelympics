"""Log display component wrapper."""

from typing import Literal

from rich.text import Text
from textual.widgets import RichLog


class LogDisplay:
    """Wrapper for RichLog widget with helper methods."""

    def __init__(self, widget: RichLog):
        """Initialize with a RichLog widget."""
        self.widget = widget
        # Keep our own buffer of log messages for easy text extraction
        self._log_buffer: list[str] = []
        # Track current mode to control coloring (action vs task)
        self._mode: Literal["action", "task"] = "action"

    def set_mode(self, mode: Literal["action", "task"]) -> None:
        """Set the current log mode to control coloring."""
        self._mode = mode

    def _style_for_mode(self) -> str:
        """Return the Rich style name for the current mode."""
        return "white" if self._mode == "action" else "blue"

    def write(self, message: str) -> None:
        """Write a message to the log with the current style."""
        styled = Text(message, style=self._style_for_mode())
        self.widget.write(styled)
        # Also store plain text in our buffer
        self._log_buffer.append(message)

    def clear(self) -> None:
        """Clear the log."""
        self.widget.clear()
        # Also clear our buffer
        self._log_buffer.clear()

    def get_text(self) -> str:
        """Return the entire log contents as plain text."""
        # Use our internal buffer which tracks all messages
        if self._log_buffer:
            return "\n".join(self._log_buffer)
        return ""

    def write_task_section(self, title: str, *, leading_blank: bool = True) -> None:
        """Write a task section header with separators and spacing."""
        if leading_blank:
            self.write("")  # Blank line before
        self.write("=" * 50)
        self.write(title)
        self.write("=" * 50)

    def write_section(self, title: str, lines: list[str]) -> None:
        """Write a formatted section with title and lines."""
        self.write("")  # Blank line before
        self.write("=" * 50)
        self.write(title)
        self.write("=" * 50)
        for line in lines:
            self.write(line)
        self.write("=" * 50)

