"""Action handler for running audits."""

from vibanalyz.app.components.log_display import LogDisplay
from vibanalyz.app.components.status_bar import StatusBar
from vibanalyz.domain.models import AuditResult, Context
from vibanalyz.services.pipeline import run_pipeline


class AuditAction:
    """Handles audit execution and result display."""

    def __init__(self, log_display: LogDisplay, status_bar: StatusBar):
        """Initialize with UI components."""
        self.log = log_display
        self.status = status_bar

    async def execute(
        self, package_name: str, version: str | None = None
    ) -> AuditResult:
        """
        Execute audit and update UI.
        
        Args:
            package_name: Package name to audit
            version: Optional version string
        
        Returns:
            AuditResult from the pipeline
        
        Raises:
            Exception: If audit fails
        """
        # Update status
        self.status.update("Running audit...")
        
        # Log audit start
        version_info = f"=={version}" if version else ""
        self.log.write(f"Starting audit for package: {package_name}{version_info}")
        self.log.write("Running pipeline...")

        try:
            # Create context
            ctx = Context(package_name=package_name, requested_version=version)

            # Run pipeline
            result = run_pipeline(ctx)

            # Display PyPI metadata if available
            if result.ctx.package:
                self._display_package_info(result.ctx.package)

            # Display results
            self._display_results(result)

            # Update status when done
            self.status.update("Audit complete. Waiting for user input.")

            return result

        except Exception as e:
            self.log.write(f"\nError during audit: {e}")
            import traceback

            self.log.write(traceback.format_exc())
            self.status.update("Error occurred. Waiting for user input.")
            raise

    def _display_package_info(self, package) -> None:
        """Display package metadata information."""
        lines = []
        lines.append(f"Package: {package.name}")

        if package.version:
            lines.append(f"Version: {package.version}")

        if package.summary:
            lines.append(f"Summary: {package.summary}")

        if package.requires_dist:
            dep_count = len(package.requires_dist)
            lines.append(f"Dependencies: {dep_count} direct dependencies")

        if package.project_urls:
            # Look for repository URL
            repo_url = None
            for key, url in package.project_urls.items():
                if key.lower() in ["repository", "source", "code"]:
                    repo_url = url
                    break

            if repo_url:
                lines.append(f"Repository: {repo_url}")
            elif package.home_page:
                lines.append(f"Homepage: {package.home_page}")

        if package.author:
            author_info = package.author
            if package.author_email:
                author_info += f" ({package.author_email})"
            lines.append(f"Author: {author_info}")

        if package.license:
            lines.append(f"License: {package.license}")

        if package.release_count is not None:
            lines.append(f"Total Releases: {package.release_count}")

        self.log.write_section("Package Information", lines)

    def _display_results(self, result: AuditResult) -> None:
        """Display audit results."""
        # Log results
        self.log.write(f"\nAudit complete!")
        self.log.write(f"Risk Score: {result.score}")
        self.log.write(f"Findings: {len(result.ctx.findings)}")

        if result.ctx.findings:
            self.log.write("\nFindings:")
            for finding in result.ctx.findings:
                self.log.write(
                    f"  [{finding.severity.upper()}] {finding.source}: {finding.message}"
                )

        if result.pdf_path:
            self.log.write(f"\nPDF report saved to: {result.pdf_path}")

        # Check for error findings and display them prominently
        error_findings = [
            f
            for f in result.ctx.findings
            if f.severity in ["warning", "high", "critical"]
        ]
        if error_findings:
            self.log.write("\n" + "!" * 50)
            self.log.write("Important Warnings/Errors:")
            for finding in error_findings:
                self.log.write(
                    f"  [{finding.severity.upper()}] {finding.source}: {finding.message}"
                )
            self.log.write("!" * 50)

