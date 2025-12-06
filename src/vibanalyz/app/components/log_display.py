"""Log display component wrapper."""

from textual.widgets import RichLog


class LogDisplay:
    """Wrapper for RichLog widget with helper methods."""

    def __init__(self, widget: RichLog):
        """Initialize with a RichLog widget."""
        self.widget = widget

    def write(self, message: str) -> None:
        """Write a message to the log."""
        self.widget.write(message)

    def clear(self) -> None:
        """Clear the log."""
        self.widget.clear()

    def write_section(self, title: str, lines: list[str]) -> None:
        """Write a formatted section with title and lines."""
        self.write(f"\n{'=' * 50}")
        self.write(title)
        self.write("=" * 50)
        for line in lines:
            self.write(line)
        self.write("=" * 50)

