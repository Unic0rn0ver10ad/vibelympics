"""Main Textual TUI application."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Footer, Header, Input, RichLog


class AuditApp(App):
    """Main audit application TUI."""

    CSS = """
    Container {
        padding: 1;
    }
    
    Horizontal {
        height: 3;
        align: center middle;
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
            Horizontal(
                Input(placeholder="Enter package name (e.g., requests)", id="package-input"),
                Button("Run audit", id="audit-button", variant="primary"),
            ),
            RichLog(id="results-log"),
        )
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        if self.package_name:
            # Auto-run audit if package name was provided
            self.set_timer(0.1, self._auto_run)

    def _auto_run(self) -> None:
        """Auto-run audit with the provided package name."""
        input_widget = self.query_one("#package-input", Input)
        input_widget.value = self.package_name
        self.run_audit(self.package_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "audit-button":
            input_widget = self.query_one("#package-input", Input)
            package_name = input_widget.value.strip()
            if package_name:
                self.run_audit(package_name)
            else:
                log = self.query_one("#results-log", RichLog)
                log.write("Please enter a package name.")

    async def run_audit(self, name: str) -> None:
        """Run the audit pipeline for the given package name."""
        from vibanalyz.domain.models import Context
        from vibanalyz.services.pipeline import run_pipeline

        log = self.query_one("#results-log", TextLog)
        log.clear()
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

        except Exception as e:
            log.write(f"\nError during audit: {e}")
            import traceback
            log.write(traceback.format_exc())

