# Status and Log Display System

## Overview

The `vibanalyz` application uses a dual-display system for user feedback:
1. **Status Display**: A concise, three-part status bar showing pipeline progress
2. **Log Display**: A detailed, scrollable log of all operations and messages

This document explains how these systems work, how they integrate with the pipeline architecture, and how to extend them.

## Architecture

### Components

#### 1. StatusBar (`src/vibanalyz/app/components/status_bar.py`)

A wrapper around a Textual `Static` widget that displays a three-part status:
- **Previous Action** (left-justified)
- **Current Action** (center-justified)  
- **Next Action** (right-justified)

Separated by configurable separators (default: `*`).

**Key Methods:**
- `update_status(previous: str, current: str, next: str, separator: str = "*")`: Updates the three-part display
- `update(message: str)`: Backward-compatible single-message update (shifts current to previous)

**Formatting:**
- Automatically calculates widget width
- Allocates space: ~30% previous, ~40% current, ~30% next
- Truncates long messages with ellipsis
- Handles widget size changes dynamically

#### 2. LogDisplay (`src/vibanalyz/app/components/log_display.py`)

A wrapper around a Textual `RichLog` widget that displays detailed log messages.

**Key Methods:**
- `write(message: str)`: Writes a message to the log
- `write_section(title: str, lines: list[str])`: Writes a formatted section with separators
- `clear()`: Clears all log content
- `get_text()`: Returns all log content as plain text (for clipboard)

**Features:**
- Maintains internal buffer for text extraction
- Supports section formatting with separators
- Scrollable display

## Message Flow

### Status Messages

**Source:** Individual pipeline tasks via `get_status_message(ctx: Context) -> str`

**Update Responsibility:** Pipeline orchestrator (`src/vibanalyz/services/pipeline.py`)

**Flow:**
1. Pipeline determines task chain for the repository source
2. Before each task runs, pipeline:
   - Gets previous task's status message (if exists)
   - Gets current task's status message
   - Gets next task's status message (if exists)
   - Calls `ctx.status_bar.update_status(previous, current, next)`
3. Task executes (status already updated)

**Example Status Messages:**
- `"Query Repo"` - Fetching package metadata
- `"Download Package"` - Downloading package artifact
- `"Generate SBOM"` - Generating SBOM with Syft
- `"Analyze Package"` - Running security analyzers

**Important:** Tasks should NOT update the status bar directly. The pipeline orchestrator handles all status updates to maintain consistency and avoid circular dependencies.

### Log Messages

**Source:** Individual pipeline tasks via `ctx.log_display.write(message: str)`

**Update Responsibility:** Individual tasks

**Flow:**
1. Task calls `ctx.log_display.write("[task_name] Message text")`
2. LogDisplay writes to RichLog widget
3. Message appears in scrollable log area

**Conventions:**
- Prefix messages with `[task_name]` for clarity
- Use descriptive, verbose messages
- Include progress updates, errors, and results
- Use `write_section()` for structured information blocks

## Integration Points

### 1. Context Object (`src/vibanalyz/domain/models.py`)

The `Context` object carries UI components through the pipeline:

```python
@dataclass
class Context:
    # ... other fields ...
    log_display: Optional["LogDisplay"] = None
    status_bar: Optional["StatusBar"] = None
```

### 2. Pipeline Orchestrator (`src/vibanalyz/services/pipeline.py`)

The `run_pipeline()` function:
- Creates context with UI components
- Updates status bar before each task
- Updates progress tracker
- Handles errors and updates status accordingly

**Key Code Section:**
```python
for index, task in enumerate(tasks):
    # Get status messages
    previous_status = get_previous_task_status(...)
    current_status = task.get_status_message(ctx)
    next_status = get_next_task_status(...)
    
    # Update status bar BEFORE task runs
    if ctx.status_bar:
        ctx.status_bar.update_status(previous_status, current_status, next_status)
    
    # Run task (task writes to log_display)
    ctx = task.run(ctx)
```

### 3. Task Interface (`src/vibanalyz/domain/protocols.py`)

All tasks implement:
- `get_status_message(ctx: Context) -> str`: Returns short status string
- `run(ctx: Context) -> Context`: Executes task, writes to log_display

**Example Task:**
```python
class FetchPyPi:
    name = "fetch_pypi"
    
    def get_status_message(self, ctx: Context) -> str:
        return "Query Repo"
    
    def run(self, ctx: Context) -> Context:
        # Status already updated by pipeline
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Starting fetch...")
            ctx.log_display.write(f"[{self.name}] Successfully fetched...")
        return ctx
```

### 4. Main Application (`src/vibanalyz/app/main.py`)

**Initialization:**
- Creates StatusBar and LogDisplay components
- Wraps Textual widgets with component classes
- Passes components to AuditAction

**Initial Status:**
```python
self.components["status"].update_status(
    "Welcome to Vibanalyz",
    "Repo Select",
    "Package Select"
)
```

**UI State Updates:**
- Updates status when repo selection changes
- Resets status on "Start over"
- Updates status before/after audit execution

### 5. Audit Action (`src/vibanalyz/app/actions/audit_action.py`)

**Responsibilities:**
- Creates context with UI components
- Calls `run_pipeline(ctx)`
- Updates status for completion/error states
- Displays results

**Status Updates:**
- Before pipeline: Sets initial pipeline status
- After pipeline: Sets completion/error status

## Adding New Tasks

### Step 1: Implement Task Interface

```python
class MyNewTask:
    name = "my_new_task"
    
    def get_status_message(self, ctx: Context) -> str:
        return "My Task Status"  # Short, high-level description
    
    def run(self, ctx: Context) -> Context:
        # Status already updated by pipeline - don't update it here!
        
        # Write detailed log messages
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Starting operation...")
            ctx.log_display.write(f"[{self.name}] Step 1 complete...")
            ctx.log_display.write(f"[{self.name}] Operation finished")
        
        return ctx
```

### Step 2: Register Task

```python
from vibanalyz.services.tasks import register

register(MyNewTask())
```

### Step 3: Add to Pipeline Chain

In `src/vibanalyz/services/pipeline.py`, add to appropriate chain:

```python
CHAINS = {
    "pypi": ["fetch_pypi", "download_pypi", "generate_sbom", "run_analyses"],
    "npm": ["fetch_npm", "download_npm", "generate_sbom", "run_analyses"],
}
```

The pipeline will automatically:
- Get status message from `get_status_message()`
- Update status bar with previous/current/next
- Call `run()` method

## Design Principles

### 1. Separation of Concerns

- **Status Display**: Managed by pipeline orchestrator (knows task order)
- **Log Display**: Managed by individual tasks (know task details)
- **Progress Tracker**: Managed by pipeline orchestrator (tracks overall progress)

### 2. Single Source of Truth

- Status messages come from task's `get_status_message()` method
- Pipeline orchestrator is the only code that updates the status bar
- Tasks never directly update the status bar

### 3. Message Granularity

- **Status Messages**: Short, high-level (e.g., "Query Repo", "Generate SBOM")
- **Log Messages**: Detailed, verbose (e.g., "[fetch_pypi] Connecting to PyPI API...")

### 4. Error Handling

- Tasks write error messages to log_display
- Pipeline updates status bar for fatal errors
- AuditAction updates status bar for completion/error states

## Common Patterns

### Pattern 1: Task with Multiple Steps

```python
def run(self, ctx: Context) -> Context:
    if ctx.log_display:
        ctx.log_display.write(f"[{self.name}] Starting...")
        ctx.log_display.write(f"[{self.name}] Step 1: Doing X...")
        # ... do step 1 ...
        ctx.log_display.write(f"[{self.name}] Step 1 complete")
        ctx.log_display.write(f"[{self.name}] Step 2: Doing Y...")
        # ... do step 2 ...
        ctx.log_display.write(f"[{self.name}] Step 2 complete")
        ctx.log_display.write(f"[{self.name}] Finished")
    return ctx
```

### Pattern 2: Task with Structured Output

```python
def run(self, ctx: Context) -> Context:
    if ctx.log_display:
        ctx.log_display.write(f"[{self.name}] Processing...")
        # ... process data ...
        ctx.log_display.write_section("Results", [
            f"Total items: {count}",
            f"Success: {success_count}",
            f"Failed: {fail_count}",
        ])
    return ctx
```

### Pattern 3: Task with Error Handling

```python
def run(self, ctx: Context) -> Context:
    if ctx.log_display:
        ctx.log_display.write(f"[{self.name}] Starting...")
    
    try:
        # ... do work ...
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] Success")
    except SomeError as e:
        if ctx.log_display:
            ctx.log_display.write(f"[{self.name}] ERROR: {str(e)}")
        raise PipelineFatalError(message=str(e), source=self.name)
    
    return ctx
```

## Troubleshooting

### Status Bar Not Updating

1. Check that `ctx.status_bar` is not None in pipeline
2. Verify `update_status()` is being called before task runs
3. Check that widget is visible (CSS styling)
4. Verify widget size is available (may default to 120 width)

### Log Messages Not Appearing

1. Check that `ctx.log_display` is not None in task
2. Verify `write()` is being called
3. Check that RichLog widget is visible and has height
4. Verify messages are being written to internal buffer

### Status Messages Not Matching Tasks

1. Verify task's `get_status_message()` returns correct string
2. Check that task is registered correctly
3. Verify task is in the correct pipeline chain
4. Check that pipeline is getting status from correct task

## File Locations

- **StatusBar Component**: `src/vibanalyz/app/components/status_bar.py`
- **LogDisplay Component**: `src/vibanalyz/app/components/log_display.py`
- **Pipeline Orchestrator**: `src/vibanalyz/services/pipeline.py`
- **Task Interface**: `src/vibanalyz/domain/protocols.py`
- **Context Model**: `src/vibanalyz/domain/models.py`
- **Main Application**: `src/vibanalyz/app/main.py`
- **Audit Action**: `src/vibanalyz/app/actions/audit_action.py`

## Future Enhancements

Potential improvements:
- Animated transitions between status updates
- Status message history/navigation
- Log filtering/search capabilities
- Export log to file
- Status bar themes/customization
- Progress percentage in status bar
