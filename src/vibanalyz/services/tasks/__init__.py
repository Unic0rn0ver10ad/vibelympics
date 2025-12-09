"""Pipeline tasks."""

from typing import Dict, List, Optional

from vibanalyz.domain.protocols import Task

_TASKS: Dict[str, Task] = {}


def register(task: Task) -> None:
    """Register a task by name."""
    _TASKS[task.name] = task


def get_task(name: str) -> Optional[Task]:
    """Retrieve a task by name."""
    return _TASKS.get(name)


def all_tasks() -> List[Task]:
    """Get all registered tasks."""
    return list(_TASKS.values())


# Import all task modules to trigger auto-registration
from vibanalyz.services.tasks import (  # noqa: E402, F401
    download_pypi,
    fetch_npm,
    fetch_pypi,
    generate_pdf_report,
    generate_sbom,
    run_analyses,
)

