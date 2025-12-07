"""Task to fetch PyPI metadata."""

from vibanalyz.adapters.pypi_client import (
    NetworkError,
    PackageNotFoundError,
    PyPIError,
    fetch_package_metadata,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class FetchPyPi:
    """Task to fetch package metadata from PyPI."""

    name = "fetch_pypi"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return f"Contacting PyPI repo for {ctx.package_name} module."

    def run(self, ctx: Context) -> Context:
        """Fetch PyPI metadata and update context."""
        # Log start of fetch operation
        if ctx.log_display:
            version_info = f"=={ctx.requested_version}" if ctx.requested_version else ""
            ctx.log_display.write(f"[{self.name}] Starting fetch for {ctx.package_name}{version_info}")
            ctx.log_display.write(f"[{self.name}] Connecting to PyPI API...")
        if ctx.progress_tracker:
            ctx.progress_tracker.update_detail(
                f"[{self.name}] Connecting to PyPI API", progress=None
            )
        
        try:
            # Fetch package metadata
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Fetching package metadata...")

            if ctx.progress_tracker:
                ctx.progress_tracker.update_detail(
                    f"[{self.name}] Fetching metadata for {ctx.package_name}", progress=None
                )
            
            ctx.package = fetch_package_metadata(ctx.package_name, ctx.requested_version)
            
            # Success - log and add finding
            if ctx.log_display:
                version_info = f" version {ctx.package.version}" if ctx.package.version else ""
                ctx.log_display.write(f"[{self.name}] Successfully fetched metadata for {ctx.package_name}{version_info}")
                if ctx.package.summary:
                    ctx.log_display.write(f"[{self.name}] Summary: {ctx.package.summary}")

            if ctx.progress_tracker:
                ctx.progress_tracker.update_detail(
                    f"[{self.name}] Metadata fetched for {ctx.package_name}", progress=1.0
                )
            
            version_info = f" version {ctx.package.version}" if ctx.package.version else ""
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Successfully fetched metadata for {ctx.package_name}{version_info}",
                    severity="info",
                )
            )
        except PackageNotFoundError as e:
            # Package or version not found - fatal error
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] ERROR: Package or version not found: {str(e)}")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="critical",
                )
            )
            # Raise fatal error to stop pipeline
            raise PipelineFatalError(
                message=f"Package '{ctx.package_name}' not found on PyPI",
                source=self.name
            )
        except NetworkError as e:
            # Network connection issues
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] ERROR: Network connection failed: {str(e)}")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="warning",
                )
            )
        except PyPIError as e:
            # Other PyPI errors
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] ERROR: PyPI API error: {str(e)}")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"PyPI error: {str(e)}",
                    severity="warning",
                )
            )
        
        return ctx


# Auto-register this task
register(FetchPyPi())

