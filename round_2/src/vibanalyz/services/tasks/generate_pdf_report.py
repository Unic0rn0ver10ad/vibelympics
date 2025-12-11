"""Task to generate a PDF report from structured report data."""

import asyncio
from pathlib import Path

from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.artifacts import get_artifacts_dir, get_host_hint
from vibanalyz.services.pdf_report import (
    extract_template_variables,
    get_template_path,
    render_html_template,
    convert_html_to_pdf,
)
from vibanalyz.services.tasks import register


class GeneratePdfReport:
    """Generate PDF report using structured report data."""

    name = "generate_pdf_report"

    def get_status_message(self, ctx: Context) -> str:
        return "Generate PDF report"

    async def run(self, ctx: Context) -> Context:
        if ctx.report_data is None:
            raise PipelineFatalError(
                message="Cannot generate PDF: report data not available. Ensure extract_report_data task ran successfully.",
                source=self.name,
            )

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Generating PDF from report data...")
            await asyncio.sleep(0)

        artifacts_dir = Path(get_artifacts_dir())
        filename = f"vibanalyz-{ctx.package_name}-report.pdf"
        output_pdf = artifacts_dir / filename

        variables = extract_template_variables(ctx.report_data)
        template_path = get_template_path()

        def _generate_pdf() -> Path:
            html_content = render_html_template(template_path, variables)
            return convert_html_to_pdf(html_content, output_pdf)

        try:
            loop = asyncio.get_event_loop()
            pdf_path = await loop.run_in_executor(None, _generate_pdf)
            ctx.report_path = str(pdf_path)
        except Exception as e:
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: Failed to write PDF: {e}")
                await asyncio.sleep(0)
            raise PipelineFatalError(
                message=f"PDF generation failed: {e}",
                source=self.name,
            ) from e

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] PDF saved to: {ctx.report_path}")
            await asyncio.sleep(0)
            host_hint = get_host_hint(artifacts_dir)
            if host_hint:
                ctx.log_display.write(f"[{self.name}] Host path hint: {host_hint}")
                await asyncio.sleep(0)

        ctx.findings.append(
            Finding(
                source=self.name,
                message="PDF report generated from structured report data",
                severity="info",
            )
        )

        return ctx


# Auto-register this task
register(GeneratePdfReport())

