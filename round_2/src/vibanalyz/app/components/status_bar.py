"""Status bar component wrapper."""

from rich.text import Text
from textual.widgets import Static


class StatusBar:
    """Wrapper for Static widget used as status bar."""

    def __init__(self, widget: Static):
        """Initialize with a Static widget."""
        self.widget = widget
        self._previous = ""
        self._current = ""
        self._next = ""

    def update(self, message: str) -> None:
        """Update the status message (backward compatibility)."""
        # Shift current to previous, set message as current
        self._previous = self._current
        self._current = message
        self._format_and_update()

    def update_status(
        self, previous: str, current: str, next: str, separator: str = "*"
    ) -> None:
        """Update the three-part status display."""
        self._previous = previous
        self._current = current
        self._next = next
        self._format_and_update(separator)

    def _format_and_update(self, separator: str = "*") -> None:
        """Format and update the status display with three parts."""
        try:
            # Get widget width - try to get actual size
            width = None
            try:
                if hasattr(self.widget, "size") and self.widget.size:
                    if hasattr(self.widget.size, "width") and self.widget.size.width:
                        width = self.widget.size.width
            except Exception:
                pass
            
            # If width not available, use a reasonable default
            if width is None or width < 40:
                width = 120  # Reasonable default for terminal width

            # Calculate space allocation
            # Reserve space for separators (2 separators with padding: " * ")
            separator_str = f" {separator} "
            separator_len = len(separator_str) * 2
            # Account for widget padding
            available_width = max(30, width - separator_len - 4)

            # Allocate space: ~30% previous, ~40% current, ~30% next
            prev_width = max(10, int(available_width * 0.3))
            current_width = max(12, int(available_width * 0.4))
            next_width = max(10, available_width - prev_width - current_width)

            # Format each part
            # Left-justify previous
            prev_text = self._previous[:prev_width].ljust(prev_width)
            # Center current
            current_text = self._current[:current_width].center(current_width)
            # Right-justify next
            next_text = self._next[:next_width].rjust(next_width)

            # Combine with separators
            formatted = f"{prev_text}{separator_str}{current_text}{separator_str}{next_text}"

            # Update the widget - Textual Static widgets use update() method
            # The update method should handle the refresh automatically
            self.widget.update(formatted)
            # Explicitly refresh to ensure the display updates immediately
            try:
                self.widget.refresh()
            except Exception:
                pass  # Refresh might not be available or needed
        except Exception:
            # Fallback: simple format if formatting fails
            separator_str = f" {separator} "
            formatted = f"{self._previous}{separator_str}{self._current}{separator_str}{self._next}"
            self.widget.update(formatted)
            if hasattr(self.widget, "refresh"):
                self.widget.refresh()

