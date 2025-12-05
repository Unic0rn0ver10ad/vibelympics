"""PDF and text report generation."""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from vibanalyz.domain.models import AuditResult


def render_text_report(result: AuditResult) -> str:
    """
    Render a text representation of the audit result.
    
    Returns a multi-line string with package info, score, and findings count.
    """
    lines = [
        "vibanalyz – Stub Audit Report",
        "=" * 40,
        "",
        f"Package: {result.ctx.package_name}",
    ]
    
    if result.ctx.package:
        lines.append(f"Version: {result.ctx.package.version or 'unknown'}")
        if result.ctx.package.summary:
            lines.append(f"Summary: {result.ctx.package.summary}")
    
    lines.extend([
        "",
        f"Risk Score: {result.score}",
        f"Findings: {len(result.ctx.findings)}",
        "",
    ])
    
    return "\n".join(lines)


def write_pdf_report(result: AuditResult, output_dir: Path | str | None = None) -> Path:
    """
    Create a PDF report for the audit result.
    
    Args:
        result: The audit result to report on
        output_dir: Directory to write the PDF to (defaults to current directory)
    
    Returns:
        Absolute path to the created PDF file
    """
    if output_dir is None:
        output_dir = Path.cwd()
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    filename = f"vibanalyz-{result.ctx.package_name}-report.pdf"
    pdf_path = output_dir / filename
    
    # Create PDF
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, "vibanalyz – Stub Audit Report")
    
    # Package info
    y = height - 100
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Package: {result.ctx.package_name}")
    
    y -= 20
    if result.ctx.package:
        c.drawString(50, y, f"Version: {result.ctx.package.version or 'unknown'}")
        y -= 20
        if result.ctx.package.summary:
            # Wrap long summaries
            summary = result.ctx.package.summary
            if len(summary) > 80:
                summary = summary[:77] + "..."
            c.drawString(50, y, f"Summary: {summary}")
            y -= 20
    
    y -= 20
    c.drawString(50, y, f"Risk Score: {result.score}")
    
    y -= 20
    c.drawString(50, y, f"Findings: {len(result.ctx.findings)}")
    
    y -= 40
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, y, "Note: This is a placeholder/stub report.")
    c.drawString(50, y - 15, "Real vulnerability analysis will be implemented in future versions.")
    
    c.save()
    
    return pdf_path.resolve()

