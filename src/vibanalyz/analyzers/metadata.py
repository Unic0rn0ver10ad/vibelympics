"""Metadata analyzer - stub implementation."""

from vibanalyz.analyzers import register
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Analyzer


class MetadataAnalyzer:
    """Analyzer that checks package metadata."""

    name = "metadata"

    def run(self, ctx: Context):
        """Run metadata analysis and yield findings."""
        if ctx.package is None:
            yield Finding(
                source=self.name,
                message="Package metadata is missing",
                severity="info",
            )
        else:
            yield Finding(
                source=self.name,
                message=f"Stub-analyzed package {ctx.package.name} version {ctx.package.version or 'unknown'}",
                severity="info",
            )


# Auto-register on import
register(MetadataAnalyzer())

