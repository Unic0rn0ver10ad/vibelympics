"""Domain models for package auditing."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PackageMetadata:
    """Package metadata from PyPI or other sources."""

    name: str
    version: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class RepoInfo:
    """Repository information."""

    url: Optional[str] = None


@dataclass
class Sbom:
    """Software Bill of Materials."""

    raw: Optional[dict] = None


@dataclass
class VulnReport:
    """Vulnerability report."""

    raw: Optional[dict] = None


@dataclass
class Finding:
    """A security finding from an analyzer."""

    source: str
    message: str
    severity: str  # "info" | "low" | "medium" | "high" | "critical"


@dataclass
class Context:
    """Shared context passed through tasks and analyzers."""

    package_name: str
    requested_version: Optional[str] = None
    package: Optional[PackageMetadata] = None
    repo: Optional[RepoInfo] = None
    sbom: Optional[Sbom] = None
    vulns: Optional[VulnReport] = None
    findings: list[Finding] = field(default_factory=list)


@dataclass
class AuditResult:
    """Final result of the audit pipeline."""

    ctx: Context
    score: int
    pdf_path: Optional[str] = None

