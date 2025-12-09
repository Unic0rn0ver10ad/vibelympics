"""Action handler for running audits."""

import time

from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import AuditResult, Context
from vibanalyz.services.pipeline import run_pipeline


class AuditAction:
    """Handles audit execution and result display."""

    def __init__(self):
        """Initialize audit action (no UI components injected)."""
        pass

    async def execute(self, ctx: Context) -> AuditResult:
        """
        Execute audit and update UI.
        
        Args:
            ctx: Context with package_name, repo_source, log_display
        
        Returns:
            AuditResult from the pipeline
        
        Raises:
            Exception: If audit fails
        """
        log = ctx.log_display
        version = ctx.requested_version
        repo_source = ctx.repo_source or "pypi"

        if log:
            log.set_mode("action")

        # Validate package name
        if not ctx.package_name or not ctx.package_name.strip():
            if log:
                log.write("Please enter a valid package name.")
            raise ValueError("Package name is required")

        # Log user selection
        version_info = f"=={version}" if version else ""
        if log:
            log.write(f"User selected: {ctx.package_name}{version_info} (source: {repo_source})")

        # Log audit start and start timing
        audit_start_time = time.perf_counter()
        if log:
            log.write(f"Starting audit for package: {ctx.package_name}{version_info} (source: {repo_source})")
            log.write("Running pipeline...")
            # Note: Individual tasks will show their own timing as they complete

        try:
            # Run pipeline (now async)
            result = await run_pipeline(ctx)
            
            # Calculate total audit time
            audit_end_time = time.perf_counter()
            total_duration = audit_end_time - audit_start_time

            # Display PyPI metadata if available
            if log and result.ctx.package:
                log.set_mode("action")
                self._display_package_info(result.ctx.package, log)

            # Display results
            if log:
                log.set_mode("action")
            self._display_results(result, log, total_duration)
            return result

        except PipelineFatalError as e:
            # Calculate total audit time even on failure
            audit_end_time = time.perf_counter()
            total_duration = audit_end_time - audit_start_time
            
            # PipelineFatalError should be caught by pipeline, but handle if it propagates
            if log:
                log.write_error(f"\nFatal error during audit: {e.message}")
                # Still show total time even on failure
                package_name = ctx.package_name
                version_str = f"=={version}" if version else ""
                log.write_error(f"\nVibanalyz audit failed for {package_name}{version_str} after {total_duration:.1f} seconds.")
            raise
        except Exception as e:
            # Calculate total audit time even on error
            audit_end_time = time.perf_counter()
            total_duration = audit_end_time - audit_start_time
            
            if log:
                log.write_error(f"\nError during audit: {e}")
                import traceback

                log.write_error(traceback.format_exc())
                # Still show total time even on error
                package_name = ctx.package_name
                version_str = f"=={version}" if version else ""
                log.write_error(f"\nVibanalyz audit failed for {package_name}{version_str} after {total_duration:.1f} seconds.")
            raise

    def _display_package_info(self, package, log_display) -> None:
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

        log_display.write_section("Package Information", lines)

    def _display_results(self, result: AuditResult, log_display, total_duration: float = None) -> None:
        """Display audit results."""
        # Log results
        log_display.write(f"\nAudit complete!")
        log_display.write(f"Risk Score: {result.score}")
        log_display.write(f"Findings: {len(result.ctx.findings)}")

        if result.ctx.findings:
            log_display.write("\nFindings:")
            for finding in result.ctx.findings:
                log_display.write(
                    f"  [{finding.severity.upper()}] {finding.source}: {finding.message}"
                )

        if result.pdf_path:
            log_display.write(f"\nPDF report saved to: {result.pdf_path}")
        
        # Display total audit time
        if total_duration is not None:
            package_name = result.ctx.package_name
            package_version = None
            if result.ctx.package and result.ctx.package.version:
                package_version = result.ctx.package.version
            elif result.ctx.requested_version:
                package_version = result.ctx.requested_version
            
            version_str = f"=={package_version}" if package_version else ""
            package_display = f"{package_name}{version_str}"
            log_display.write(f"\nVibanalyz completed audit for {package_display} in {total_duration:.1f} seconds.")

        # Check for error findings and display them prominently
        error_findings = [
            f
            for f in result.ctx.findings
            if f.severity in ["warning", "high", "critical"]
        ]
        if error_findings:
            log_display.write("\n" + "!" * 50)
            log_display.write("Important Warnings/Errors:")
            for finding in error_findings:
                log_display.write(
                    f"  [{finding.severity.upper()}] {finding.source}: {finding.message}"
                )
            log_display.write("!" * 50)

