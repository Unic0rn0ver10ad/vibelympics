"""Task to download a Rust crate artifact for SBOM generation."""

import asyncio
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

import requests

from vibanalyz.adapters.rust_client import (
    NetworkError,
    PackageNotFoundError,
    RustError,
    get_download_info,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class DownloadRust:
    """Task to download a Rust crate artifact."""

    name = "download_rust"

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
                ctx.log_display.write(f"[{self.name}] Resolving download URL from Crates.io...")
                await asyncio.sleep(0)
            
            # Run blocking network call in executor
            loop = asyncio.get_event_loop()
            download_info = await loop.run_in_executor(
                None, get_download_info, ctx.package.name, version
            )
            ctx.download_info = download_info

            # Download file to temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="vibanalyz_rust_"))
            crate_path = temp_dir / download_info.filename

            if ctx.log_display:
                ctx.log_display.write(
                    f"[{self.name}] Downloading to {crate_path.as_posix()}"
                )
                await asyncio.sleep(0)

            # Run blocking download in executor
            def _download_file():
                with requests.get(download_info.url, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    with open(crate_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                return crate_path

            await loop.run_in_executor(None, _download_file)

            # Extract crate (Rust crates are gzipped tarballs)
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Extracting crate...")
                await asyncio.sleep(0)

            def _extract_crate():
                extracted_dir = temp_dir / "extracted"
                extracted_dir.mkdir(exist_ok=True)
                with tarfile.open(crate_path, "r:gz") as tar:
                    tar.extractall(extracted_dir)
                # Rust crates extract to {name}-{version}/ directory
                # Find the extracted directory (should be the only subdirectory)
                subdirs = [d for d in extracted_dir.iterdir() if d.is_dir()]
                if subdirs:
                    crate_dir = subdirs[0]
                else:
                    # Fallback: use extracted_dir
                    crate_dir = extracted_dir
                return crate_dir

            crate_dir = await loop.run_in_executor(None, _extract_crate)

            # Check Cargo.toml for diagnostic purposes
            cargo_toml = crate_dir / "Cargo.toml"
            has_dependencies = False
            if cargo_toml.exists():
                try:
                    # Quick check if Cargo.toml has dependencies section
                    cargo_content = cargo_toml.read_text(encoding="utf-8")
                    has_dependencies = "[dependencies]" in cargo_content or "[dev-dependencies]" in cargo_content
                except Exception:
                    pass  # Ignore errors reading Cargo.toml
            
            # Try to generate Cargo.lock for Syft (optional)
            # Syft's Rust cataloger works better with Cargo.lock, but can work with just Cargo.toml
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Generating Cargo.lock (optional)...")
                await asyncio.sleep(0)
                if has_dependencies:
                    ctx.log_display.write(
                        f"[{self.name}] NOTE: Cargo.toml contains dependencies - Cargo.lock will improve SBOM accuracy"
                    )
                    await asyncio.sleep(0)

            def _generate_lockfile():
                # Check if Cargo.toml exists
                cargo_toml = crate_dir / "Cargo.toml"
                if not cargo_toml.exists():
                    # No Cargo.toml, skip lockfile generation
                    return None
                
                # Try to generate Cargo.lock using cargo generate-lockfile
                # This downloads dependencies and creates lockfile without building
                # Use --offline flag is not used, but we can try with network access
                # Set CARGO_HOME to a temp directory to avoid conflicts
                env = {}
                cargo_home = os.environ.get("CARGO_HOME")
                if not cargo_home:
                    # Use a temp directory for cargo cache
                    temp_cargo_home = temp_dir / ".cargo_home"
                    temp_cargo_home.mkdir(exist_ok=True)
                    env["CARGO_HOME"] = str(temp_cargo_home)
                
                result = subprocess.run(
                    ["cargo", "generate-lockfile", "--manifest-path", str(cargo_toml)],
                    cwd=str(crate_dir),
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    env={**os.environ, **env} if env else None,
                )
                if result.returncode != 0:
                    # Extract meaningful error message
                    error_output = result.stderr or result.stdout or "Unknown error"
                    # Try to extract the most relevant error line
                    error_lines = error_output.strip().split('\n')
                    # Look for lines that contain "error:" or "failed"
                    relevant_errors = [line for line in error_lines if 'error:' in line.lower() or 'failed' in line.lower()]
                    if relevant_errors:
                        error_msg = relevant_errors[-1]  # Get the last (most specific) error
                    else:
                        error_msg = error_output.split('\n')[-1] if error_output else "Unknown error"
                    
                    raise subprocess.CalledProcessError(
                        result.returncode, "cargo generate-lockfile", error_msg
                    )
                
                # Verify Cargo.lock was created
                cargo_lock = crate_dir / "Cargo.lock"
                if not cargo_lock.exists():
                    raise RuntimeError("Cargo.lock was not created despite successful command")
                
                return str(cargo_lock)

            cargo_lock_path = None
            lockfile_error = None
            try:
                cargo_lock_path = await loop.run_in_executor(None, _generate_lockfile)
                if cargo_lock_path and ctx.log_display:
                    ctx.log_display.write(f"[{self.name}] Cargo.lock generated successfully")
                    await asyncio.sleep(0)
            except subprocess.TimeoutExpired:
                lockfile_error = "cargo generate-lockfile timed out after 5 minutes"
                if ctx.log_display:
                    ctx.log_display.write(
                        f"[{self.name}] WARNING: {lockfile_error}. Continuing without Cargo.lock"
                    )
                    await asyncio.sleep(0)
            except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as e:
                # cargo not available or lockfile generation failed - log warning but continue
                # Syft can work with just Cargo.toml (though Cargo.lock provides better dependency info)
                lockfile_error = str(e)
                if isinstance(e, FileNotFoundError):
                    lockfile_error = "cargo not found in PATH"
                elif isinstance(e, subprocess.CalledProcessError):
                    # Extract the error message from the exception
                    if hasattr(e, 'stderr') and e.stderr:
                        lockfile_error = e.stderr
                    elif hasattr(e, 'output') and e.output:
                        lockfile_error = e.output
                
                if ctx.log_display:
                    # Log detailed error for diagnostics
                    ctx.log_display.write(
                        f"[{self.name}] WARNING: Failed to generate Cargo.lock: {lockfile_error}. Continuing..."
                    )
                    await asyncio.sleep(0)
                    # Add note about potential impact
                    ctx.log_display.write(
                        f"[{self.name}] NOTE: Syft may have limited success cataloging Rust dependencies without Cargo.lock"
                    )
                    await asyncio.sleep(0)
            
            # Add finding if Cargo.lock generation failed
            if not cargo_lock_path and lockfile_error:
                ctx.findings.append(
                    Finding(
                        source=self.name,
                        message=f"Failed to generate Cargo.lock: {lockfile_error}. SBOM generation may be incomplete.",
                        severity="warning",
                    )
                )

            # Update context with local path to extracted crate directory
            ctx.download_info.local_path = str(crate_dir)

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
        except RustError as e:
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: Crates.io error: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Crates.io error: {str(e)}",
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
register(DownloadRust())

