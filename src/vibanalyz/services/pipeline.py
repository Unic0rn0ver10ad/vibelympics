"""Main audit pipeline."""

import asyncio
import time

from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import AuditResult, Context, Finding
from vibanalyz.domain.scoring import compute_risk_score
from vibanalyz.services.artifacts import get_artifacts_dir
from vibanalyz.services.tasks import get_task

# Define task chains for different repo sources
# Each chain is a list of task names that will be resolved from the registry
CHAINS = {
    "pypi": [
        "fetch_pypi",
        "download_pypi",
        "generate_sbom",
        "scan_vulnerabilities",
        "run_analyses",
        "extract_report_data",
        "generate_pdf_report",
    ],
    "npm": [
        "fetch_npm",
        "download_npm",
        "generate_sbom",
        "scan_vulnerabilities",
        "run_analyses",
        "extract_report_data",
        "generate_pdf_report",
    ],
    "rust": [
        "fetch_rust",
        "download_rust",
        "generate_sbom",
        "scan_vulnerabilities",
        "run_analyses",
        "extract_report_data",
        "generate_pdf_report",
    ],
}


def get_task_chain(repo_source: str) -> list[str]:
    """
    Get the task chain for a repository source.
    
    Args:
        repo_source: Repository source (e.g., "pypi", "npm")
    
    Returns:
        List of task names in the chain
    
    Raises:
        ValueError: If repo_source is invalid
    """
    if repo_source not in CHAINS:
        raise ValueError(
            f"Unknown repo_source: {repo_source}. "
            f"Available sources: {list(CHAINS.keys())}"
        )
    return CHAINS[repo_source]


def get_task_status_messages(
    repo_source: str, task_name: str, ctx: Context
) -> tuple[str, str, str]:
    """
    Get previous, current, and next task status messages.
    
    Args:
        repo_source: Repository source (e.g., "pypi", "npm")
        task_name: Current task name
        ctx: Context for generating status messages
    
    Returns:
        Tuple of (previous_status, current_status, next_status)
    """
    try:
        task_chain = get_task_chain(repo_source)
        if task_name not in task_chain:
            # Task not in chain, return current only
            current_task = get_task(task_name)
            current_status = (
                current_task.get_status_message(ctx) if current_task else task_name
            )
            return ("", current_status, "")
        
        task_index = task_chain.index(task_name)
        previous_task_name = task_chain[task_index - 1] if task_index > 0 else None
        next_task_name = (
            task_chain[task_index + 1] if task_index < len(task_chain) - 1 else None
        )
        
        # Get current status
        current_task = get_task(task_name)
        current_status = (
            current_task.get_status_message(ctx) if current_task else task_name
        )
        
        # Get previous status
        previous_status = ""
        if previous_task_name:
            prev_task = get_task(previous_task_name)
            if prev_task:
                previous_status = prev_task.get_status_message(ctx)
        
        # Get next status
        next_status = ""
        if next_task_name:
            next_task = get_task(next_task_name)
            if next_task:
                next_status = next_task.get_status_message(ctx)
        
        return (previous_status, current_status, next_status)
    except Exception:
        # Fallback: just return current
        current_task = get_task(task_name)
        current_status = (
            current_task.get_status_message(ctx) if current_task else task_name
        )
        return ("", current_status, "")


async def run_pipeline(ctx: Context) -> AuditResult:
    """
    Run the audit pipeline asynchronously.
    
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
    
    # Execute all tasks in sequence with timing
    # Each task is timed individually and displays its completion time
    for index, task in enumerate(tasks):
        task_start_time = time.perf_counter()
        status_msg = task.get_status_message(ctx)
        
        try:
            # Write task section header before running the task
            if ctx.log_display:
                ctx.log_display.set_mode("task")
                ctx.log_display.write_task_section(status_msg)
                # Yield control to event loop after log write
                await asyncio.sleep(0)

            # Run task (task writes to log_display, status already updated by pipeline)
            # Support both async and sync tasks
            result = task.run(ctx)
            if asyncio.iscoroutine(result):
                ctx = await result
            else:
                ctx = result
            
            # Calculate task execution time
            task_end_time = time.perf_counter()
            task_duration = task_end_time - task_start_time
            
            # Log task completion with timing (all tasks are timed)
            if ctx.log_display:
                ctx.log_display.set_mode("task")
                ctx.log_display.write(
                    f"{status_msg} completed successfully in {task_duration:.1f} seconds"
                )
                await asyncio.sleep(0)
            
            # Yield control after each task to allow UI updates
            await asyncio.sleep(0)
        except PipelineFatalError as e:
            # Calculate task execution time even on failure
            task_end_time = time.perf_counter()
            task_duration = task_end_time - task_start_time
            
            # Log task failure with timing (in red)
            if ctx.log_display:
                ctx.log_display.write_error(
                    f"{status_msg} failed after {task_duration:.1f} seconds"
                )
                await asyncio.sleep(0)
            
            # Fatal error - stop pipeline execution
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

    # Compute score and hydrate result (PDF now generated in dedicated task)
    result = AuditResult(ctx=ctx, score=0)
    result.score = compute_risk_score(result)
    result.pdf_path = ctx.report_path

    return result

