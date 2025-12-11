# Pipeline Task Architecture Guide

## Overview

The vibanalyz pipeline uses a **task-based architecture** where individual tasks are isolated, independently modifiable units that execute in sequence. Tasks are organized into **chains** that vary based on the repository source (PyPI, NPM, etc.).

## Core Principles

1. **Task Isolation**: Each task is in its own file and can be modified independently
2. **Registry System**: Tasks auto-register themselves via a registry
3. **Chain Configuration**: Task execution order is defined in `pipeline.py` via the `CHAINS` dictionary
4. **Context Passing**: Tasks communicate through a shared `Context` object
5. **Fatal Error Handling**: Tasks can raise `PipelineFatalError` to terminate the pipeline early

## Architecture Components

### Task Registry (`services/tasks/__init__.py`)

Tasks are registered in a central registry that maps task names to task instances:

```python
_TASKS: Dict[str, Task] = {}

def register(task: Task) -> None:
    """Register a task by name."""
    _TASKS[task.name] = task

def get_task(name: str) -> Optional[Task]:
    """Retrieve a task by name."""
    return _TASKS.get(name)
```

### Task Protocol (`domain/protocols.py`)

All tasks must conform to the `Task` protocol:

```python
class Task(Protocol):
    name: str
    
    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        ...
    
    def run(self, ctx: Context) -> Context:
        """Run the task and return updated context."""
        ...
```

### Chain Configuration (`services/pipeline.py`)

Task execution order is defined in the `CHAINS` dictionary:

```python
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
```

## Creating a New Task

### Step 1: Create Task File

Create a new file in `services/tasks/` with a descriptive name (e.g., `fetch_npm.py`, `clone_repo.py`).

### Step 2: Implement Task Class

```python
"""Task to [describe what this task does]."""

from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class FetchNpm:
    """Task to fetch package metadata from NPM."""

    name = "fetch_npm"  # Must match the name used in CHAINS

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return f"Contacting NPM repo for {ctx.package_name} module."

    def run(self, ctx: Context) -> Context:
        """Execute the task and return updated context."""
        # Log start of operation
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Starting operation...")
        
        try:
            # Perform task operations
            # Update ctx as needed (e.g., ctx.package, ctx.sbom, etc.)
            
            # Log success
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Operation completed successfully")
            
            # Add findings if appropriate
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message="Operation completed",
                    severity="info",
                )
            )
        except SomeFatalError as e:
            # For fatal errors that should stop the pipeline
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] ERROR: {str(e)}")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="critical",
                )
            )
            # Raise fatal error to stop pipeline
            raise PipelineFatalError(
                message=f"Fatal error: {str(e)}",
                source=self.name
            )
        except SomeRecoverableError as e:
            # For recoverable errors, just add finding and continue
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] WARNING: {str(e)}")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=str(e),
                    severity="warning",
                )
            )
        
        return ctx


# Auto-register this task
register(FetchNpm())
```

### Step 3: Import Task Module

Add the import to `services/tasks/__init__.py` to trigger auto-registration:

```python
# Import all task modules to trigger auto-registration
from vibanalyz.services.tasks import fetch_pypi, run_analyses, fetch_npm  # noqa: E402, F401
```

### Step 4: Add to Chain Configuration

Update `CHAINS` in `services/pipeline.py` to include your task in the appropriate chain(s):

```python
CHAINS = {
    "pypi": [
        "fetch_pypi",
        "run_analyses",
    ],
    "npm": [
        "fetch_npm",  # Add your new task here
        "run_analyses",
    ],
}
```

## Task Implementation Guidelines

### Required Methods

1. **`name`**: Class attribute (string) - Must be unique and match the name used in `CHAINS`
2. **`get_status_message(ctx: Context) -> str`**: Returns the status bar message shown when this task starts
3. **`run(ctx: Context) -> Context`**: Executes the task logic and returns updated context

### Status Messages

- Use format: `"<Action> for {ctx.package_name} module."` or similar
- Be concise and descriptive
- Include the package name from context
- Example: `"Contacting PyPI repo for {ctx.package_name} module."`

### Logging

- Always check `if ctx.log_display:` before logging
- Use format: `f"[{self.name}] <message>"`
- Log important steps, progress, and errors
- Never clear the log (only append)

### Error Handling

**Fatal Errors** (stop pipeline):
- Use `PipelineFatalError` exception
- Examples: Package not found, critical configuration missing
- Add critical finding before raising

**Recoverable Errors** (continue pipeline):
- Catch exception, log warning, add finding
- Examples: Network timeouts, optional data missing
- Use appropriate severity (warning, info)

### Context Updates

- Read from `ctx` to get input data
- Update `ctx` fields to pass data to subsequent tasks
- Add `Finding` objects to `ctx.findings` for reporting
- Never modify other tasks' data structures directly

## Modifying Existing Tasks

### What You CAN Modify

1. **The task file itself** (`services/tasks/<task_name>.py`)
   - Update `run()` method logic
   - Update `get_status_message()` method
   - Add new error handling
   - Improve logging

2. **Pipeline chain configuration** (`services/pipeline.py`)
   - Add/remove tasks from chains
   - Reorder tasks within a chain
   - Add new chains for new repo sources

### What You MUST NOT Modify

1. **Other task files** - Only modify the task you're working on
2. **Task protocol** (`domain/protocols.py`) - Do not change the interface
3. **Task registry** (`services/tasks/__init__.py`) - Only add imports, don't change registry logic
4. **Pipeline execution logic** - Only modify `CHAINS` dictionary, not the `run_pipeline()` function logic
5. **Context model** (`domain/models.py`) - Do not add fields without architectural discussion
6. **Exception handling in pipeline** - The pipeline's error handling is fixed

## Task Naming Conventions

- Use lowercase with underscores: `fetch_pypi`, `run_analyses`, `clone_repo`
- Be descriptive: `fetch_npm` not `fn`
- Match the file name: `fetch_npm.py` contains `FetchNpm` class with `name = "fetch_npm"`

## Shared Tasks Across Chains

Tasks can appear in multiple chains. For example, `run_analyses` appears in both PyPI and NPM chains:

```python
CHAINS = {
    "pypi": [
        "fetch_pypi",
        "run_analyses",  # Shared task
    ],
    "npm": [
        "fetch_npm",
        "run_analyses",  # Same task, different chain
    ],
}
```

The same task instance is reused - no need to create separate implementations.

## Best Practices

### DO

- ✅ Keep tasks focused on a single responsibility
- ✅ Use descriptive status messages
- ✅ Log important steps and errors
- ✅ Handle errors appropriately (fatal vs recoverable)
- ✅ Update context fields to pass data forward
- ✅ Add findings for important events
- ✅ Check if `ctx.log_display` and `ctx.status_bar` exist before using
- ✅ Use the task name in log messages: `f"[{self.name}] ..."`

### DON'T

- ❌ Modify other task files
- ❌ Change the Task protocol
- ❌ Clear the log display
- ❌ Access TUI components directly (use context)
- ❌ Hardcode task dependencies or ordering
- ❌ Modify pipeline execution logic (only CHAINS)
- ❌ Create duplicate tasks for different chains (reuse instead)
- ❌ Skip error handling
- ❌ Modify context structure without architectural approval

## Example: Complete Task Implementation

```python
"""Task to clone a Git repository."""

from pathlib import Path
from vibanalyz.domain.exceptions import PipelineFatalError
from vibanalyz.domain.models import Context, Finding, RepoInfo
from vibanalyz.domain.protocols import Task
from vibanalyz.services.tasks import register


class CloneRepo:
    """Task to clone a Git repository."""

    name = "clone_repo"

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        return f"Cloning repository for {ctx.package_name} module."

    def run(self, ctx: Context) -> Context:
        """Clone the repository and update context."""
        # Check prerequisites
        if not ctx.package:
            raise PipelineFatalError(
                message="Cannot clone repo: package metadata not available",
                source=self.name
            )
        
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Starting repository clone")
            if ctx.package.project_urls:
                ctx.log_display.write(f"[{self.name}] Repository URL: {ctx.package.project_urls.get('Repository', 'N/A')}")
        
        try:
            # Perform clone operation
            repo_url = self._extract_repo_url(ctx)
            if not repo_url:
                if ctx.log_display:
                    ctx.log_display.write(f"[{self.name}] WARNING: No repository URL found")
                ctx.findings.append(
                    Finding(
                        source=self.name,
                        message="No repository URL found in package metadata",
                        severity="warning",
                    )
                )
                return ctx
            
            # Clone logic here...
            repo_path = Path("/tmp/cloned_repo")  # Example
            
            # Update context
            ctx.repo = RepoInfo(url=repo_url)
            # If RepoInfo had a path field: ctx.repo.path = repo_path
            
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] Successfully cloned repository")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Repository cloned successfully from {repo_url}",
                    severity="info",
                )
            )
        except Exception as e:
            # Fatal error - cannot continue without repo
            if ctx.log_display:
                ctx.log_display.write(f"[{self.name}] ERROR: Failed to clone repository: {str(e)}")
            
            ctx.findings.append(
                Finding(
                    source=self.name,
                    message=f"Failed to clone repository: {str(e)}",
                    severity="critical",
                )
            )
            raise PipelineFatalError(
                message=f"Repository clone failed: {str(e)}",
                source=self.name
            )
        
        return ctx
    
    def _extract_repo_url(self, ctx: Context) -> str | None:
        """Extract repository URL from package metadata."""
        if not ctx.package or not ctx.package.project_urls:
            return None
        
        for key, url in ctx.package.project_urls.items():
            if key.lower() in ["repository", "source", "code"]:
                return url
        return None


# Auto-register this task
register(CloneRepo())
```

## Adding Task to Chain

After creating the task, add it to the appropriate chain in `services/pipeline.py`:

```python
CHAINS = {
    "pypi": [
        "fetch_pypi",
        "clone_repo",      # Add here
        "run_analyses",
    ],
    "npm": [
        "fetch_npm",
        "clone_repo",      # Can reuse in multiple chains
        "run_analyses",
    ],
}
```

## Testing Your Task

1. Ensure task is registered (check `services/tasks/__init__.py` has import)
2. Ensure task is in the appropriate chain(s) in `CHAINS`
3. Run the pipeline and verify:
   - Status message appears correctly
   - Logging works as expected
   - Context is updated properly
   - Errors are handled correctly
   - Pipeline continues or stops as intended

## Common Pitfalls

1. **Forgetting to register**: Task won't be found if not imported in `__init__.py`
2. **Name mismatch**: Task `name` must match the string in `CHAINS`
3. **Not checking for None**: Always check if `ctx.log_display` exists before using
4. **Modifying other tasks**: Only modify the task you're creating/updating
5. **Changing protocol**: Don't modify the Task protocol interface
6. **Hardcoding dependencies**: Tasks should work independently

## Summary

- **One task = One file**: Each task is isolated in its own file
- **Auto-registration**: Tasks register themselves via `register()` call
- **Chain configuration**: Add tasks to `CHAINS` in `pipeline.py` to execute them
- **Context communication**: Tasks read from and write to `Context` object
- **Fatal errors**: Raise `PipelineFatalError` to stop pipeline early
- **Isolation**: Only modify the task you're working on and `pipeline.py` (for chains)
