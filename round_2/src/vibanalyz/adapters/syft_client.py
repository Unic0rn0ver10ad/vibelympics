"""Syft CLI adapter for SBOM generation."""

import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional


class SyftError(Exception):
    """Base exception for Syft-related errors."""

    pass


class SyftNotFoundError(SyftError):
    """Raised when Syft CLI is not found in PATH."""

    pass


def generate_sbom(file_path: str, output_format: str = "cyclonedx-json") -> dict:
    """
    Run Syft on a file or directory and return SBOM as dict.
    
    Args:
        file_path: Path to file or directory to scan
        output_format: Output format (default: "json")
    
    Returns:
        Parsed SBOM as dictionary
    
    Raises:
        SyftNotFoundError: If Syft CLI is not available
        SyftError: For other Syft-related errors
    """
    # Check if syft is available
    syft_path = shutil.which("syft")
    if not syft_path:
        raise SyftNotFoundError(
            "Syft CLI not found. Install from https://github.com/anchore/syft"
        )
    
    path = Path(file_path)
    if not path.exists():
        raise SyftError(f"Path does not exist: {file_path}")
    
    # Build command: syft file:/path/to/file -o json
    # Syft supports file: and dir: prefixes
    syft_source: Optional[str] = None
    extracted_dir: Optional[Path] = None

    try:
        if path.is_file():
            # For wheel files, extract to a temp directory so Python catalogers can operate
            if path.suffix.lower() == ".whl":
                try:
                    extracted_dir = Path(tempfile.mkdtemp(prefix="vibanalyz_whl_"))
                    with zipfile.ZipFile(path, "r") as zf:
                        zf.extractall(extracted_dir)
                except zipfile.BadZipFile as e:
                    raise SyftError(f"Failed to extract wheel: {e}") from e
                syft_source = f"dir:{extracted_dir}"
            else:
                syft_source = f"file:{file_path}"
        elif path.is_dir():
            syft_source = f"dir:{file_path}"
        else:
            raise SyftError(f"Path is neither a file nor directory: {file_path}")
    
        # Run Syft command
        result = subprocess.run(
            [syft_path, syft_source, "-o", output_format],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=True,
        )
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise SyftError(f"Failed to parse Syft JSON output: {e}")
    
    except subprocess.TimeoutExpired:
        raise SyftError("Syft command timed out after 5 minutes")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or "Unknown error"
        raise SyftError(f"Syft command failed: {error_msg}")
    except FileNotFoundError:
        raise SyftNotFoundError(
            "Syft CLI not found. Install from https://github.com/anchore/syft"
        )
    except Exception as e:
        raise SyftError(f"Unexpected error running Syft: {e}")
    finally:
        # Clean up extracted wheel directory if used
        if extracted_dir and extracted_dir.exists():
            shutil.rmtree(extracted_dir, ignore_errors=True)
