"""Grype CLI adapter for vulnerability scanning."""

import json
import shutil
import subprocess
from pathlib import Path


class GrypeError(Exception):
    """Base exception for Grype-related errors."""

    pass


class GrypeNotFoundError(GrypeError):
    """Raised when Grype CLI is not found in PATH."""

    pass


def scan_sbom(sbom_file_path: str, output_format: str = "json") -> dict:
    """
    Run Grype on an SBOM file and return vulnerability report as dict.
    
    Args:
        sbom_file_path: Path to SBOM file (CycloneDX JSON format)
        output_format: Output format (default: "json")
    
    Returns:
        Parsed vulnerability report as dictionary
    
    Raises:
        GrypeNotFoundError: If Grype CLI is not available
        GrypeError: For other Grype-related errors
    """
    # Check if grype is available
    grype_path = shutil.which("grype")
    if not grype_path:
        raise GrypeNotFoundError(
            "Grype CLI not found. Install from https://github.com/anchore/grype"
        )
    
    path = Path(sbom_file_path)
    if not path.exists():
        raise GrypeError(f"SBOM file does not exist: {sbom_file_path}")
    
    if not path.is_file():
        raise GrypeError(f"SBOM path is not a file: {sbom_file_path}")
    
    try:
        # Build command: grype sbom:/path/to/sbom.json -o json
        sbom_source = f"sbom:{sbom_file_path}"
        
        # Run Grype command
        result = subprocess.run(
            [grype_path, sbom_source, "-o", output_format],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=True,
        )
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise GrypeError(f"Failed to parse Grype JSON output: {e}")
    
    except subprocess.TimeoutExpired:
        raise GrypeError("Grype command timed out after 5 minutes")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or "Unknown error"
        raise GrypeError(f"Grype command failed: {error_msg}")
    except FileNotFoundError:
        raise GrypeNotFoundError(
            "Grype CLI not found. Install from https://github.com/anchore/grype"
        )
    except Exception as e:
        raise GrypeError(f"Unexpected error running Grype: {e}")

