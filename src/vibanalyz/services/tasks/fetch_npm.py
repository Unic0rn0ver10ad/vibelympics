"""Task to fetch NPM metadata."""

import asyncio

from vibanalyz.adapters.npm_client import (
    NetworkError,
    PackageNotFoundError,
    NPMError,
    fetch_package_metadata,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.formatting import format_package_info_lines
from vibanalyz.services.tasks import register


class FetchNpm:
    """Task to fetch package metadata from NPM."""

    name = "fetch_npm"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return "Query Repo"

    async def run(self, ctx: Context) -> Context:
        """Fetch NPM metadata and update context."""
        # Status is updated by pipeline before task runs
        # Log start of fetch operation
        if ctx.log_display:
            version_info = f"=={ctx.requested_version}" if ctx.requested_version else ""
            ctx.log_display.write(f"[{self.name}] Starting fetch for {ctx.package_name}{version_info}")
            await asyncio.sleep(0)
            ctx.log_display.write(f"[{self.name}] Connecting to NPM Registry API...")
            await asyncio.sleep(0)
        
        try:
            # Fetch package metadata
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Fetching package metadata...")
                await asyncio.sleep(0)
            
            # Run blocking network call in executor
            loop = asyncio.get_event_loop()
            ctx.package = await loop.run_in_executor(
                None, fetch_package_metadata, ctx.package_name, ctx.requested_version
            )
            
            # Success - log and add finding
            if ctx.log_display:
                version_info = f" version {ctx.package.version}" if ctx.package.version else ""
                ctx.log_display.write(f"[{self.name}] Successfully fetched metadata for {ctx.package_name}{version_info}")
                await asyncio.sleep(0)
                if ctx.package.summary:
                    ctx.log_display.write(f"[{self.name}] Summary: {ctx.package.summary}")
                    await asyncio.sleep(0)
                
                # Display Package Information section
                ctx.log_display.set_mode("action")
                lines = format_package_info_lines(ctx.package)
                ctx.log_display.write_section("Package Information", lines)
                await asyncio.sleep(0)
            
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
                ctx.log_display.write_error(f"[{self.name}] ERROR: Package or version not found: {str(e)}")
                await asyncio.sleep(0)
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="critical",
                )
            )
            # Raise fatal error to stop pipeline
            raise PipelineFatalError(
                message=f"Package '{ctx.package_name}' not found on NPM",
                source=self.name
            )
        except NetworkError as e:
            # Network connection issues
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: Network connection failed: {str(e)}")
                await asyncio.sleep(0)
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="warning",
                )
            )
        except NPMError as e:
            # Other NPM errors
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: NPM API error: {str(e)}")
                await asyncio.sleep(0)
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"NPM error: {str(e)}",
                    severity="warning",
                )
            )
        
        return ctx


# Auto-register this task
register(FetchNpm())
