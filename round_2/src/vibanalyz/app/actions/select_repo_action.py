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
            repo_source: The selected repo source (e.g., "pypi", "npm", "rust")
        """
        self.log_display.set_mode("action")
        if repo_source == "pypi":
            repo_display_name = "PyPI"
        elif repo_source == "npm":
            repo_display_name = "NPM"
        elif repo_source == "rust":
            repo_display_name = "Rust"
        else:
            repo_display_name = repo_source
        self.log_display.write(f"Repo source changed to: {repo_display_name}")

