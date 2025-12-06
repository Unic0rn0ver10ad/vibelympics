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
        height: auto;
        align: center middle;
        margin-top: 1;
        margin-bottom: 0;
    }
    
    Horizontal#input-row {
        margin-bottom: 1;
    }
    
    Horizontal#action-row {
        margin-top: 0;
    }
    
    Label {
        margin-bottom: 1;
        padding-left: 0;
    }
    
    Input {
        width: 30;
        margin-right: 1;
    }
    
    Button {
        width: 12;
    }
    
    Button.repo-button {
        width: 8;
        margin-right: 1;
    }
    
    Button.repo-button.selected {
        background: $accent;
        text-style: bold;
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
    
    Label.repo-label {
        width: 6;
        margin-right: 1;
        text-align: right;
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
        self.selected_repo: str = "pypi"  # Default to PyPI

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Container(
            Vertical(
                Label("Enter the name of a package to check here"),
                Horizontal(
                    Label("Repo:", classes="repo-label"),
                    Button("PyPI", id="repo-pypi-button", classes="repo-button selected"),
                    Button("NPM", id="repo-npm-button", classes="repo-button"),
                    id="input-row",
                ),
                Horizontal(
                    Input(placeholder="requests", id="package-input", value=self.package_name or ""),
                    Button("Run audit", id="audit-button", variant="primary"),
                    Button("Start over", id="start-over-button"),
                    id="action-row",
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
        else:
            # Focus the input field by default so it's ready for typing
            self.set_timer(0.1, self._focus_input)

    def _focus_input(self) -> None:
        """Focus the input field."""
        try:
            self.query_one("#package-input", Input).focus()
        except Exception:
            pass

    async def _auto_run(self) -> None:
        """Auto-run audit with the provided package name."""
        if self.package_name:
            self.components["input"].set_value(self.package_name)
            package_name, version = self.components["input"].get_package_info()
            repo_source = self._get_repo_source()
            await self._handle_audit(package_name, version, repo_source)

    def _get_repo_source(self) -> str:
        """Get the currently selected repo source."""
        return self.selected_repo

    def _update_repo_selection(self, repo: str) -> None:
        """Update the selected repo and refresh button styling."""
        self.selected_repo = repo
        
        # Update button styling to show which is selected
        pypi_button = self.query_one("#repo-pypi-button", Button)
        npm_button = self.query_one("#repo-npm-button", Button)
        
        if repo == "pypi":
            pypi_button.add_class("selected")
            npm_button.remove_class("selected")
        else:
            npm_button.add_class("selected")
            pypi_button.remove_class("selected")

    async def _handle_audit(
        self, package_name: str, version: str | None = None, repo_source: str | None = None
    ) -> None:
        """Handle audit action."""
        if not package_name:
            self.components["log"].write("Please enter a valid package name.")
            return

        # Get repo source if not provided
        if repo_source is None:
            repo_source = self._get_repo_source()

        # Log user selection
        if version:
            self.components["log"].write(
                f"User selected: {package_name}=={version} (source: {repo_source})"
            )
        else:
            self.components["log"].write(f"User selected: {package_name} (source: {repo_source})")

        try:
            # Execute audit action
            result = await self.actions["audit"].execute(package_name, version, repo_source)

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

    def _start_over(self) -> None:
        """Reset the UI to initial state for a new audit."""
        # Reset repo selection to default (PyPI)
        self._update_repo_selection("pypi")
        
        # Clear the input text box
        self.components["input"].clear()
        
        # Reset status bar to default message
        self.components["status"].update("Waiting for user input.")
        
        # Clear the log display
        self.components["log"].clear()
        
        # Reset app state
        self.state.reset()
        
        # Write welcome message again
        self.components["log"].write("Welcome to Vibanalyz MVP 1.0")
        
        # Focus the input field
        self._focus_input()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "audit-button":
            package_name, version = self.components["input"].get_package_info()
            repo_source = self._get_repo_source()
            await self._handle_audit(package_name, version, repo_source)
        elif button_id == "start-over-button":
            self._start_over()
        elif button_id == "repo-pypi-button":
            self._update_repo_selection("pypi")
            self.components["log"].write("Repo source changed to: PyPI")
        elif button_id == "repo-npm-button":
            self._update_repo_selection("npm")
            self.components["log"].write("Repo source changed to: NPM")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key press in input field."""
        if event.input.id == "package-input":
            package_name, version = self.components["input"].get_package_info()
            repo_source = self._get_repo_source()
            await self._handle_audit(package_name, version, repo_source)

