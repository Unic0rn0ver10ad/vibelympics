"""Task to extract report data from context and structure it for PDF generation."""

import asyncio
from collections import defaultdict, deque

from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


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


def _analyze_sbom_structure(sbom_data: dict, ctx: Context = None) -> dict:
    """
    Analyze SBOM structure and return summary metrics using CycloneDX data.
    
    Args:
        sbom_data: CycloneDX SBOM dictionary
        ctx: Optional context for fallback to package metadata
    
    Returns:
        Dictionary with component and dependency metrics
    """
    components = sbom_data.get("components", []) or []
    dependencies = sbom_data.get("dependencies", []) or []

    # Build dependency graph from CycloneDX dependencies array
    deps_map = defaultdict(list)
    all_refs = set()
    children = set()
    for dep in dependencies:
        ref = dep.get("ref")
        if not ref:
            continue
        all_refs.add(ref)
        for child in dep.get("dependsOn", []) or []:
            deps_map[ref].append(child)
            children.add(child)
            all_refs.add(child)

    # roots = refs that are never a child
    roots = all_refs - children if all_refs else set()
    
    # Initialize metadata fallback variables
    use_metadata_fallback = False
    declared_deps_count = 0
    
    # When dependencies section is missing/empty, identify root components
    if not dependencies and components:
        # Find library/application components that aren't children
        for comp in components:
            bom_ref = comp.get("bom-ref")
            comp_type = comp.get("type", "").lower()
            if bom_ref and comp_type in ("library", "application", "framework"):
                if bom_ref not in children:
                    roots.add(bom_ref)
                    all_refs.add(bom_ref)
        
        # Fallback: Use package metadata requires_dist when dependency graph is empty
        if ctx and ctx.package and ctx.package.requires_dist:
            declared_deps = [d for d in ctx.package.requires_dist if d]
            declared_deps_count = len(declared_deps)
            if declared_deps_count > 0:
                use_metadata_fallback = True

    # BFS to compute depth and collect direct/transitive sets
    def bfs_depth(start: str) -> tuple[int, set[str], set[str]]:
        direct = set(deps_map.get(start, []))
        if not direct:
            return 0, direct, set()
        
        seen = {start}
        transitive = set()
        max_depth_local = 1
        queue = deque([(child, 2) for child in direct])
        seen.update(direct)
        while queue:
            node, depth = queue.popleft()
            max_depth_local = max(max_depth_local, depth)
            for nxt in deps_map.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    transitive.add(nxt)
                    queue.append((nxt, depth + 1))
        return max_depth_local, direct, transitive

    max_depth = 0
    direct_deps = set()
    transitive_deps = set()
    
    # If using metadata fallback, populate metrics from declared dependencies
    if use_metadata_fallback:
        max_depth = 1 if declared_deps_count > 0 else 0
    else:
        # Use CycloneDX dependency graph
        for root in roots or []:
            depth, direct, transitive = bfs_depth(root)
            max_depth = max(max_depth, depth)
            direct_deps.update(direct)
            transitive_deps.update(transitive)

    total_components = len(components)

    # Use metadata fallback counts if applicable
    if use_metadata_fallback:
        direct_deps_count = declared_deps_count
        transitive_deps_count = 0
    else:
        direct_deps_count = len(direct_deps)
        transitive_deps_count = len(transitive_deps)

    return {
        "total_components": total_components,
        "max_depth": max_depth,
        "direct_dependencies": direct_deps_count,
        "transitive_dependencies": transitive_deps_count,
    }


def _parse_vulnerabilities(vuln_data: dict) -> dict:
    """
    Parse vulnerability data and return summary.
    
    Args:
        vuln_data: Vulnerability data dictionary from Grype
    
    Returns:
        Dictionary with vulnerability metrics
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
    vulnerabilities_found = []
    
    for key, match_list in vuln_groups.items():
        match = match_list[0]
        vulnerability = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        
        grype_severity = vulnerability.get("severity", "Unknown")
        severity = _map_grype_severity(grype_severity)
        severity_counts[severity] += 1
        
        # Store unique vulnerability info
        vulnerabilities_found.append({
            "cve_id": vulnerability.get("id", "UNKNOWN"),
            "package_name": artifact.get("name", "unknown"),
            "package_version": artifact.get("version", "unknown"),
            "severity": severity,
        })
    
    return {
        "total_matches": total_matches,
        "unique_vulnerabilities": unique_count,
        "vulnerabilities_found": vulnerabilities_found if vulnerabilities_found else None,
        "high_severity": severity_counts.get("high", 0),
        "moderate_severity": severity_counts.get("medium", 0),
        "low_severity": severity_counts.get("low", 0),
    }


class ExtractReportData:
    """Task to extract report data from context and structure it for PDF generation."""

    name = "extract_report_data"

    def get_status_message(self, ctx: Context) -> str:
        return "Extract report data"

    async def run(self, ctx: Context) -> Context:
        """Extract report data from context and store in ctx.report_data."""
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Extracting report data...")
            await asyncio.sleep(0)

        report_data = {}

        # Extract Package Information
        report_data["package_name"] = ctx.package_name
        report_data["package_version"] = ctx.package.version if ctx.package and ctx.package.version else ctx.requested_version or "N/A"
        report_data["repo_name"] = ctx.repo_source if ctx.repo_source else "Unknown"
        
        # Get package URL (homepage or project URL)
        package_url = None
        if ctx.package and ctx.package.home_page:
            package_url = ctx.package.home_page
        elif ctx.package and ctx.package.project_urls:
            # Look for homepage or project URL in project_urls (case-insensitive)
            for key, url in ctx.package.project_urls.items():
                if key.lower() in ["homepage", "home", "project-url", "project", "documentation", "docs"]:
                    package_url = url
                    break
            # If still no URL found, use first available URL from project_urls
            if not package_url and ctx.package.project_urls:
                package_url = next(iter(ctx.package.project_urls.values()))
        elif ctx.download_info and ctx.download_info.url:
            # Fallback to download URL if no homepage available
            package_url = ctx.download_info.url
        
        # If still no URL, try to construct PyPI URL
        if not package_url and ctx.repo_source == "pypi":
            package_url = f"https://pypi.org/project/{ctx.package_name}/"
        
        report_data["package_url"] = package_url if package_url else "N/A"

        # Extract Repository Health
        repository_health = {}
        
        # Get repository URL
        repo_url = None
        if ctx.repo and ctx.repo.url:
            repo_url = ctx.repo.url
        elif ctx.package and ctx.package.project_urls:
            # Look for repository URL in project_urls
            for key, url in ctx.package.project_urls.items():
                if key.lower() in ["repository", "source", "code"]:
                    repo_url = url
                    break
        
        repository_health["repository"] = repo_url if repo_url else "None found"
        
        # Get license
        license_info = None
        if ctx.package and ctx.package.license:
            license_info = ctx.package.license
        repository_health["license"] = license_info if license_info else "No license found"
        
        # Get total releases
        total_releases = None
        if ctx.package and ctx.package.release_count is not None:
            total_releases = ctx.package.release_count
        repository_health["total_releases"] = total_releases
        
        report_data["repository_health"] = repository_health

        # Extract Components & Dependencies
        components_data = {}
        if ctx.sbom and ctx.sbom.raw:
            try:
                analysis = _analyze_sbom_structure(ctx.sbom.raw, ctx)
                components_data["total_components"] = analysis["total_components"]
                components_data["dependency_depth"] = analysis["max_depth"]
                components_data["direct_dependencies"] = analysis["direct_dependencies"]
                components_data["transitive_dependencies"] = analysis["transitive_dependencies"]
            except Exception as e:
                if ctx.log_display:
                    ctx.log_display.write_error(f"[{self.name}] WARNING: Failed to analyze SBOM: {e}")
                    await asyncio.sleep(0)
                components_data["total_components"] = None
                components_data["dependency_depth"] = None
                components_data["direct_dependencies"] = None
                components_data["transitive_dependencies"] = None
        else:
            components_data["total_components"] = None
            components_data["dependency_depth"] = None
            components_data["direct_dependencies"] = None
            components_data["transitive_dependencies"] = None
        
        report_data["components"] = components_data

        # Extract Known Vulnerabilities
        vulnerabilities_data = {}
        if ctx.vulns and ctx.vulns.raw:
            try:
                vuln_summary = _parse_vulnerabilities(ctx.vulns.raw)
                vulnerabilities_data["total_matches"] = vuln_summary["total_matches"]
                vulnerabilities_data["unique_vulnerabilities"] = vuln_summary["unique_vulnerabilities"]
                vulnerabilities_data["vulnerabilities_found"] = vuln_summary["vulnerabilities_found"]
                vulnerabilities_data["high_severity"] = vuln_summary["high_severity"]
                vulnerabilities_data["moderate_severity"] = vuln_summary["moderate_severity"]
                vulnerabilities_data["low_severity"] = vuln_summary["low_severity"]
            except Exception as e:
                if ctx.log_display:
                    ctx.log_display.write_error(f"[{self.name}] WARNING: Failed to parse vulnerabilities: {e}")
                    await asyncio.sleep(0)
                vulnerabilities_data["total_matches"] = "Unknown"
                vulnerabilities_data["unique_vulnerabilities"] = "Unknown"
                vulnerabilities_data["vulnerabilities_found"] = None
                vulnerabilities_data["high_severity"] = "Unknown"
                vulnerabilities_data["moderate_severity"] = "Unknown"
                vulnerabilities_data["low_severity"] = "Unknown"
        else:
            vulnerabilities_data["total_matches"] = "Unknown"
            vulnerabilities_data["unique_vulnerabilities"] = "Unknown"
            vulnerabilities_data["vulnerabilities_found"] = None
            vulnerabilities_data["high_severity"] = "Unknown"
            vulnerabilities_data["moderate_severity"] = "Unknown"
            vulnerabilities_data["low_severity"] = "Unknown"
        
        report_data["vulnerabilities"] = vulnerabilities_data

        # Store report data in context
        ctx.report_data = report_data

        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Report data extracted successfully")
            await asyncio.sleep(0)

        ctx.findings.append(
            Finding(
                source=self.name,
                message="Report data extracted for PDF generation",
                severity="info",
            )
        )

        return ctx


# Auto-register this task
register(ExtractReportData())

