"""Action handler for copying log to clipboard."""

from textual.app import App

from vibanalyz.app.components.log_display import LogDisplay


class CopyLogAction:
    """Handles copying log contents to clipboard."""

    def __init__(self, log_display: LogDisplay, app: App):
        """Initialize with log display component and app for clipboard access."""
        self.log_display = log_display
        self.app = app

    def execute(self) -> None:
        """Copy log text to clipboard and provide feedback."""
        self.log_display.set_mode("action")
        text = self.log_display.get_text()
        if text:
            try:
                self.app.copy_to_clipboard(text)
                self.log_display.write("[log] Copied log to clipboard.")
            except Exception as e:
                self.log_display.write(f"[log] Failed to copy log: {e}")
        else:
            self.log_display.write("[log] Nothing to copy.")

