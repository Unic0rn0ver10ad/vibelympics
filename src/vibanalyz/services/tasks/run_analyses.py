"""Task to run all registered analyzers."""

from vibanalyz.analyzers import all_analyzers
from vibanalyz.domain.models import Context
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class RunAnalyses:
    """Task to run all registered analyzers."""

    name = "run_analyses"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return f"Analyzing metadata for {ctx.package_name} module."

    def run(self, ctx: Context) -> Context:
        """Run all analyzers and extend findings."""
        analyzers = all_analyzers()

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Starting security analysis")
            ctx.log_display.write(f"[{self.name}] Found {len(analyzers)} analyzer(s) to run")
        if ctx.progress_tracker:
            ctx.progress_tracker.update_detail(
                f"[{self.name}] Preparing analyzers", progress=0.0
            )

        for idx, analyzer in enumerate(analyzers, start=1):
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Running analyzer: {analyzer.name}")

            if ctx.progress_tracker:
                step_progress = idx / max(len(analyzers), 1)
                ctx.progress_tracker.update_detail(
                    f"[{self.name}] Running analyzer: {analyzer.name}",
                    progress=step_progress,
                )

            findings = analyzer.run(ctx)
            findings_list = list(findings)  # Convert iterable to list
            
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Analyzer '{analyzer.name}' found {len(findings_list)} finding(s)")
                for finding in findings_list:
                    ctx.log_display.write(f"[{self.name}]   [{finding.severity.upper()}] {finding.message}")

            ctx.findings.extend(findings_list)

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Analysis complete. Total findings: {len(ctx.findings)}")

        if ctx.progress_tracker:
            ctx.progress_tracker.update_detail(
                f"[{self.name}] Analysis complete", progress=1.0
            )

        return ctx


# Auto-register this task
register(RunAnalyses())

