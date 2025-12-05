"""Main audit pipeline."""

from vibanalyz.domain.models import AuditResult, Context
from vibanalyz.domain.scoring import compute_risk_score
from vibanalyz.services.reporting import write_pdf_report
from vibanalyz.services.tasks.fetch_pypi import FetchPyPi
from vibanalyz.services.tasks.run_analyses import RunAnalyses

# Define the task pipeline
TASKS = [
    FetchPyPi(),
    RunAnalyses(),
]


def run_pipeline(ctx: Context) -> AuditResult:
    """
    Run the audit pipeline.
    
    Args:
        ctx: Initial context with package_name set
    
    Returns:
        AuditResult with score and PDF path
    """
    # Run each task in order
    for task in TASKS:
        ctx = task.run(ctx)
    
    # Compute score
    result = AuditResult(ctx=ctx, score=0)
    result.score = compute_risk_score(result)
    
    # Generate PDF report
    pdf_path = write_pdf_report(result)
    result.pdf_path = str(pdf_path)
    
    return result

