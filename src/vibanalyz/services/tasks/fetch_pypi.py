"""Task to fetch PyPI metadata."""

from vibanalyz.adapters.pypi_client import (
    NetworkError,
    PackageNotFoundError,
    PyPIError,
    fetch_package_metadata,
)
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task


class FetchPyPi:
    """Task to fetch package metadata from PyPI."""

    name = "fetch_pypi"

    def run(self, ctx: Context) -> Context:
        """Fetch PyPI metadata and update context."""
        try:
            ctx.package = fetch_package_metadata(ctx.package_name, ctx.requested_version)
            
            # Success - add info finding
            version_info = f" version {ctx.package.version}" if ctx.package.version else ""
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Successfully fetched metadata for {ctx.package_name}{version_info}",
                    severity="info",
                )
            )
        except PackageNotFoundError as e:
            # Package or version not found
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="info",
                )
            )
        except NetworkError as e:
            # Network connection issues
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="warning",
                )
            )
        except PyPIError as e:
            # Other PyPI errors
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"PyPI error: {str(e)}",
                    severity="warning",
                )
            )
        
        return ctx

