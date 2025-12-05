"""Task to fetch PyPI metadata."""

from vibanalyz.adapters.pypi_client import fetch_package_metadata_stub
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task


class FetchPyPi:
    """Task to fetch package metadata from PyPI."""

    name = "fetch_pypi"

    def run(self, ctx: Context) -> Context:
        """Fetch PyPI metadata and update context."""
        ctx.package = fetch_package_metadata_stub(ctx.package_name, ctx.requested_version)
        ctx.findings.append(
            Finding(
                source=self.name,
                message=f"Stub metadata fetched for {ctx.package_name}",
                severity="info",
            )
        )
        return ctx

