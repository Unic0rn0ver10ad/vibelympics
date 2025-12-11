"""Formatting utilities for display."""

from vibanalyz.domain.models import PackageMetadata


def format_package_info_lines(package: PackageMetadata) -> list[str]:
    """
    Format package metadata into display lines for the Package Information section.
    
    Args:
        package: PackageMetadata instance
    
    Returns:
        List of formatted information lines
    """
    lines = []
    lines.append(f"Package: {package.name}")

    if package.version:
        lines.append(f"Version: {package.version}")

    if package.summary:
        lines.append(f"Summary: {package.summary}")

    if package.requires_dist:
        dep_count = len(package.requires_dist)
        lines.append(f"Dependencies: {dep_count} direct dependencies")

    if package.project_urls:
        # Look for repository URL
        repo_url = None
        for key, url in package.project_urls.items():
            if key.lower() in ["repository", "source", "code"]:
                repo_url = url
                break

        if repo_url:
            lines.append(f"Repository: {repo_url}")
        elif package.home_page:
            lines.append(f"Homepage: {package.home_page}")

    if package.author:
        author_info = package.author
        if package.author_email:
            author_info += f" ({package.author_email})"
        lines.append(f"Author: {author_info}")

    if package.license:
        lines.append(f"License: {package.license}")

    if package.release_count is not None:
        lines.append(f"Total Releases: {package.release_count}")

    return lines

