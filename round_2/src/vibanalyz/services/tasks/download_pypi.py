"""Task to download a PyPI package artifact for SBOM generation."""

import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import requests

from vibanalyz.adapters.pypi_client import (
    NetworkError,
    PackageNotFoundError,
    PyPIError,
    get_download_info,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class DownloadPyPi:
    """Task to download a PyPI package artifact."""

    name = "download_pypi"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return "Download Package"

    async def run(self, ctx: Context) -> Context:
        """Download the package file and update context."""
        # Status is updated by pipeline before task runs
        if not ctx.package:
            raise PipelineFatalError(
                message="Cannot download package: metadata not available",
                source=self.name,
            )

        # Determine version to download
        version: Optional[str] = ctx.package.version or ctx.requested_version
        if not version:
            raise PipelineFatalError(
                message="Cannot download package: version is not specified",
                source=self.name,
            )

        if ctx.log_display:
            ctx.log_display.write(
                f"[{self.name}] Preparing to download {ctx.package.name}=={version}"
            )
            await asyncio.sleep(0)

        try:
            # Get download information
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Resolving download URL from PyPI...")
                await asyncio.sleep(0)
            
            # Run blocking network call in executor
            loop = asyncio.get_event_loop()
            download_info = await loop.run_in_executor(
                None, get_download_info, ctx.package.name, version
            )
            ctx.download_info = download_info

            # Download file to temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="vibanalyz_pypi_"))
            target_path = temp_dir / download_info.filename

            if ctx.log_display:
                ctx.log_display.write(
                    f"[{self.name}] Downloading to {target_path.as_posix()}"
                )
                await asyncio.sleep(0)

            # Run blocking download in executor
            def _download_file():
                with requests.get(download_info.url, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    with open(target_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                return target_path

            await loop.run_in_executor(None, _download_file)

            # Update context with local path
            ctx.download_info.local_path = str(target_path)

            if ctx.log_display:
                ctx.log_display.write(
                    f"[{self.name}] Downloaded {download_info.filename} ({download_info.package_type})"
                )
                await asyncio.sleep(0)

            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Downloaded package artifact: {download_info.filename}",
                    severity="info",
                )
            )

        except PackageNotFoundError as e:
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="critical",
                )
            )
            raise PipelineFatalError(message=str(e), source=self.name)
        except NetworkError as e:
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="critical",
                )
            )
            raise PipelineFatalError(message=str(e), source=self.name)
        except PyPIError as e:
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: PyPI error: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"PyPI error: {str(e)}",
                    severity="critical",
                )
            )
            raise PipelineFatalError(message=str(e), source=self.name)
        except requests.exceptions.RequestException as e:
            msg = f"Failed to download package artifact: {e}"
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: {msg}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=msg,
                    severity="critical",
                )
            )
            raise PipelineFatalError(message=msg, source=self.name)

        return ctx


# Auto-register this task
register(DownloadPyPi())
