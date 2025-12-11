"""PyPI client adapter - real HTTP implementation."""

import json
from typing import Optional

import requests

from vibanalyz.domain.models import DownloadInfo, PackageMetadata


class PyPIError(Exception):
    """Base exception for PyPI-related errors."""

    pass


class PackageNotFoundError(PyPIError):
    """Raised when a package or version is not found on PyPI."""

    pass


class NetworkError(PyPIError):
    """Raised when network-related errors occur."""

    pass


def fetch_package_metadata(name: str, version: Optional[str] = None) -> PackageMetadata:
    """
    Fetch package metadata from PyPI JSON API.
    
    Args:
        name: Package name
        version: Optional version string. If None, fetches latest version.
    
    Returns:
        PackageMetadata instance with package information
    
    Raises:
        PackageNotFoundError: If package or version not found (404)
        NetworkError: If network connection fails
        PyPIError: For other PyPI-related errors
    """
    # Build URL
    if version:
        url = f"https://pypi.org/pypi/{name}/{version}/json"
    else:
        url = f"https://pypi.org/pypi/{name}/json"
    
    try:
        # Make HTTP request with timeout
        response = requests.get(url, timeout=10)
        
        # Handle 404 - package or version not found
        if response.status_code == 404:
            if version:
                raise PackageNotFoundError(
                    f"Version '{version}' not found for package '{name}'"
                )
            else:
                raise PackageNotFoundError(f"Package '{name}' not found on PyPI")
        
        # Handle other HTTP errors
        response.raise_for_status()
        
        # Parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise PyPIError(f"Invalid JSON response from PyPI: {e}")
        
        # Parse and return metadata
        return _parse_pypi_response(data, name, version)
        
    except requests.exceptions.Timeout:
        raise NetworkError("Connection to PyPI timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError as e:
        raise NetworkError(f"Unable to connect to PyPI: {e}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while fetching from PyPI: {e}")
    except (PackageNotFoundError, PyPIError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        raise PyPIError(f"Unexpected error fetching from PyPI: {e}")


def _parse_pypi_response(json_data: dict, package_name: str, requested_version: Optional[str]) -> PackageMetadata:
    """
    Parse PyPI JSON response into PackageMetadata.
    
    Args:
        json_data: JSON response from PyPI API
        package_name: Original package name requested
        requested_version: Version that was requested (if any)
    
    Returns:
        PackageMetadata instance
    """
    info = json_data.get("info", {})
    releases = json_data.get("releases", {})
    
    # Extract basic info
    name = info.get("name", package_name)
    version = info.get("version")
    summary = info.get("summary")
    
    # Extract author information
    author = info.get("author")
    author_email = info.get("author_email")
    
    # Extract URLs
    home_page = info.get("home_page")
    project_urls = info.get("project_urls")  # Dict like {"Homepage": "...", "Repository": "..."}
    
    # Extract dependencies
    requires_dist = info.get("requires_dist")  # List of dependency strings
    
    # Extract maintainers (if available)
    maintainers = info.get("maintainers")
    if maintainers:
        maintainers = [m.get("name", "") for m in maintainers if isinstance(m, dict)]
    
    # Extract license
    license_info = info.get("license")
    
    # Count releases
    release_count = len(releases) if releases else None
    
    return PackageMetadata(
        name=name,
        version=version,
        summary=summary,
        maintainers=maintainers,
        home_page=home_page,
        project_urls=project_urls,
        requires_dist=requires_dist,
        author=author,
        author_email=author_email,
        license=license_info,
        release_count=release_count,
    )


# Keep stub function for backward compatibility (may be used elsewhere)
def fetch_package_metadata_stub(name: str, version: str | None = None) -> PackageMetadata:
    """
    Fetch package metadata from PyPI (stub implementation).
    
    DEPRECATED: Use fetch_package_metadata() instead.
    This is kept for backward compatibility.
    """
    return PackageMetadata(
        name=name,
        version=version or "0.0.0-stub",
        summary="This is a stub metadata response. Real PyPI integration will be implemented later.",
    )


def get_download_info(name: str, version: str) -> DownloadInfo:
    """
    Get download URL for a specific package version from PyPI.

    Prefers wheel (bdist_wheel) over source distribution (sdist).

    Args:
        name: Package name
        version: Version string to download

    Returns:
        DownloadInfo with URL, filename, and package_type

    Raises:
        PackageNotFoundError: If package or version not found
        NetworkError: For network-related issues
        PyPIError: For other errors
    """
    url = f"https://pypi.org/pypi/{name}/{version}/json"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            raise PackageNotFoundError(f"Version '{version}' not found for package '{name}'")

        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise PyPIError(f"Invalid JSON response from PyPI: {e}")

        # When fetching a specific version, PyPI returns files in top-level "urls" array
        # Fall back to releases[version] if urls is not present
        files = data.get("urls", [])
        if not files:
            releases = data.get("releases", {})
            files = releases.get(version, [])

        # Prefer wheel over sdist
        selected = None
        for file_info in files:
            if file_info.get("packagetype") == "bdist_wheel":
                selected = file_info
                break

        if not selected and files:
            # Fallback to first available (likely sdist)
            selected = files[0]

        if not selected:
            raise PyPIError(f"No downloadable files found for {name}=={version}")

        return DownloadInfo(
            url=selected.get("url", ""),
            filename=selected.get("filename", ""),
            package_type=selected.get("packagetype", ""),
        )

    except requests.exceptions.Timeout:
        raise NetworkError("Connection to PyPI timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError as e:
        raise NetworkError(f"Unable to connect to PyPI: {e}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while fetching from PyPI: {e}")
    except (PackageNotFoundError, PyPIError):
        raise
    except Exception as e:
        raise PyPIError(f"Unexpected error fetching download info from PyPI: {e}")

