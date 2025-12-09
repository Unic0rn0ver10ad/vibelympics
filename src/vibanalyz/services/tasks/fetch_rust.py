"""Task to fetch Rust/Crates.io metadata."""

import asyncio

from vibanalyz.adapters.rust_client import (
    NetworkError,
    PackageNotFoundError,
    RustError,
    fetch_package_metadata,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class FetchRust:
    """Task to fetch package metadata from Crates.io."""

    name = "fetch_rust"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return "Query Repo"

    async def run(self, ctx: Context) -> Context:
        """Fetch Crates.io metadata and update context."""
        # Status is updated by pipeline before task runs
        # Log start of fetch operation
        if ctx.log_display:
            version_info = f"=={ctx.requested_version}" if ctx.requested_version else ""
            ctx.log_display.write(f"[{self.name}] Starting fetch for {ctx.package_name}{version_info}")
            await asyncio.sleep(0)
            ctx.log_display.write(f"[{self.name}] Connecting to Crates.io API...")
            await asyncio.sleep(0)
        
        try:
            # Fetch package metadata (run blocking I/O in executor)
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Fetching package metadata...")
                await asyncio.sleep(0)
            
            # Run blocking network call in executor to avoid blocking event loop
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
                message=f"Package '{ctx.package_name}' not found on Crates.io",
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
        except RustError as e:
            # Other Crates.io errors
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: Crates.io API error: {str(e)}")
                await asyncio.sleep(0)
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Crates.io error: {str(e)}",
                    severity="warning",
                )
            )
        
        return ctx


# Auto-register this task
register(FetchRust())

