"""Task to run all registered analyzers."""

import asyncio

from vibanalyz.analyzers import all_analyzers
from vibanalyz.domain.models import Context
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class RunAnalyses:
    """Task to run all registered analyzers."""

    name = "run_analyses"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return "Analyze Package"

    async def run(self, ctx: Context) -> Context:
        """Run all analyzers and extend findings."""
        # Status is updated by pipeline before task runs
        analyzers = all_analyzers()

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Starting security analysis")
            await asyncio.sleep(0)
            ctx.log_display.write(f"[{self.name}] Found {len(analyzers)} analyzer(s) to run")
            await asyncio.sleep(0)

        for idx, analyzer in enumerate(analyzers, start=1):
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Running analyzer: {analyzer.name}")
                await asyncio.sleep(0)

            findings = analyzer.run(ctx)
            findings_list = list(findings)  # Convert iterable to list
            
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Analyzer '{analyzer.name}' found {len(findings_list)} finding(s)")
                await asyncio.sleep(0)
                for finding in findings_list:
                    ctx.log_display.write(f"[{self.name}]   [{finding.severity.upper()}] {finding.message}")
                    await asyncio.sleep(0)

            ctx.findings.extend(findings_list)

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Analysis complete. Total findings: {len(ctx.findings)}")
            await asyncio.sleep(0)

        return ctx


# Auto-register this task
register(RunAnalyses())

