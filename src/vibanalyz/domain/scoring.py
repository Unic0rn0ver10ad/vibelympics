"""Risk scoring logic."""

from collections import defaultdict

from vibanalyz.domain.models import AuditResult


def _map_grype_severity(grype_severity: str) -> str:
    """
    Map Grype severity to our severity levels.
    
    Args:
        grype_severity: Grype severity string
    
    Returns:
        Our severity level: "critical", "high", "medium", "low", or "info"
    """
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


def compute_risk_score(result: AuditResult) -> int:
    """
    Compute a risk score for the audit result.
    
    Base score is 0. Vulnerabilities add to the score based on severity weights.
    """
    base_score = 0
    
    # Factor in vulnerabilities if present
    if result.ctx.vulns and result.ctx.vulns.raw:
        vuln_data = result.ctx.vulns.raw
        matches = vuln_data.get("matches", []) or []
        
        # Count vulnerabilities by severity
        severity_counts: dict[str, int] = defaultdict(int)
        
        # Deduplicate by (cve_id, package_name, package_version)
        seen_vulns: set[tuple[str, str, str]] = set()
        for match in matches:
            vulnerability = match.get("vulnerability", {})
            artifact = match.get("artifact", {})
            
            cve_id = vulnerability.get("id", "UNKNOWN")
            package_name = artifact.get("name", "unknown")
            package_version = artifact.get("version", "unknown")
            
            key = (cve_id, package_name, package_version)
            if key not in seen_vulns:
                seen_vulns.add(key)
                grype_severity = vulnerability.get("severity", "Unknown")
                severity = _map_grype_severity(grype_severity)
                severity_counts[severity] += 1
        
        # Apply weights: critical=10, high=5, medium=2, low=1, info=0
        severity_weights = {
            "critical": 10,
            "high": 5,
            "medium": 2,
            "low": 1,
            "info": 0,
        }
        
        # Calculate vulnerability score
        vuln_score = 0
        for severity, count in severity_counts.items():
            weight = severity_weights.get(severity, 0)
            vuln_score += count * weight
        
        base_score += vuln_score
    
    return base_score

