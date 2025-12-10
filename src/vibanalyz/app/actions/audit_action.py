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

            # Display results
            # Note: Package Information is now displayed in the fetch task, not here
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

    def _display_results(self, result: AuditResult, log_display, total_duration: float = None) -> None:
        """Display audit results."""
        # Display total audit time first
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
        
        # Display PDF report path
        if result.pdf_path:
            log_display.write(f"PDF report saved to: {result.pdf_path}")

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

