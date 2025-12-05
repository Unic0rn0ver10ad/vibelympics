"""PyPI client adapter - stub implementation."""

from vibanalyz.domain.models import PackageMetadata


def fetch_package_metadata_stub(name: str, version: str | None = None) -> PackageMetadata:
    """
    Fetch package metadata from PyPI (stub implementation).
    
    This does not make any network calls. It returns a stub PackageMetadata
    instance with the provided name and version (or a placeholder).
    """
    return PackageMetadata(
        name=name,
        version=version or "0.0.0-stub",
        summary="This is a stub metadata response. Real PyPI integration will be implemented later.",
    )

