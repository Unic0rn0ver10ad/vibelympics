"""PDF and text report generation."""

from collections import defaultdict
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from vibanalyz.domain.models import AuditResult
from vibanalyz.services.artifacts import get_artifacts_dir


def _map_grype_severity(grype_severity: str) -> str:
    """Map Grype severity to our severity levels."""
    severity_lower = grype_severity.lower() if grype_severity else "unknown"
    
    if severity_lower == "critical":
        return "critical"
    elif severity_lower == "high":
        return "high"
    elif severity_lower == "medium":
        return "medium"
    elif severity_lower == "low":
        return "low"
    else:
        return "info"


def _extract_fixed_version(match: dict) -> str | None:
    """Extract fixed version from Grype match."""
    vulnerability = match.get("vulnerability", {})
    fix = vulnerability.get("fix", {})
    versions = fix.get("versions", [])
    
    if versions and len(versions) > 0:
        return versions[0]
    return None


def _parse_vulnerabilities(vuln_data: dict) -> tuple[dict[str, int], list[dict], int, int]:
    """
    Parse vulnerability data and return summary.
    
    Returns:
        Tuple of (severity_counts, unique_vulns, total_matches, unique_count)
    """
    matches = vuln_data.get("matches", []) or []
    total_matches = len(matches)
    
    # Deduplicate by (cve_id, package_name, package_version)
    vuln_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for match in matches:
        vulnerability = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        
        cve_id = vulnerability.get("id", "UNKNOWN")
        package_name = artifact.get("name", "unknown")
        package_version = artifact.get("version", "unknown")
        
        key = (cve_id, package_name, package_version)
        vuln_groups[key].append(match)
    
    unique_count = len(vuln_groups)
    
    # Count by severity
    severity_counts: dict[str, int] = defaultdict(int)
    unique_vulns: list[dict] = []
    
    for key, match_list in vuln_groups.items():
        match = match_list[0]
        vulnerability = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        
        grype_severity = vulnerability.get("severity", "Unknown")
        severity = _map_grype_severity(grype_severity)
        severity_counts[severity] += 1
        
        # Store unique vulnerability info
        unique_vulns.append({
            "cve_id": vulnerability.get("id", "UNKNOWN"),
            "package_name": artifact.get("name", "unknown"),
            "package_version": artifact.get("version", "unknown"),
            "severity": severity,
            "description": vulnerability.get("description") or vulnerability.get("name") or "No description",
            "fixed_version": _extract_fixed_version(match),
            "component_count": len(match_list),
        })
    
    return severity_counts, unique_vulns, total_matches, unique_count


def render_text_report(result: AuditResult) -> str:
    """
    Render a text representation of the audit result.
    
    Returns a multi-line string with package info, score, findings, and vulnerabilities.
    """
    lines = [
        "vibanalyz – Audit Report",
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
    
    # Add vulnerability section if present
    if result.ctx.vulns and result.ctx.vulns.raw:
        severity_counts, unique_vulns, total_matches, unique_count = _parse_vulnerabilities(
            result.ctx.vulns.raw
        )
        
        lines.extend([
            "Vulnerabilities",
            "-" * 40,
            f"Total Unique Vulnerabilities: {unique_count}",
        ])
        
        if total_matches != unique_count:
            lines.append(f"Total Matches: {total_matches} ({total_matches - unique_count} duplicate(s))")
        
        lines.append("")
        
        # Summary by severity
        severity_order = ["critical", "high", "medium", "low", "info"]
        for sev in severity_order:
            count = severity_counts.get(sev, 0)
            if count > 0:
                lines.append(f"  {sev.capitalize()}: {count}")
        
        lines.append("")
        
        # Detailed list
        if unique_vulns:
            lines.append("Vulnerability Details:")
            lines.append("")
            
            # Group by severity
            vulns_by_severity: dict[str, list[dict]] = defaultdict(list)
            for vuln in unique_vulns:
                vulns_by_severity[vuln["severity"]].append(vuln)
            
            for sev in severity_order:
                if sev not in vulns_by_severity:
                    continue
                
                for vuln in vulns_by_severity[sev]:
                    detail_parts = [f"  [{sev.upper()}] CVE-{vuln['cve_id']}"]
                    detail_parts.append(f"{vuln['package_name']}@{vuln['package_version']}")
                    
                    if vuln["fixed_version"]:
                        detail_parts.append(f"(Fixed in {vuln['fixed_version']})")
                    else:
                        detail_parts.append("(No fix available)")
                    
                    if vuln["component_count"] > 1:
                        detail_parts.append(f"[affects {vuln['component_count']} components]")
                    
                    lines.append(" ".join(detail_parts))
                    
                    # Add description
                    desc = vuln["description"]
                    if desc and desc != "No description":
                        # Wrap long descriptions
                        if len(desc) > 80:
                            desc = desc[:77] + "..."
                        lines.append(f"    {desc}")
                    lines.append("")
    
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
        output_dir = get_artifacts_dir()
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
    c.drawString(50, height - 50, "vibanalyz – Audit Report")
    
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
    
    # Vulnerability section
    y -= 30
    if result.ctx.vulns and result.ctx.vulns.raw:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Vulnerabilities")
        y -= 25
        
        c.setFont("Helvetica", 12)
        severity_counts, unique_vulns, total_matches, unique_count = _parse_vulnerabilities(
            result.ctx.vulns.raw
        )
        
        c.drawString(50, y, f"Total Unique Vulnerabilities: {unique_count}")
        y -= 20
        
        if total_matches != unique_count:
            c.drawString(50, y, f"Total Matches: {total_matches} ({total_matches - unique_count} duplicate(s))")
            y -= 20
        
        # Summary by severity
        severity_order = ["critical", "high", "medium", "low", "info"]
        for sev in severity_order:
            count = severity_counts.get(sev, 0)
            if count > 0:
                c.drawString(70, y, f"{sev.capitalize()}: {count}")
                y -= 18
        
        y -= 10
        
        # Detailed list (limit to first page space)
        if unique_vulns and y > 100:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Vulnerability Details:")
            y -= 20
            
            c.setFont("Helvetica", 10)
            # Group by severity
            vulns_by_severity: dict[str, list[dict]] = defaultdict(list)
            for vuln in unique_vulns:
                vulns_by_severity[vuln["severity"]].append(vuln)
            
            for sev in severity_order:
                if sev not in vulns_by_severity or y < 50:
                    continue
                
                for vuln in vulns_by_severity[sev][:5]:  # Limit to 5 per severity for space
                    if y < 50:
                        break
                    
                    detail_parts = [f"[{sev.upper()}] CVE-{vuln['cve_id']}"]
                    detail_parts.append(f"{vuln['package_name']}@{vuln['package_version']}")
                    
                    if vuln["fixed_version"]:
                        detail_parts.append(f"(Fixed in {vuln['fixed_version']})")
                    
                    detail_line = " ".join(detail_parts)
                    # Truncate if too long
                    if len(detail_line) > 90:
                        detail_line = detail_line[:87] + "..."
                    c.drawString(70, y, detail_line)
                    y -= 15
                    
                    # Add description if space
                    if y > 50 and vuln["description"] and vuln["description"] != "No description":
                        desc = vuln["description"]
                        if len(desc) > 85:
                            desc = desc[:82] + "..."
                        c.setFont("Helvetica-Oblique", 9)
                        c.drawString(80, y, desc)
                        y -= 12
                        c.setFont("Helvetica", 10)
                    
                    y -= 3
    
    c.save()
    
    return pdf_path.resolve()

