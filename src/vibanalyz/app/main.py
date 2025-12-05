"""Main Textual TUI application."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Static


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
        # Set initial welcome message in RichLog
        log = self.query_one("#results-log", RichLog)
        log.write("Welcome to Vibanalyz MVP 1.0")
        
        if self.package_name:
            # Auto-run audit if package name was provided
            self.set_timer(0.1, self._auto_run)

    def _auto_run(self) -> None:
        """Auto-run audit with the provided package name."""
        input_widget = self.query_one("#package-input", Input)
        input_widget.value = self.package_name
        self.run_audit(self.package_name)

    def _trigger_audit(self) -> None:
        """Helper method to trigger audit from button or Enter key."""
        input_widget = self.query_one("#package-input", Input)
        package_name = input_widget.value.strip()
        if package_name:
            # Log user selection
            log = self.query_one("#results-log", RichLog)
            log.write(f"User selected: {package_name}")
            
            # Update status when audit starts
            status = self.query_one("#status-bar", Static)
            status.update("Running audit...")
            self.run_audit(package_name)
        else:
            log = self.query_one("#results-log", RichLog)
            log.write("Please enter a package name.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "audit-button":
            self._trigger_audit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key press in input field."""
        if event.input.id == "package-input":
            self._trigger_audit()

    async def run_audit(self, name: str) -> None:
        """Run the audit pipeline for the given package name."""
        from vibanalyz.domain.models import Context
        from vibanalyz.services.pipeline import run_pipeline

        log = self.query_one("#results-log", RichLog)
        # Don't clear - keep the "User selected" line
        log.write(f"Starting audit for package: {name}")
        log.write("Running pipeline...")

        try:
            # Create context
            ctx = Context(package_name=name)

            # Run pipeline
            result = run_pipeline(ctx)

            # Log results
            log.write(f"\nAudit complete!")
            log.write(f"Risk Score: {result.score}")
            log.write(f"Findings: {len(result.ctx.findings)}")

            if result.ctx.findings:
                log.write("\nFindings:")
                for finding in result.ctx.findings:
                    log.write(
                        f"  [{finding.severity.upper()}] {finding.source}: {finding.message}"
                    )

            if result.pdf_path:
                log.write(f"\nPDF report saved to: {result.pdf_path}")

            # Update status when done
            status = self.query_one("#status-bar", Static)
            status.update("Audit complete. Waiting for user input.")

        except Exception as e:
            log.write(f"\nError during audit: {e}")
            import traceback
            log.write(traceback.format_exc())
            status = self.query_one("#status-bar", Static)
            status.update("Error occurred. Waiting for user input.")

