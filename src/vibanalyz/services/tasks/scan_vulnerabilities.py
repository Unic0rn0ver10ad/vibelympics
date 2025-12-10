"""Task to scan SBOM for vulnerabilities using Grype."""

import asyncio
from collections import defaultdict
from typing import Optional

from vibanalyz.adapters.grype_client import (
    GrypeError,
    GrypeNotFoundError,
    scan_sbom,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding, VulnReport
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


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
        # Negligible, Unknown, or any other value
        return "info"


def _build_sbom_lookup_maps(sbom_data: dict) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """
    Build lookup maps from SBOM for component matching.
    
    Args:
        sbom_data: CycloneDX SBOM dictionary
    
    Returns:
        Tuple of (purl_map, name_version_map)
        - purl_map: maps PURL to bom-ref
        - name_version_map: maps (name, version) to bom-ref
    """
    purl_map: dict[str, str] = {}
    name_version_map: dict[tuple[str, str], str] = {}
    
    components = sbom_data.get("components", []) or []
    for comp in components:
        bom_ref = comp.get("bom-ref")
        if not bom_ref:
            continue
        
        # Extract PURL if available
        purl = comp.get("purl")
        if purl:
            purl_map[purl] = bom_ref
        
        # Extract name and version
        name = comp.get("name")
        version = comp.get("version", "")
        if name:
            name_version_map[(name, version)] = bom_ref
    
    return purl_map, name_version_map


def _extract_fixed_version(match: dict) -> Optional[str]:
    """
    Extract fixed version from Grype match.
    
    Args:
        match: Grype vulnerability match dictionary
    
    Returns:
        Fixed version string if available, None otherwise
    """
    vulnerability = match.get("vulnerability", {})
    fix = vulnerability.get("fix", {})
    versions = fix.get("versions", [])
    
    if versions and len(versions) > 0:
        return versions[0]
    return None


def _find_sbom_component(
    artifact: dict,
    purl_map: dict[str, str],
    name_version_map: dict[tuple[str, str], str],
) -> Optional[str]:
    """
    Find SBOM component bom-ref for a Grype artifact.
    
    Args:
        artifact: Grype artifact dictionary
        purl_map: PURL to bom-ref mapping
        name_version_map: (name, version) to bom-ref mapping
    
    Returns:
        bom-ref if found, None otherwise
    """
    # Try PURL match first
    purl = artifact.get("purl")
    if purl and purl in purl_map:
        return purl_map[purl]
    
    # Fallback to name/version match
    name = artifact.get("name")
    version = artifact.get("version", "")
    if name:
        key = (name, version)
        if key in name_version_map:
            return name_version_map[key]
    
    return None


class ScanVulnerabilities:
    """Task to scan SBOM for vulnerabilities using Grype."""

    name = "scan_vulnerabilities"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return "Scan for Vulnerabilities"

    async def run(self, ctx: Context) -> Context:
        """Scan SBOM for vulnerabilities and update context."""
        # Status is updated by pipeline before task runs
        if not ctx.sbom or not ctx.sbom.file_path:
            raise PipelineFatalError(
                message="Cannot scan vulnerabilities: SBOM not generated",
                source=self.name,
            )

        if ctx.log_display:
            ctx.log_display.write(
                f"[{self.name}] Scanning SBOM for vulnerabilities..."
            )
            await asyncio.sleep(0)

        try:
            # Run Grype on SBOM file
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Running Grype...")
                await asyncio.sleep(0)
            
            # Run blocking subprocess call in executor
            loop = asyncio.get_event_loop()
            vuln_data = await loop.run_in_executor(
                None, scan_sbom, ctx.sbom.file_path
            )
            
            # Store raw JSON in context
            ctx.vulns = VulnReport(raw=vuln_data)

            # Build SBOM lookup maps for component linking
            purl_map: dict[str, str] = {}
            name_version_map: dict[tuple[str, str], str] = {}
            if ctx.sbom.raw:
                purl_map, name_version_map = _build_sbom_lookup_maps(ctx.sbom.raw)

            # Process vulnerabilities: deduplicate and create findings
            matches = vuln_data.get("matches", []) or []
            
            # Group matches by composite key (cve_id, package_name, package_version)
            vuln_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
            for match in matches:
                vulnerability = match.get("vulnerability", {})
                artifact = match.get("artifact", {})
                
                cve_id = vulnerability.get("id", "UNKNOWN")
                package_name = artifact.get("name", "unknown")
                package_version = artifact.get("version", "unknown")
                
                key = (cve_id, package_name, package_version)
                vuln_groups[key].append(match)

            # Create findings for unique vulnerabilities
            total_matches = len(matches)
            unique_vulns = len(vuln_groups)
            
            if ctx.log_display:
                ctx.log_display.write(
                    f"[{self.name}] Found {total_matches} vulnerability match(es), "
                    f"{unique_vulns} unique vulnerability(ies)"
                )
                await asyncio.sleep(0)

            # Count vulnerabilities by severity
            severity_counts: dict[str, int] = defaultdict(int)
            
            for key, match_list in vuln_groups.items():
                cve_id, package_name, package_version = key
                # Use first match for details (all matches in group have same CVE/package)
                match = match_list[0]
                vulnerability = match.get("vulnerability", {})
                artifact = match.get("artifact", {})
                
                # Map severity
                grype_severity = vulnerability.get("severity", "Unknown")
                severity = _map_grype_severity(grype_severity)
                severity_counts[severity] += 1
                
                # Extract fixed version
                fixed_version = _extract_fixed_version(match)
                
                # Find SBOM component
                bom_ref = _find_sbom_component(artifact, purl_map, name_version_map)
                
                # Get description
                description = vulnerability.get("description") or vulnerability.get("name") or "No description available"
                
                # Build message
                component_count = len(match_list)
                message_parts = [f"CVE-{cve_id}: {package_name}@{package_version}"]
                
                if fixed_version:
                    message_parts.append(f"(Fixed in {fixed_version})")
                
                if component_count > 1:
                    message_parts.append(f"- affects {component_count} component(s)")
                
                if bom_ref:
                    message_parts.append(f"[SBOM: {bom_ref}]")
                
                message_parts.append(f"- {description}")
                message = " ".join(message_parts)
                
                # Create finding
                finding = Finding(
                    source="grype",
                    message=message,
                    severity=severity,
                )
                ctx.findings.append(finding)

            # Display vulnerability summary
            if ctx.log_display:
                ctx.log_display.write_section("Vulnerability Summary", [])
                await asyncio.sleep(0)
                
                if unique_vulns > 0:
                    ctx.log_display.write(
                        f"[{self.name}] Total Unique Vulnerabilities: {unique_vulns}"
                    )
                    await asyncio.sleep(0)
                    
                    if total_matches != unique_vulns:
                        ctx.log_display.write(
                            f"[{self.name}] Total Matches: {total_matches} "
                            f"({total_matches - unique_vulns} duplicate(s))"
                        )
                        await asyncio.sleep(0)
                    
                    # Display counts by severity
                    severity_order = ["critical", "high", "medium", "low", "info"]
                    for sev in severity_order:
                        count = severity_counts.get(sev, 0)
                        if count > 0:
                            ctx.log_display.write(
                                f"[{self.name}] {sev.capitalize()}: {count}"
                            )
                            await asyncio.sleep(0)
                else:
                    ctx.log_display.write(
                        f"[{self.name}] No vulnerabilities found"
                    )
                    await asyncio.sleep(0)

            # Display detailed vulnerability list
            if unique_vulns > 0 and ctx.log_display:
                ctx.log_display.write_section("Vulnerability Details", [])
                await asyncio.sleep(0)
                
                # Group by severity for display
                vulns_by_severity: dict[str, list[tuple[tuple, dict]]] = defaultdict(list)
                for key, match_list in vuln_groups.items():
                    match = match_list[0]
                    vulnerability = match.get("vulnerability", {})
                    grype_severity = vulnerability.get("severity", "Unknown")
                    severity = _map_grype_severity(grype_severity)
                    vulns_by_severity[severity].append((key, match))
                
                # Display by severity (critical first)
                severity_order = ["critical", "high", "medium", "low", "info"]
                for sev in severity_order:
                    if sev not in vulns_by_severity:
                        continue
                    
                    vulns = vulns_by_severity[sev]
                    for key, match in vulns:
                        cve_id, package_name, package_version = key
                        vulnerability = match.get("vulnerability", {})
                        artifact = match.get("artifact", {})
                        
                        fixed_version = _extract_fixed_version(match)
                        bom_ref = _find_sbom_component(artifact, purl_map, name_version_map)
                        description = vulnerability.get("description") or vulnerability.get("name") or "No description"
                        component_count = len(vuln_groups[key])
                        
                        # Build detail line
                        detail_parts = [f"  [{sev.upper()}] CVE-{cve_id}"]
                        detail_parts.append(f"{package_name}@{package_version}")
                        
                        if fixed_version:
                            detail_parts.append(f"(Fixed in {fixed_version})")
                        else:
                            detail_parts.append("(No fix available)")
                        
                        if component_count > 1:
                            detail_parts.append(f"[affects {component_count} components]")
                        
                        if bom_ref:
                            detail_parts.append(f"[SBOM: {bom_ref}]")
                        
                        detail_line = " ".join(detail_parts)
                        
                        # Use write_error for critical/high, regular write for others
                        if sev in ["critical", "high"]:
                            ctx.log_display.write_error(detail_line)
                        else:
                            ctx.log_display.write(detail_line)
                        await asyncio.sleep(0)
                        
                        # Add description on next line if available
                        if description and description != "No description":
                            ctx.log_display.write(f"    {description[:100]}{'...' if len(description) > 100 else ''}")
                            await asyncio.sleep(0)

            # Add summary finding
            if unique_vulns > 0:
                ctx.findings.append(
                    Finding(
                        source=self.name,
                        message=f"Found {unique_vulns} unique vulnerability(ies) in SBOM",
                        severity="info",
                    )
                )
            else:
                ctx.findings.append(
                    Finding(
                        source=self.name,
                        message="No vulnerabilities found in SBOM",
                        severity="info",
                    )
                )

        except GrypeNotFoundError as e:
            # Grype not found - create finding but don't fail pipeline
            if ctx.log_display:
                ctx.log_display.write_error(
                    f"[{self.name}] WARNING: {str(e)}"
                )
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Grype not available: {str(e)}",
                    severity="critical",
                )
            )
            # Create empty vuln report
            ctx.vulns = VulnReport(raw={"matches": []})
        except GrypeError as e:
            # Grype scan failed - log warning and continue
            if ctx.log_display:
                ctx.log_display.write_error(
                    f"[{self.name}] WARNING: Vulnerability scan failed: {str(e)}"
                )
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Vulnerability scan failed: {str(e)}",
                    severity="warning",
                )
            )
            # Create empty vuln report
            ctx.vulns = VulnReport(raw={"matches": []})

        return ctx


# Auto-register this task
register(ScanVulnerabilities())

