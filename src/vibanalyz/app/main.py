"""Main Textual TUI application."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static

from vibanalyz.app.actions.audit_action import AuditAction
from vibanalyz.app.components.input_section import InputSection
from vibanalyz.app.components.log_display import LogDisplay
from vibanalyz.app.components.status_bar import StatusBar
from vibanalyz.app.state import AppState


class AuditApp(App):
    """Main audit application TUI."""

    CSS = """
    Container {
        padding: 1 1 0 1;
    }
    
    Vertical {
        padding: 1;
        margin-bottom: 0;
        height: auto;
    }
    
    Horizontal {
        height: 3;
        align: center middle;
        margin-top: 1;
        margin-bottom: 0;
    }
    
    Label {
        margin-bottom: 1;
        padding-left: 0;
    }
    
    Input {
        width: 40;
        margin-right: 1;
    }
    
    Button {
        width: 12;
    }
    
    RichLog {
        border: solid $primary;
        height: 1fr;
        margin-top: 0;
        margin-bottom: 0;
        min-height: 10;
    }
    
    Static#status-bar {
        padding: 1;
        text-align: left;
        height: 3;
        margin-top: 0;
        margin-bottom: 0;
    }
    
    Footer {
        dock: bottom;
        height: 1;
    }
    """

    TITLE = "vibanalyz – MVP stub"

    def __init__(self, package_name: str | None = None):
        """Initialize the app with optional package name."""
        super().__init__()
        self.package_name = package_name
        self.state = AppState()
        self.components: dict[str, LogDisplay | StatusBar | InputSection] = {}
        self.actions: dict[str, AuditAction] = {}

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Container(
            Vertical(
                Label("Enter the name of a PyPI module to check here"),
                Horizontal(
                    Input(placeholder="requests", id="package-input", value=self.package_name or ""),
                    Button("Run audit", id="audit-button", variant="primary"),
                ),
            ),
            RichLog(id="results-log"),
            Static("Waiting for user input.", id="status-bar"),
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Initialize components
        self.components["log"] = LogDisplay(self.query_one("#results-log", RichLog))
        self.components["status"] = StatusBar(self.query_one("#status-bar", Static))
        self.components["input"] = InputSection(
            self.query_one("#package-input", Input)
        )

        # Initialize actions
        self.actions["audit"] = AuditAction(
            self.components["log"], self.components["status"]
        )

        # Set initial welcome message
        self.components["log"].write("Welcome to Vibanalyz MVP 1.0")

        if self.package_name:
            # Auto-run audit if package name was provided
            self.set_timer(0.1, self._auto_run)

    async def _auto_run(self) -> None:
        """Auto-run audit with the provided package name."""
        if self.package_name:
            self.components["input"].set_value(self.package_name)
            package_name, version = self.components["input"].get_package_info()
            await self._handle_audit(package_name, version)

    async def _handle_audit(self, package_name: str, version: str | None = None) -> None:
        """Handle audit action."""
        if not package_name:
            self.components["log"].write("Please enter a valid package name.")
            return

        # Log user selection
        if version:
            self.components["log"].write(f"User selected: {package_name}=={version}")
        else:
            self.components["log"].write(f"User selected: {package_name}")

        try:
            # Execute audit action
            result = await self.actions["audit"].execute(package_name, version)

            # Update state
            self.state.mark_audit_complete(package_name, version, result)

            # Update UI based on state (e.g., show/hide buttons)
            self._update_ui_for_state()

        except Exception:
            # Error handling is done in AuditAction
            pass

    def _update_ui_for_state(self) -> None:
        """Update UI components based on current state."""
        # Future: Show/hide buttons, enable/disable features based on state
        # For now, this is a placeholder for future enhancements
        pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "audit-button":
            package_name, version = self.components["input"].get_package_info()
            await self._handle_audit(package_name, version)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key press in input field."""
        if event.input.id == "package-input":
            package_name, version = self.components["input"].get_package_info()
            await self._handle_audit(package_name, version)

