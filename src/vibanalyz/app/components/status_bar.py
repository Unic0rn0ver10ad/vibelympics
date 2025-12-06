"""Status bar component wrapper."""

from textual.widgets import Static


class StatusBar:
    """Wrapper for Static widget used as status bar."""

    def __init__(self, widget: Static):
        """Initialize with a Static widget."""
        self.widget = widget

    def update(self, message: str) -> None:
        """Update the status message."""
        self.widget.update(message)

