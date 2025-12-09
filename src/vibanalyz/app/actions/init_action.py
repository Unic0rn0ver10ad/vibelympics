"""Action handler for app initialization."""

from vibanalyz.app.components.log_display import LogDisplay


class InitAction:
    """Handles app initialization and displays welcome message."""

    def __init__(self, log_display: LogDisplay):
        """Initialize with log display component."""
        self.log_display = log_display

    def execute(self) -> None:
        """Display welcome message."""
        self.log_display.set_mode("action")
        self.log_display.write_task_section("Welcome to Vibanalyz MVP 1.0", leading_blank=False)

