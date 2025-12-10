"""Main Textual TUI application."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, RichLog

from vibanalyz.app.actions.audit_action import AuditAction
from vibanalyz.app.actions.copy_log_action import CopyLogAction
from vibanalyz.app.actions.init_action import InitAction
from vibanalyz.app.actions.select_repo_action import SelectRepoAction
from vibanalyz.app.actions.start_over_action import StartOverAction
from vibanalyz.app.components.input_section import InputSection
from vibanalyz.app.components.log_display import LogDisplay
from vibanalyz.app.state import AppState
from vibanalyz.domain.models import Context


class AuditApp(App):
    """Main audit application TUI."""

    CSS = """
    Screen {
        layout: vertical;
    }
    
    Container {
        layout: vertical;
        height: 1fr;
    }
    
    #controls {
        height: auto;
    }
    
    .control-group {
        margin-right: 2;
    }
    
    .section-label {
        text-style: bold;
        height: 1;
    }
    
    #log-label {
        text-style: bold;
        height: 1;
    }
    
    #results-log {
        height: 20;
        border: solid $primary;
    }
    
    Input {
        width: 30;
    }
    
    Button {
        width: auto;
        min-width: 10;
    }
    
    .repo-button {
        width: 8;
        margin-right: 1;
    }
    
    .repo-button.selected {
        background: $accent;
        text-style: bold;
    }
    """

    TITLE = "Vibanalyz MVP 1.0"

    def __init__(self, package_name: str | None = None):
        """Initialize the app with optional package name."""
        super().__init__()
        self.package_name = package_name
        self.state = AppState()
        self.components: dict[str, LogDisplay | InputSection] = {}
        self.actions: dict[str, object] = {}  # Actions are various types, all independent
        self.selected_repo: str = "pypi"  # Default to PyPI

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        with Container():
            # Log area (moved to top)
            yield Label("Log", id="log-label")
            yield RichLog(id="results-log")
            
            # Controls row (moved to bottom)
            with Horizontal(id="controls"):
                with Vertical(classes="control-group"):
                    yield Label("Ecosystem", classes="section-label")
                    with Horizontal():
                        yield Button("PyPI", id="repo-pypi-button", classes="repo-button selected")
                        yield Button("NPM", id="repo-npm-button", classes="repo-button")
                        yield Button("Rust", id="repo-rust-button", classes="repo-button")
                
                with Vertical(classes="control-group"):
                    yield Label("Package", classes="section-label")
                    yield Input(
                        placeholder="requests",
                        id="package-input",
                        value=self.package_name or ""
                    )
                
                with Vertical(classes="control-group"):
                    yield Label("Actions", classes="section-label")
                    with Horizontal():
                        yield Button("Run audit", id="audit-button", variant="primary")
                        yield Button("Start over", id="start-over-button")
                        yield Button("Copy log", id="copy-log-button")
        
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Set theme to flexoki
        self.theme = "flexoki"
        
        # Initialize components
        self.components["log"] = LogDisplay(self.query_one("#results-log", RichLog))
        self.components["input"] = InputSection(
            self.query_one("#package-input", Input)
        )

        # Initialize actions
        self.actions["audit"] = AuditAction()
        self.actions["init"] = InitAction(self.components["log"])
        self.actions["start_over"] = StartOverAction(self.components["log"], self.components["input"])
        self.actions["copy_log"] = CopyLogAction(self.components["log"], self)
        self.actions["select_repo"] = SelectRepoAction(self.components["log"])

        # Set initial welcome message
        self.actions["init"].execute()

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
        # Check button states to determine selected repo
        # Use try/except since query_one() doesn't have can_raise parameter
        try:
            rust_button = self.query_one("#repo-rust-button", Button)
            if "selected" in rust_button.classes:
                return "rust"
        except Exception:
            pass
        
        try:
            npm_button = self.query_one("#repo-npm-button", Button)
            if "selected" in npm_button.classes:
                return "npm"
        except Exception:
            pass
        
        # Default to PyPI (or if PyPI button is selected)
        return "pypi"

    def _update_repo_selection(self, repo: str) -> None:
        """Update the selected repo and refresh button styling."""
        self.selected_repo = repo
        
        # Update button styling to show which is selected
        pypi_button = self.query_one("#repo-pypi-button", Button)
        npm_button = self.query_one("#repo-npm-button", Button)
        rust_button = self.query_one("#repo-rust-button", Button)
        
        # Remove selected class from all buttons
        pypi_button.remove_class("selected")
        npm_button.remove_class("selected")
        rust_button.remove_class("selected")
        
        # Add selected class to the chosen button
        if repo == "pypi":
            pypi_button.add_class("selected")
        elif repo == "npm":
            npm_button.add_class("selected")
        elif repo == "rust":
            rust_button.add_class("selected")

    async def _handle_audit(
        self, package_name: str, version: str | None = None, repo_source: str | None = None
    ) -> None:
        """Handle audit action."""
        # Get repo source if not provided
        if repo_source is None:
            repo_source = self._get_repo_source()

        ctx = Context(
            package_name=package_name,
            requested_version=version,
            repo_source=repo_source,
            log_display=self.components["log"],
        )

        try:
            # Execute audit action
            result = await self.actions["audit"].execute(ctx)

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
        
        # Reset app state
        self.state.reset()
        
        # Clear UI and show welcome message (handled by action)
        self.actions["start_over"].execute()
        
        # Focus the input field
        self._focus_input()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "copy-log-button":
            self.actions["copy_log"].execute()
        elif button_id == "audit-button":
            package_name, version = self.components["input"].get_package_info()
            repo_source = self._get_repo_source()
            await self._handle_audit(package_name, version, repo_source)
        elif button_id == "start-over-button":
            self._start_over()
        elif button_id == "repo-pypi-button":
            self._update_repo_selection("pypi")
            self.actions["select_repo"].execute("pypi")
        elif button_id == "repo-npm-button":
            self._update_repo_selection("npm")
            self.actions["select_repo"].execute("npm")
        elif button_id == "repo-rust-button":
            self._update_repo_selection("rust")
            self.actions["select_repo"].execute("rust")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key press in input field."""
        if event.input.id == "package-input":
            package_name, version = self.components["input"].get_package_info()
            repo_source = self._get_repo_source()
            await self._handle_audit(package_name, version, repo_source)
