"""Task to download an NPM package artifact for SBOM generation."""

import asyncio
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

import requests

from vibanalyz.adapters.npm_client import (
    NetworkError,
    NPMError,
    PackageNotFoundError,
    get_download_info,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class DownloadNpm:
    """Task to download an NPM package artifact."""

    name = "download_npm"

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
                f"[{self.name}] Preparing to download {ctx.package.name}@{version}"
            )
            await asyncio.sleep(0)

        try:
            # Get download information
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Resolving download URL from NPM...")
                await asyncio.sleep(0)
            
            # Run blocking network call in executor
            loop = asyncio.get_event_loop()
            download_info = await loop.run_in_executor(
                None, get_download_info, ctx.package.name, version
            )
            ctx.download_info = download_info

            # Download file to temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="vibanalyz_npm_"))
            tarball_path = temp_dir / download_info.filename

            if ctx.log_display:
                ctx.log_display.write(
                    f"[{self.name}] Downloading to {tarball_path.as_posix()}"
                )
                await asyncio.sleep(0)

            # Run blocking download in executor
            def _download_file():
                with requests.get(download_info.url, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    with open(tarball_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                return tarball_path

            await loop.run_in_executor(None, _download_file)

            # Extract tarball (NPM tarballs contain a package/ subdirectory)
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Extracting tarball...")
                await asyncio.sleep(0)

            def _extract_tarball():
                extracted_dir = temp_dir / "extracted"
                extracted_dir.mkdir(exist_ok=True)
                with tarfile.open(tarball_path, "r:gz") as tar:
                    tar.extractall(extracted_dir)
                # NPM tarballs extract to a package/ subdirectory
                package_dir = extracted_dir / "package"
                if not package_dir.exists():
                    # Fallback: if no package/ subdirectory, use extracted_dir
                    package_dir = extracted_dir
                return package_dir

            package_dir = await loop.run_in_executor(None, _extract_tarball)

            # Install NPM dependencies so Syft can detect them
            # Syft's Node.js cataloger requires node_modules to detect dependencies
            if ctx.log_display:
                ctx.log_display.write_with_spinner(f"[{self.name}] Installing NPM dependencies...")
                await asyncio.sleep(0)

            def _install_dependencies():
                # Check if package.json exists
                package_json = package_dir / "package.json"
                if not package_json.exists():
                    # No package.json, skip installation
                    return False  # False means skipped
                
                # Run npm install (production dependencies only to speed up)
                # Use --no-audit and --no-fund to skip unnecessary checks
                result = subprocess.run(
                    ["npm", "install", "--production", "--no-audit", "--no-fund", "--silent"],
                    cwd=str(package_dir),
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
                if result.returncode != 0:
                    # Log warning but don't fail - Syft might still work with just package.json
                    error_msg = result.stderr or result.stdout or "Unknown error"
                    raise subprocess.CalledProcessError(
                        result.returncode, "npm install", error_msg
                    )
                return True  # True means success

            try:
                install_result = await loop.run_in_executor(None, _install_dependencies)
                if ctx.log_display:
                    if install_result is False:
                        # No package.json, skip installation
                        ctx.log_display.write(f"[{self.name}] No package.json found, skipping dependency installation")
                    elif install_result is True:
                        ctx.log_display.write(f"[{self.name}] Dependencies installed successfully")
                    await asyncio.sleep(0)
            except subprocess.TimeoutExpired:
                if ctx.log_display:
                    ctx.log_display.write(
                        f"[{self.name}] WARNING: npm install timed out, continuing without node_modules"
                    )
                    await asyncio.sleep(0)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                # npm not available or install failed - log warning but continue
                # Syft might still work with just package.json (though with limited detection)
                if ctx.log_display:
                    error_msg = str(e)
                    if isinstance(e, FileNotFoundError):
                        error_msg = "npm not found in PATH"
                    ctx.log_display.write(
                        f"[{self.name}] WARNING: Failed to install dependencies: {error_msg}. Continuing..."
                    )
                    await asyncio.sleep(0)

            # Update context with local path to extracted package directory
            ctx.download_info.local_path = str(package_dir)

            if ctx.log_display:
                ctx.log_display.write(
                    f"[{self.name}] Downloaded and extracted {download_info.filename} ({download_info.package_type})"
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
        except NPMError as e:
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: NPM error: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"NPM error: {str(e)}",
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
register(DownloadNpm())

