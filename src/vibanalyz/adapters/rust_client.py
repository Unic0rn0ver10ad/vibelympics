"""Rust/Crates.io registry client adapter - real HTTP implementation."""

import json
from typing import Optional

import requests

from vibanalyz.domain.models import DownloadInfo, PackageMetadata


class RustError(Exception):
    """Base exception for Rust/Crates.io-related errors."""

    pass


class PackageNotFoundError(RustError):
    """Raised when a package or version is not found on Crates.io."""

    pass


class NetworkError(RustError):
    """Raised when network-related errors occur."""

    pass


def fetch_package_metadata(name: str, version: Optional[str] = None) -> PackageMetadata:
    """
    Fetch package metadata from Crates.io API.
    
    Args:
        name: Package name (crate name)
        version: Optional version string. If None, fetches latest version.
    
    Returns:
        PackageMetadata instance with package information
    
    Raises:
        PackageNotFoundError: If package or version not found (404)
        NetworkError: If network connection fails
        RustError: For other Crates.io-related errors
    """
    # Build URL
    if version:
        url = f"https://crates.io/api/v1/crates/{name}/{version}"
    else:
        url = f"https://crates.io/api/v1/crates/{name}"
    
    try:
        # Make HTTP request with timeout
        response = requests.get(url, timeout=10)
        
        # Handle 404 - package or version not found
        if response.status_code == 404:
            if version:
                raise PackageNotFoundError(
                    f"Version '{version}' not found for crate '{name}'"
                )
            else:
                raise PackageNotFoundError(f"Crate '{name}' not found on Crates.io")
        
        # Handle other HTTP errors
        response.raise_for_status()
        
        # Parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise RustError(f"Invalid JSON response from Crates.io: {e}")
        
        # Parse and return metadata
        return _parse_crates_response(data, name, version)
        
    except requests.exceptions.Timeout:
        raise NetworkError("Connection to Crates.io timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError as e:
        raise NetworkError(f"Unable to connect to Crates.io: {e}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while fetching from Crates.io: {e}")
    except (PackageNotFoundError, RustError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        raise RustError(f"Unexpected error fetching from Crates.io: {e}")


def _parse_crates_response(json_data: dict, package_name: str, requested_version: Optional[str]) -> PackageMetadata:
    """
    Parse Crates.io JSON response into PackageMetadata.
    
    Args:
        json_data: JSON response from Crates.io API
        package_name: Original package name requested
        requested_version: Version that was requested (if any)
    
    Returns:
        PackageMetadata instance
    """
    # Crates.io API structure:
    # - If version is specified, response has "version" object
    # - If no version, response has "crate" object and "versions" array
    # - Crate object has: name, description, homepage, repository, documentation, etc.
    # - Version object has: num, dl_path, checksum, deps, etc.
    
    if requested_version or "version" in json_data:
        # Version-specific response
        version_data = json_data.get("version", {})
        crate_data = json_data.get("crate", {})
        version = version_data.get("num")
    else:
        # Package-level response - get latest version
        crate_data = json_data.get("crate", {})
        versions = json_data.get("versions", [])
        if versions:
            # Latest version is typically the first one (sorted by semver)
            version_data = versions[0]
            version = version_data.get("num")
        else:
            version = None
            version_data = {}
    
    # Extract basic info
    name = crate_data.get("name", package_name)
    summary = crate_data.get("description")
    
    # Extract author information (from crate or version)
    # Crates.io doesn't have a single author field, but has owners/users
    author = None
    author_email = None
    # Try to get from owners if available
    owners = crate_data.get("owners", [])
    if owners and isinstance(owners, list) and len(owners) > 0:
        owner = owners[0]
        if isinstance(owner, dict):
            author = owner.get("name") or owner.get("login")
            author_email = owner.get("email")
    
    # Extract URLs
    home_page = crate_data.get("homepage")
    repository = crate_data.get("repository")
    documentation = crate_data.get("documentation")
    
    # Build project_urls dict similar to PyPI format
    project_urls = {}
    if home_page:
        project_urls["Homepage"] = home_page
    if repository:
        project_urls["Repository"] = repository
    if documentation:
        project_urls["Documentation"] = documentation
    
    # Extract dependencies from version data
    requires_dist = None
    deps = version_data.get("deps", [])
    if deps and isinstance(deps, list):
        # Convert dependencies to list of strings
        # Format: "package-name:version" (using colon as separator)
        requires_dist = [f"{dep.get('crate_id', '')}:{dep.get('req', '')}" for dep in deps if dep.get('crate_id')]
    
    # Extract license
    license_info = version_data.get("license") or crate_data.get("license")
    
    # Count releases (from package-level response if available)
    release_count = None
    if not requested_version and "versions" in json_data:
        versions = json_data.get("versions", [])
        release_count = len(versions) if versions else None
    
    # Extract maintainers (owners/users)
    maintainers = None
    if owners and isinstance(owners, list):
        maintainers = [o.get("name") or o.get("login", "") for o in owners if isinstance(o, dict) and (o.get("name") or o.get("login"))]
    
    return PackageMetadata(
        name=name,
        version=version,
        summary=summary,
        maintainers=maintainers,
        home_page=home_page,
        project_urls=project_urls if project_urls else None,
        requires_dist=requires_dist,
        author=author,
        author_email=author_email,
        license=license_info,
        release_count=release_count,
    )


def get_download_info(name: str, version: str) -> DownloadInfo:
    """
    Get download URL for a specific package version from Crates.io.

    Args:
        name: Package name (crate name)
        version: Version string to download

    Returns:
        DownloadInfo with URL, filename, and package_type

    Raises:
        PackageNotFoundError: If package or version not found
        NetworkError: For network-related issues
        RustError: For other errors
    """
    url = f"https://crates.io/api/v1/crates/{name}/{version}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            raise PackageNotFoundError(f"Version '{version}' not found for crate '{name}'")

        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise RustError(f"Invalid JSON response from Crates.io: {e}")

        # Extract download info from version data
        version_data = data.get("version", {})
        
        # Crates.io download URL format: https://static.crates.io/crates/{name}/{name}-{version}.crate
        # Construct directly from crate name and version (more reliable than using dl_path)
        filename = f"{name}-{version}.crate"
        download_url = f"https://static.crates.io/crates/{name}/{filename}"

        return DownloadInfo(
            url=download_url,
            filename=filename,
            package_type="rust-crate",
        )

    except requests.exceptions.Timeout:
        raise NetworkError("Connection to Crates.io timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError as e:
        raise NetworkError(f"Unable to connect to Crates.io: {e}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while fetching from Crates.io: {e}")
    except (PackageNotFoundError, RustError):
        raise
    except Exception as e:
        raise RustError(f"Unexpected error fetching download info from Crates.io: {e}")

