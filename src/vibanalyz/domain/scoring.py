"""Risk scoring logic."""

from vibanalyz.domain.models import AuditResult


def compute_risk_score(result: AuditResult) -> int:
    """
    Compute a risk score for the audit result.
    
    This is a stub implementation that returns a fixed value.
    In the future, this will inspect findings and compute a real score.
    """
    return 42

