"""Action handler for starting over."""

from vibanalyz.app.components.input_section import InputSection
from vibanalyz.app.components.log_display import LogDisplay


class StartOverAction:
    """Handles start over functionality - clears UI and resets to initial state."""

    def __init__(self, log_display: LogDisplay, input_section: InputSection):
        """Initialize with log display and input section components."""
        self.log_display = log_display
        self.input_section = input_section

    def execute(self) -> None:
        """Clear log and input, display welcome message."""
        self.log_display.set_mode("action")
        self.log_display.clear()
        self.input_section.clear()
        self.log_display.write("Welcome to Vibanalyz MVP 1.0")

