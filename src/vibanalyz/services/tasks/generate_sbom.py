"""Task to generate SBOM using Syft."""

import asyncio
import json
from collections import defaultdict, deque
from pathlib import Path

from vibanalyz.adapters.syft_client import (
    SyftError,
    SyftNotFoundError,
    generate_sbom,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding, Sbom
from vibanalyz.domain.protocols import Task
from vibanalyz.services.artifacts import get_artifacts_dir, get_host_hint
from vibanalyz.services.tasks import register


def _analyze_sbom_structure(sbom_data: dict, ctx: Context = None) -> dict:
    """
    Analyze SBOM structure and return summary metrics using CycloneDX data.
    
    Args:
        sbom_data: CycloneDX SBOM dictionary
        ctx: Optional context for fallback to package metadata
    """
    components = sbom_data.get("components", []) or []
    dependencies = sbom_data.get("dependencies", []) or []

    # Build lookups
    component_types = defaultdict(int)
    licenses = set()
    component_by_ref = {}  # bom-ref -> component
    for comp in components:
        bom_ref = comp.get("bom-ref")
        if bom_ref:
            component_by_ref[bom_ref] = comp
        comp_type = comp.get("type", "unknown")
        component_types[comp_type] += 1
        for lic in comp.get("licenses", []) or []:
            if isinstance(lic, dict):
                lic_id = lic.get("license", {}).get("id") or lic.get("license", {}).get("name")
                if lic_id:
                    licenses.add(lic_id)
            elif isinstance(lic, str):
                licenses.add(lic)

    # Build dependency graph from CycloneDX dependencies array
    # deps_map: parent_ref -> list(child_refs)
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
    
    # Initialize metadata fallback variables (used later regardless of dependencies)
    use_metadata_fallback = False
    declared_deps_count = 0
    
    # FIX: When dependencies section is missing/empty, identify root components
    # as library/application type components (exclude file types)
    if not dependencies and components:
        # Find library/application components that aren't children
        for comp in components:
            bom_ref = comp.get("bom-ref")
            comp_type = comp.get("type", "").lower()
            # Only consider library/application types as potential roots
            if bom_ref and comp_type in ("library", "application", "framework"):
                if bom_ref not in children:
                    roots.add(bom_ref)
                    all_refs.add(bom_ref)
        
        # Fallback: Use package metadata requires_dist when dependency graph is empty
        if ctx and ctx.package and ctx.package.requires_dist:
            # Count declared dependencies (filter out empty/None entries)
            declared_deps = [d for d in ctx.package.requires_dist if d]
            declared_deps_count = len(declared_deps)
            if declared_deps_count > 0:
                # Use metadata fallback when we have declared deps but no graph
                use_metadata_fallback = True

    # BFS to compute depth and collect direct/transitive sets
    def bfs_depth(start: str) -> tuple[int, set[str], set[str]]:
        direct = set(deps_map.get(start, []))
        if not direct:
            # No dependencies - depth is 0
            return 0, direct, set()
        
        seen = {start}
        transitive = set()
        # Start with depth 1 for direct dependencies
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
        # Direct dependencies = count of declared dependencies
        # We can't know transitive without resolution, so set to 0
        # Depth = 1 if there are any declared dependencies (they're direct, but we don't know their depth)
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
        transitive_deps_count = 0  # Unknown without resolution
    else:
        direct_deps_count = len(direct_deps)
        transitive_deps_count = len(transitive_deps)

    return {
        "total_components": total_components,
        "max_depth": max_depth,
        "direct_dependencies": direct_deps_count,
        "transitive_dependencies": transitive_deps_count,
        "root_components": len(roots),
        "component_types": dict(component_types),
        "unique_licenses": len(licenses),
        "relationship_types": {"cyclonedx_dependencies": len(dependencies)},
    }


def _calculate_max_depth(root_id: str, parent_to_children: dict, visited: set = None) -> int:
    """
    Calculate maximum depth from a root component using BFS.
    
    Args:
        root_id: Starting component ID
        parent_to_children: Mapping of parent to children
        visited: Set of visited nodes (for cycle detection)
        
    Returns:
        Maximum depth from root
    """
    if visited is None:
        visited = set()
    
    if root_id in visited:
        return 0  # Cycle detected
    
    visited.add(root_id)
    children = parent_to_children.get(root_id, [])
    
    if not children:
        return 1  # Leaf node
    
    max_child_depth = 0
    for child_id in children:
        child_depth = _calculate_max_depth(child_id, parent_to_children, visited.copy())
        max_child_depth = max(max_child_depth, child_depth)
    
    return 1 + max_child_depth


class GenerateSbom:
    """Task to generate SBOM from downloaded package artifact."""

    name = "generate_sbom"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return "Generate SBOM"

    async def run(self, ctx: Context) -> Context:
        """Generate SBOM and update context."""
        # Status is updated by pipeline before task runs
        if not ctx.download_info or not ctx.download_info.local_path:
            raise PipelineFatalError(
                message="Cannot generate SBOM: package artifact not downloaded",
                source=self.name,
            )

        if ctx.log_display:
            ctx.log_display.write(
                f"[{self.name}] Generating SBOM for {ctx.download_info.filename}"
            )
            await asyncio.sleep(0)

        try:
            # Run Syft to generate SBOM
            if ctx.log_display:
                ctx.log_display.write_with_spinner(f"[{self.name}] Running Syft...", spinner_style="dots")
                await asyncio.sleep(0)
            
            # Run blocking subprocess call in executor
            loop = asyncio.get_event_loop()
            sbom_data = await loop.run_in_executor(
                None, generate_sbom, ctx.download_info.local_path
            )
            
            # Write completion message (replaces spinner)
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Syft completed")
                await asyncio.sleep(0)
            
            # Save SBOM to JSON file (shared artifacts directory)
            output_dir = get_artifacts_dir()
            
            # Generate filename matching PDF report pattern
            version_suffix = ""
            if ctx.package and ctx.package.version:
                version_suffix = f"-{ctx.package.version}"
            filename = f"vibanalyz-{ctx.package_name}{version_suffix}-sbom.json"
            sbom_file_path = output_dir / filename
            
            # Write SBOM to file (run blocking I/O in executor)
            loop = asyncio.get_event_loop()
            def _write_sbom_file():
                try:
                    with open(sbom_file_path, "w", encoding="utf-8") as f:
                        json.dump(sbom_data, f, indent=2)
                    return str(sbom_file_path.resolve())
                except Exception as e:
                    if ctx.log_display:
                        # Note: Can't await here in sync function, will handle after
                        pass
                    raise e
            
            try:
                sbom_file_path_str = await loop.run_in_executor(None, _write_sbom_file)
            except Exception as e:
                sbom_file_path_str = None
                if ctx.log_display:
                    ctx.log_display.write(
                        f"[{self.name}] WARNING: Failed to save SBOM file: {e}"
                    )
                    await asyncio.sleep(0)
            
            # Store SBOM in context with file path
            ctx.sbom = Sbom(raw=sbom_data, file_path=sbom_file_path_str)

            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] SBOM generated successfully")
                await asyncio.sleep(0)
                
                if sbom_file_path_str:
                    ctx.log_display.write(
                        f"[{self.name}] SBOM saved to: {sbom_file_path_str}"
                    )
                    await asyncio.sleep(0)
                    host_hint = get_host_hint(output_dir)
                    if host_hint:
                        ctx.log_display.write(
                            f"[{self.name}] Host path hint: {host_hint}"
                        )
                        await asyncio.sleep(0)
                
                # Add separator section
                ctx.log_display.write_section("SBOM Information", [])
                await asyncio.sleep(0)
                
                # Analyze and display SBOM summary
                if isinstance(sbom_data, dict):
                    analysis = _analyze_sbom_structure(sbom_data, ctx)
                    
                    # Check for empty SBOM
                    total_components = analysis['total_components']
                    if total_components == 0:
                        # Empty SBOM detected - this is a problem
                        warning_msg = (
                            f"WARNING: SBOM is empty (0 components found). "
                            f"This may indicate an issue with SBOM generation. "
                            f"Vulnerability scanning will have no components to analyze."
                        )
                        if ctx.log_display:
                            ctx.log_display.write_error(f"[{self.name}] {warning_msg}")
                            await asyncio.sleep(0)
                        ctx.findings.append(
                            Finding(
                                source=self.name,
                                message=warning_msg,
                                severity="warning",
                            )
                        )
                    
                    # Display summary metrics
                    ctx.log_display.write(
                        f"[{self.name}] Total Components: {total_components}"
                    )
                    await asyncio.sleep(0)
                    ctx.log_display.write(
                        f"[{self.name}] Dependency Depth: {analysis['max_depth']} level(s)"
                    )
                    await asyncio.sleep(0)
                    ctx.log_display.write(
                        f"[{self.name}] Direct Dependencies: {analysis['direct_dependencies']}"
                    )
                    await asyncio.sleep(0)
                    ctx.log_display.write(
                        f"[{self.name}] Transitive Dependencies: {analysis['transitive_dependencies']}"
                    )
                    await asyncio.sleep(0)
                    ctx.log_display.write(
                        f"[{self.name}] Root Components: {analysis['root_components']}"
                    )
                    await asyncio.sleep(0)
                    
                    # Component types
                    if analysis['component_types']:
                        type_summary = ", ".join(
                            [f"{count} {atype}" for atype, count in analysis['component_types'].items()]
                        )
                        ctx.log_display.write(
                            f"[{self.name}] Component Types: {type_summary}"
                        )
                        await asyncio.sleep(0)
                    
                    # Licenses
                    if analysis['unique_licenses'] > 0:
                        ctx.log_display.write(
                            f"[{self.name}] Unique Licenses: {analysis['unique_licenses']}"
                        )
                        await asyncio.sleep(0)
                    
                    # Schema version (CycloneDX uses specVersion at top level)
                    schema_version = sbom_data.get("specVersion", "unknown")
                    ctx.log_display.write(
                        f"[{self.name}] SBOM Schema Version: {schema_version}"
                    )
                    await asyncio.sleep(0)
                    
                    # Tool info (Syft version, timestamp) - CycloneDX uses metadata.tools
                    metadata = sbom_data.get("metadata", {})
                    tools = metadata.get("tools", {}) if metadata else {}
                    tool_components = tools.get("components", []) if isinstance(tools, dict) else []
                    syft_version = "unknown"
                    timestamp = metadata.get("timestamp", "unknown") if metadata else "unknown"
                    if tool_components:
                        # Find syft tool
                        for tool in tool_components:
                            if isinstance(tool, dict) and tool.get("name", "").lower() == "syft":
                                syft_version = tool.get("version", "unknown")
                                break
                    ctx.log_display.write(
                        f"[{self.name}] Generated by Syft {syft_version} at {timestamp}"
                    )
                    await asyncio.sleep(0)
                    
                    # SBOM size (approximate)
                    sbom_size = len(json.dumps(sbom_data))
                    size_kb = sbom_size / 1024
                    ctx.log_display.write(
                        f"[{self.name}] SBOM Size: {size_kb:.2f} KB"
                    )
                    await asyncio.sleep(0)

            ctx.findings.append(
                Finding(
                    source=self.name,
                    message="SBOM generated successfully",
                    severity="info",
                )
            )

        except SyftNotFoundError as e:
            # Fatal error - Syft is required
            if ctx.log_display:
                ctx.log_display.write_error(f"[{self.name}] ERROR: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="critical",
                )
            )
            raise PipelineFatalError(
                message=f"SBOM generation failed: {str(e)}",
                source=self.name,
            )
        except SyftError as e:
            # Fatal error - SBOM generation failed
            if ctx.log_display:
                # Clear spinner and show error
                ctx.log_display.write_error(f"[{self.name}] ERROR: {str(e)}")
                await asyncio.sleep(0)
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"SBOM generation failed: {str(e)}",
                    severity="critical",
                )
            )
            raise PipelineFatalError(
                message=f"SBOM generation failed: {str(e)}",
                source=self.name,
            )

        return ctx


# Auto-register this task
register(GenerateSbom())
