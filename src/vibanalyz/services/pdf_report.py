"""Generate PDF reports from plain text."""

from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from vibanalyz.services.artifacts import get_artifacts_dir


def _wrap_lines(text: str, max_chars: int = 100) -> list[str]:
    """Wrap lines to a maximum character width."""
    wrapped: list[str] = []
    for line in text.splitlines():
        if len(line) <= max_chars:
            wrapped.append(line)
            continue
        # simple hard wrap without hyphenation
        start = 0
        while start < len(line):
            wrapped.append(line[start : start + max_chars])
            start += max_chars
    return wrapped


def write_pdf_from_text(
    text: str,
    filename: str,
    output_dir: Path | str | None = None,
    *,
    max_chars_per_line: int = 100,
) -> Path:
    """
    Render the provided text into a PDF file.

    Args:
        text: Plain text content to render.
        filename: Target filename (e.g., 'vibanalyz-<pkg>-report.pdf').
        output_dir: Directory to write the PDF to; defaults to artifacts dir.
        max_chars_per_line: Soft wrap width to keep content readable.

    Returns:
        Absolute Path to the generated PDF.
    """
    if output_dir is None:
        output_dir = get_artifacts_dir()
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / filename

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    # basic margins
    x_margin = 50
    y_margin = 50
    y = height - y_margin

    c.setFont("Helvetica", 10)

    # wrap lines
    lines: Iterable[str] = _wrap_lines(text, max_chars=max_chars_per_line)
    line_height = 12

    for line in lines:
        if y < y_margin:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - y_margin
        c.drawString(x_margin, y, line)
        y -= line_height

    c.save()
    return pdf_path.resolve()

