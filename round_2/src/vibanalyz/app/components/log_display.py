"""Log display component wrapper."""

import asyncio
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
        # Track current mode to control coloring (action, task, or error)
        self._mode: Literal["action", "task", "error"] = "action"

    def set_mode(self, mode: Literal["action", "task", "error"]) -> None:
        """Set the current log mode to control coloring."""
        self._mode = mode

    def _style_for_mode(self) -> str:
        """Return the Rich style name for the current mode."""
        if self._mode == "error":
            return "bold red"
        elif self._mode == "task":
            return "blue"  # Hot pink using hex color code
        else:  # action
            return "white"

    def write(self, message: str) -> None:
        """Write a message to the log with the current style."""
        styled = Text(message, style=self._style_for_mode())
        self.widget.write(styled)
        # Also store plain text in our buffer
        self._log_buffer.append(message)
        # Note: We can't await here since this is a sync method
        # The pipeline will yield control after log writes
    
    def _write_yellow(self, message: str) -> None:
        """Write a message in yellow (for headers)."""
        styled = Text(message, style="bright_yellow")
        self.widget.write(styled)
        # Also store plain text in our buffer
        self._log_buffer.append(message)
    
    def write_error(self, message: str) -> None:
        """Write an error message in red, then restore previous mode."""
        previous_mode = self._mode
        self.set_mode("error")
        self.write(message)
        self.set_mode(previous_mode)
    
    async def write_async(self, message: str) -> None:
        """Write a message to the log and yield control to event loop."""
        self.write(message)
        # Yield control to allow UI updates
        await asyncio.sleep(0)

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
        self._write_yellow("=" * 50)
        self._write_yellow(title)
        self._write_yellow("=" * 50)

    def write_section(self, title: str, lines: list[str]) -> None:
        """Write a formatted section with title and lines."""
        self.write("")  # Blank line before
        self._write_yellow("=" * 50)
        self._write_yellow(title)
        self._write_yellow("=" * 50)
        for line in lines:
            self.write(line)
        self._write_yellow("=" * 50)
    
    def write_with_spinner(self, message: str, spinner_style: str = "dots") -> None:
        """
        Write a message with a static clock icon indicator.
        
        The clock icon indicates a long-running operation is in progress.
        When the operation completes, write a completion message using write().
        
        Args:
            message: The message text to display
            spinner_style: Unused (kept for API compatibility)
        """
        # Use clock emoji as static indicator
        clock_icon = "🕛"
        spinner_message = f"{clock_icon} {message}"
        
        # Write message with clock icon
        styled = Text(spinner_message, style=self._style_for_mode())
        self.widget.write(styled)
        # Store plain text message in buffer (without clock icon for cleaner text export)
        self._log_buffer.append(message)

