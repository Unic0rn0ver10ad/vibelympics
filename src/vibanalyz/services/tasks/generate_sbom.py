"""Task to generate SBOM using Syft."""

import json
from collections import defaultdict
from pathlib import Path

from vibanalyz.adapters.syft_client import (
    SyftError,
    SyftNotFoundError,
    generate_sbom,
)
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding, Sbom
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


def _analyze_sbom_structure(sbom_data: dict) -> dict:
    """
    Analyze SBOM structure and return summary metrics.
    
    Args:
        sbom_data: The SBOM data dictionary from Syft
        
    Returns:
        Dictionary with analysis metrics
    """
    artifacts = sbom_data.get("artifacts", [])
    relationships = sbom_data.get("artifactRelationships", [])
    
    # Basic counts
    total_components = len(artifacts) if artifacts else 0
    
    # Component types breakdown
    type_counts = defaultdict(int)
    licenses = set()
    for artifact in artifacts:
        artifact_type = artifact.get("type", "unknown")
        type_counts[artifact_type] += 1
        
        # Collect licenses
        artifact_licenses = artifact.get("licenses", [])
        if artifact_licenses:
            for license_info in artifact_licenses:
                if isinstance(license_info, str):
                    licenses.add(license_info)
                elif isinstance(license_info, dict):
                    licenses.add(license_info.get("value", "unknown"))
    
    # Build dependency graph
    # Map: child_id -> list of parent_ids
    child_to_parents = defaultdict(list)
    # Map: parent_id -> list of child_ids
    parent_to_children = defaultdict(list)
    
    for rel in relationships:
        parent_id = rel.get("parent")
        child_id = rel.get("child")
        rel_type = rel.get("type", "")
        
        if parent_id and child_id and rel_type == "dependsOn":
            child_to_parents[child_id].append(parent_id)
            parent_to_children[parent_id].append(child_id)
    
    # Find root components (no incoming relationships)
    all_component_ids = {artifact.get("id") for artifact in artifacts if artifact.get("id")}
    components_with_parents = set(child_to_parents.keys())
    root_components = all_component_ids - components_with_parents
    
    # Calculate dependency depth using BFS from root components
    max_depth = 0
    if root_components and parent_to_children:
        for root_id in root_components:
            depth = _calculate_max_depth(root_id, parent_to_children)
            max_depth = max(max_depth, depth)
    
    # Count direct vs transitive dependencies
    # Direct: components that are children of root components
    direct_deps = set()
    for root_id in root_components:
        direct_deps.update(parent_to_children.get(root_id, []))
    
    # Transitive: all other components with parents
    transitive_deps = components_with_parents - direct_deps
    
    # Relationship types breakdown
    rel_type_counts = defaultdict(int)
    for rel in relationships:
        rel_type = rel.get("type", "unknown")
        rel_type_counts[rel_type] += 1
    
    return {
        "total_components": total_components,
        "max_depth": max_depth,
        "direct_dependencies": len(direct_deps),
        "transitive_dependencies": len(transitive_deps),
        "root_components": len(root_components),
        "component_types": dict(type_counts),
        "unique_licenses": len(licenses),
        "relationship_types": dict(rel_type_counts),
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
        return f"Generating SBOM for {ctx.package_name}."

    def run(self, ctx: Context) -> Context:
        """Generate SBOM and update context."""
        if not ctx.download_info or not ctx.download_info.local_path:
            raise PipelineFatalError(
                message="Cannot generate SBOM: package artifact not downloaded",
                source=self.name,
            )

        if ctx.log_display:
            ctx.log_display.write(
                f"[{self.name}] Generating SBOM for {ctx.download_info.filename}"
            )

        try:
            # Run Syft to generate SBOM
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Running Syft...")
            
            sbom_data = generate_sbom(ctx.download_info.local_path)
            
            # Save SBOM to JSON file (same directory as PDF reports)
            output_dir = Path.cwd()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename matching PDF report pattern
            version_suffix = ""
            if ctx.package and ctx.package.version:
                version_suffix = f"-{ctx.package.version}"
            filename = f"vibanalyz-{ctx.package_name}{version_suffix}-sbom.json"
            sbom_file_path = output_dir / filename
            
            # Write SBOM to file
            try:
                with open(sbom_file_path, "w", encoding="utf-8") as f:
                    json.dump(sbom_data, f, indent=2)
                sbom_file_path_str = str(sbom_file_path.resolve())
            except Exception as e:
                sbom_file_path_str = None
                if ctx.log_display:
                    ctx.log_display.write(
                        f"[{self.name}] WARNING: Failed to save SBOM file: {e}"
                    )
            
            # Store SBOM in context with file path
            ctx.sbom = Sbom(raw=sbom_data, file_path=sbom_file_path_str)

            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] SBOM generated successfully")
                
                if sbom_file_path_str:
                    ctx.log_display.write(
                        f"[{self.name}] SBOM saved to: {sbom_file_path_str}"
                    )
                
                # Add separator section
                ctx.log_display.write_section("SBOM Information", [])
                
                # Analyze and display SBOM summary
                if isinstance(sbom_data, dict):
                    analysis = _analyze_sbom_structure(sbom_data)
                    
                    # Display summary metrics
                    ctx.log_display.write(
                        f"[{self.name}] Total Components: {analysis['total_components']}"
                    )
                    ctx.log_display.write(
                        f"[{self.name}] Dependency Depth: {analysis['max_depth']} level(s)"
                    )
                    ctx.log_display.write(
                        f"[{self.name}] Direct Dependencies: {analysis['direct_dependencies']}"
                    )
                    ctx.log_display.write(
                        f"[{self.name}] Transitive Dependencies: {analysis['transitive_dependencies']}"
                    )
                    ctx.log_display.write(
                        f"[{self.name}] Root Components: {analysis['root_components']}"
                    )
                    
                    # Component types
                    if analysis['component_types']:
                        type_summary = ", ".join(
                            [f"{count} {atype}" for atype, count in analysis['component_types'].items()]
                        )
                        ctx.log_display.write(
                            f"[{self.name}] Component Types: {type_summary}"
                        )
                    
                    # Licenses
                    if analysis['unique_licenses'] > 0:
                        ctx.log_display.write(
                            f"[{self.name}] Unique Licenses: {analysis['unique_licenses']}"
                        )
                    
                    # Schema version
                    schema = sbom_data.get("schema", {})
                    schema_version = schema.get("version", "unknown")
                    ctx.log_display.write(
                        f"[{self.name}] SBOM Schema Version: {schema_version}"
                    )
                    
                    # Descriptor info (Syft version, timestamp)
                    descriptor = sbom_data.get("descriptor", {})
                    if descriptor:
                        syft_version = descriptor.get("version", "unknown")
                        timestamp = descriptor.get("timestamp", "unknown")
                        ctx.log_display.write(
                            f"[{self.name}] Generated by Syft {syft_version} at {timestamp}"
                        )
                    
                    # SBOM size (approximate)
                    sbom_size = len(json.dumps(sbom_data))
                    size_kb = sbom_size / 1024
                    ctx.log_display.write(
                        f"[{self.name}] SBOM Size: {size_kb:.2f} KB"
                    )

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
                ctx.log_display.write(f"[{self.name}] ERROR: {str(e)}")
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
                ctx.log_display.write(f"[{self.name}] ERROR: {str(e)}")
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
