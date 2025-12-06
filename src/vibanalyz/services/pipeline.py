"""Main audit pipeline."""

from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import AuditResult, Context, Finding
from vibanalyz.domain.scoring import compute_risk_score
from vibanalyz.services.reporting import write_pdf_report
from vibanalyz.services.tasks import get_task

# Define task chains for different repo sources
# Each chain is a list of task names that will be resolved from the registry
CHAINS = {
    "pypi": [
        "fetch_pypi",
        "run_analyses",
    ],
    "npm": [
        "fetch_npm",
        "run_analyses",
    ],
}


def run_pipeline(ctx: Context) -> AuditResult:
    """
    Run the audit pipeline.
    
    Args:
        ctx: Initial context with package_name and repo_source set
    
    Returns:
        AuditResult with score and PDF path
    
    Raises:
        ValueError: If repo_source is invalid or chain is not found
    """
    # Validate repo_source
    if not ctx.repo_source:
        raise ValueError("repo_source must be set in context")
    
    if ctx.repo_source not in CHAINS:
        raise ValueError(
            f"Unknown repo_source: {ctx.repo_source}. "
            f"Available sources: {list(CHAINS.keys())}"
        )
    
    # Get the task chain for this repo source
    task_names = CHAINS[ctx.repo_source]
    
    # Build task sequence by resolving task names from registry
    tasks = []
    missing_tasks = []
    for task_name in task_names:
        task = get_task(task_name)
        if task is None:
            missing_tasks.append(task_name)
        else:
            tasks.append(task)
    
    # Handle missing tasks
    if missing_tasks:
        error_msg = f"Missing tasks in registry: {', '.join(missing_tasks)}"
        ctx.findings.append(
            Finding(
                source="pipeline",
                message=error_msg,
                severity="critical",
            )
        )
        raise ValueError(error_msg)
    
    # Run each task in order
    for task in tasks:
        # Update status bar before task starts
        if ctx.status_bar:
            status_msg = task.get_status_message(ctx)
            ctx.status_bar.update(status_msg)
        
        try:
            # Run task (task can use ctx.log_display for detailed logging)
            ctx = task.run(ctx)
        except PipelineFatalError as e:
            # Fatal error - stop pipeline execution
            if ctx.log_display:
                ctx.log_display.write(f"[pipeline] FATAL ERROR: {e.message}")
            ctx.findings.append(
                Finding(
                    source=e.source or "pipeline",
                    message=e.message,
                    severity="critical",
                )
            )
            # Return partial result immediately
            result = AuditResult(ctx=ctx, score=0)
            result.score = compute_risk_score(result)
            return result
    
    # Compute score
    result = AuditResult(ctx=ctx, score=0)
    result.score = compute_risk_score(result)
    
    # Generate PDF report
    pdf_path = write_pdf_report(result)
    result.pdf_path = str(pdf_path)
    
    return result

