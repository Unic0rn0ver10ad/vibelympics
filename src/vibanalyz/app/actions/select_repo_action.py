"""Action handler for repo source selection."""

from vibanalyz.app.components.log_display import LogDisplay


class SelectRepoAction:
    """Handles repo source selection changes."""

    def __init__(self, log_display: LogDisplay):
        """Initialize with log display component."""
        self.log_display = log_display

    def execute(self, repo_source: str) -> None:
        """
        Log repo source change.
        
        Args:
            repo_source: The selected repo source (e.g., "pypi", "npm")
        """
        self.log_display.set_mode("action")
        repo_display_name = "PyPI" if repo_source == "pypi" else "NPM"
        self.log_display.write(f"Repo source changed to: {repo_display_name}")

