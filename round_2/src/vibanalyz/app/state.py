"""Application state management."""

from dataclasses import dataclass

from vibanalyz.domain.models import AuditResult


@dataclass
class AppState:
    """Application state."""

    has_run_audit: bool = False
    current_package: str | None = None
    current_version: str | None = None
    audit_result: AuditResult | None = None

    def mark_audit_complete(
        self, package: str, version: str | None, result: AuditResult
    ) -> None:
        """Update state after audit completion."""
        self.has_run_audit = True
        self.current_package = package
        self.current_version = version
        self.audit_result = result

    def reset(self) -> None:
        """Reset state to initial values."""
        self.has_run_audit = False
        self.current_package = None
        self.current_version = None
        self.audit_result = None

