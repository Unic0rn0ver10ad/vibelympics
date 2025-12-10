"""Generate PDF reports from plain text."""

import pprint
from pathlib import Path
from typing import Iterable

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from vibanalyz.services.artifacts import get_artifacts_dir


def format_report_text(
    report_data: dict,
    package_name: str | None = None,
    output_dir: Path | str | None = None,
) -> str:
    """
    Format report data dictionary into formatted text for PDF.
    
    Args:
        report_data: Dictionary with repository_health, components, and vulnerabilities keys
        package_name: Optional package name for saving dict file
        output_dir: Optional output directory for saving dict file; defaults to artifacts dir
    
    Returns:
        Formatted text string
    """
    # Save structured dict to text file if package_name is provided
    if package_name:
        try:
            if output_dir is None:
                output_dir = get_artifacts_dir()
            elif isinstance(output_dir, str):
                output_dir = Path(output_dir)
            
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"vibanalyz-{package_name}-report-data.txt"
            dict_file_path = output_dir / filename
            
            # Format dict as Python literal using pprint
            dict_text = pprint.pformat(report_data, width=120, indent=2)
            
            # Write to file
            with open(dict_file_path, "w", encoding="utf-8") as f:
                f.write(dict_text)
        except Exception:
            # Silently fail - don't break PDF generation if dict saving fails
            pass
    
    lines = []
    
    # Repository Health section
    lines.append("=" * 50)
    lines.append("Repository Health")
    lines.append("=" * 50)
    
    repo_health = report_data.get("repository_health", {})
    lines.append(f"Repository: {repo_health.get('repository', 'None found')}")
    lines.append(f"License: {repo_health.get('license', 'No license found')}")
    total_releases = repo_health.get("total_releases")
    if total_releases is not None:
        lines.append(f"Total Releases: {total_releases}")
    else:
        lines.append("Total Releases: None")
    
    # Components & Dependencies section
    lines.append("")
    lines.append("=" * 50)
    lines.append("Components & Dependencies")
    lines.append("=" * 50)
    
    components = report_data.get("components", {})
    total_components = components.get("total_components")
    if total_components is not None:
        lines.append(f"Total Components: {total_components}")
    else:
        lines.append("Total Components: None")
    
    dependency_depth = components.get("dependency_depth")
    if dependency_depth is not None:
        lines.append(f"Dependency Depth: {dependency_depth} level(s)")
    else:
        lines.append("Dependency Depth: None")
    
    direct_deps = components.get("direct_dependencies")
    if direct_deps is not None:
        lines.append(f"Direct Dependencies: {direct_deps}")
    else:
        lines.append("Direct Dependencies: None")
    
    transitive_deps = components.get("transitive_dependencies")
    if transitive_deps is not None:
        lines.append(f"Transitive Dependencies: {transitive_deps}")
    else:
        lines.append("Transitive Dependencies: None")
    
    # Known Vulnerabilities section
    lines.append("")
    lines.append("=" * 50)
    lines.append("Known Vulnerabilities")
    lines.append("=" * 50)
    
    vulns = report_data.get("vulnerabilities", {})
    total_matches = vulns.get("total_matches", "Unknown")
    unique_vulns = vulns.get("unique_vulnerabilities", "Unknown")
    
    lines.append(f"Found {total_matches} vulnerability match(es), {unique_vulns} unique vulnerability(ies)")
    
    vulnerabilities_found = vulns.get("vulnerabilities_found")
    if vulnerabilities_found:
        vuln_list = [f"{v.get('cve_id', 'UNKNOWN')}: {v.get('package_name', 'unknown')}@{v.get('package_version', 'unknown')}" for v in vulnerabilities_found]
        lines.append(f"Vulnerabilities found: {', '.join(vuln_list)}")
    else:
        lines.append("Vulnerabilities found: None")
    
    high_sev = vulns.get("high_severity", "Unknown")
    moderate_sev = vulns.get("moderate_severity", "Unknown")
    low_sev = vulns.get("low_severity", "Unknown")
    
    lines.append(f"High Severity Vulnerabilities: {high_sev}")
    lines.append(f"Moderate Severity Vulnerabilities: {moderate_sev}")
    lines.append(f"Low Severity Vulnerabilities: {low_sev}")
    
    return "\n".join(lines)


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

