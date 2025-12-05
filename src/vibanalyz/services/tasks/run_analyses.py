"""Task to run all registered analyzers."""

from vibanalyz.analyzers import all_analyzers
from vibanalyz.domain.models import Context
from vibanalyz.domain.protocols import Task


class RunAnalyses:
    """Task to run all registered analyzers."""

    name = "run_analyses"

    def run(self, ctx: Context) -> Context:
        """Run all analyzers and extend findings."""
        for analyzer in all_analyzers():
            findings = analyzer.run(ctx)
            ctx.findings.extend(findings)
        return ctx

