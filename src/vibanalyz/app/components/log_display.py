"""Log display component wrapper."""

from textual.widgets import RichLog


class LogDisplay:
    """Wrapper for RichLog widget with helper methods."""

    def __init__(self, widget: RichLog):
        """Initialize with a RichLog widget."""
        self.widget = widget
        # Keep our own buffer of log messages for easy text extraction
        self._log_buffer: list[str] = []

    def write(self, message: str) -> None:
        """Write a message to the log."""
        self.widget.write(message)
        # Also store in our buffer
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

    def write_section(self, title: str, lines: list[str]) -> None:
        """Write a formatted section with title and lines."""
        self.write(f"\n{'=' * 50}")
        self.write(title)
        self.write("=" * 50)
        for line in lines:
            self.write(line)
        self.write("=" * 50)

