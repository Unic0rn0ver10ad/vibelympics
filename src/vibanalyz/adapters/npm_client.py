"""NPM registry client adapter - real HTTP implementation."""

import json
from typing import Optional

import requests

from vibanalyz.domain.models import PackageMetadata


class NPMError(Exception):
    """Base exception for NPM-related errors."""

    pass


class PackageNotFoundError(NPMError):
    """Raised when a package or version is not found on NPM."""

    pass


class NetworkError(NPMError):
    """Raised when network-related errors occur."""

    pass


def fetch_package_metadata(name: str, version: Optional[str] = None) -> PackageMetadata:
    """
    Fetch package metadata from NPM Registry API.
    
    Args:
        name: Package name
        version: Optional version string. If None, fetches latest version.
    
    Returns:
        PackageMetadata instance with package information
    
    Raises:
        PackageNotFoundError: If package or version not found (404)
        NetworkError: If network connection fails
        NPMError: For other NPM-related errors
    """
    # Build URL
    if version:
        url = f"https://registry.npmjs.org/{name}/{version}"
    else:
        url = f"https://registry.npmjs.org/{name}"
    
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
                raise PackageNotFoundError(f"Package '{name}' not found on NPM")
        
        # Handle other HTTP errors
        response.raise_for_status()
        
        # Parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise NPMError(f"Invalid JSON response from NPM: {e}")
        
        # Parse and return metadata
        return _parse_npm_response(data, name, version)
        
    except requests.exceptions.Timeout:
        raise NetworkError("Connection to NPM registry timed out. Please check your internet connection.")
    except requests.exceptions.ConnectionError as e:
        raise NetworkError(f"Unable to connect to NPM registry: {e}")
    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error while fetching from NPM: {e}")
    except (PackageNotFoundError, NPMError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        raise NPMError(f"Unexpected error fetching from NPM: {e}")


def _parse_npm_response(json_data: dict, package_name: str, requested_version: Optional[str]) -> PackageMetadata:
    """
    Parse NPM Registry JSON response into PackageMetadata.
    
    Args:
        json_data: JSON response from NPM Registry API
        package_name: Original package name requested
        requested_version: Version that was requested (if any)
    
    Returns:
        PackageMetadata instance
    """
    # NPM API structure:
    # - If version is specified, response is the version-specific data
    # - If no version, response has "dist-tags" with "latest" and "versions" dict
    # - Version-specific data has fields like: name, version, description, author, etc.
    
    # Determine if we got version-specific or package-level response
    if requested_version or "version" in json_data:
        # Version-specific response
        version_data = json_data
        version = version_data.get("version")
    else:
        # Package-level response - get latest version
        dist_tags = json_data.get("dist-tags", {})
        latest_version = dist_tags.get("latest")
        if latest_version:
            versions = json_data.get("versions", {})
            version_data = versions.get(latest_version, {})
            version = latest_version
        else:
            # Fallback: try to get first available version
            versions = json_data.get("versions", {})
            if versions:
                version = list(versions.keys())[0]
                version_data = versions[version]
            else:
                version = None
                version_data = json_data
    
    # Extract basic info
    name = version_data.get("name", package_name)
    summary = version_data.get("description")
    
    # Extract author information
    author = None
    author_email = None
    author_info = version_data.get("author")
    if isinstance(author_info, dict):
        author = author_info.get("name")
        author_email = author_info.get("email")
    elif isinstance(author_info, str):
        # Parse string format: "Name <email> (url)"
        author = author_info
        # Try to extract email if present
        if "<" in author_info and ">" in author_info:
            start = author_info.find("<") + 1
            end = author_info.find(">")
            if start > 0 and end > start:
                author_email = author_info[start:end]
                author = author_info[:start-1].strip()
    
    # Extract maintainers (NPM uses "maintainers" field)
    maintainers = version_data.get("maintainers")
    if maintainers and isinstance(maintainers, list):
        maintainers = [m.get("name", "") for m in maintainers if isinstance(m, dict) and "name" in m]
    
    # Extract URLs
    home_page = version_data.get("homepage")
    repository = version_data.get("repository")
    bugs = version_data.get("bugs")
    
    # Build project_urls dict similar to PyPI format
    project_urls = {}
    if home_page:
        project_urls["Homepage"] = home_page
    if repository:
        if isinstance(repository, dict):
            repo_url = repository.get("url", "")
        else:
            repo_url = str(repository)
        project_urls["Repository"] = repo_url
    if bugs:
        if isinstance(bugs, dict):
            bugs_url = bugs.get("url", "")
        else:
            bugs_url = str(bugs)
        project_urls["Bug Tracker"] = bugs_url
    
    # Extract dependencies
    requires_dist = None
    dependencies = version_data.get("dependencies")
    if dependencies and isinstance(dependencies, dict):
        # Convert NPM dependencies dict to list of strings
        # Format: "package-name@version"
        requires_dist = [f"{dep}@{ver}" for dep, ver in dependencies.items()]
    
    # Extract license
    license_info = version_data.get("license")
    if isinstance(license_info, dict):
        license_info = license_info.get("type")
    
    # Count releases (from package-level response if available)
    release_count = None
    if not requested_version and "versions" in json_data:
        versions = json_data.get("versions", {})
        release_count = len(versions) if versions else None
    
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
