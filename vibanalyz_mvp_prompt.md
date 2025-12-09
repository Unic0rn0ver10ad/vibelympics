# vibanalyz – Architecture Reference

This document describes the current architecture of **`vibanalyz`**, a Python CLI/TUI application for auditing software packages from multiple repository sources (PyPI, NPM).

## Overview

The application:
- Can be installed and run locally via `pip install .`
- Can be built into a **single container image** using the **Chainguard Python** base image
- Launches a **Textual** TUI that:
  - Accepts an optional package name as a CLI argument
  - Allows selecting the repository source (PyPI or NPM)
  - Fetches real package metadata from the selected registry
  - Runs security analyses and generates findings
  - Produces a PDF audit report

---

## Requirements

1. **Project name & packaging**
   - Python package name: `vibanalyz`
   - Uses `pyproject.toml` with `hatchling` backend
   - Uses `src/` layout
   - Console script entrypoint: `vibanalyz`

2. **Dependencies**
   - Python version: `>=3.11`
   - `textual` – TUI framework
   - `reportlab` – PDF generation
   - `requests` – HTTP client for registry APIs

---

## Directory Structure

```text
vibanalyz/
  pyproject.toml
  Dockerfile
  architecture_notes.md      # TUI architecture guide
  vibanalyz_mvp_prompt.md    # This file
  src/
    vibanalyz/
      __init__.py
      cli.py

      app/
        __init__.py
        main.py              # Main Textual app (orchestrator)
        state.py             # Application state management
        actions/
          __init__.py
          audit_action.py    # Audit execution action handler
        components/
          __init__.py
          input_section.py   # Package input component
          log_display.py     # Log output component
          status_bar.py      # Status bar component

      domain/
        __init__.py
        models.py            # Core data models
        protocols.py         # Task and Analyzer protocols
        scoring.py           # Risk score computation
        exceptions.py        # Pipeline exceptions

      services/
        __init__.py
        pipeline.py          # Pipeline orchestrator with chain support
        reporting.py         # PDF report generation
        tasks/
          __init__.py        # Task registry
          fetch_pypi.py      # PyPI metadata fetch task
          fetch_npm.py       # NPM metadata fetch task
          run_analyses.py    # Run all analyzers task

      analyzers/
        __init__.py          # Analyzer registry
        metadata.py          # Metadata analyzer

      adapters/
        __init__.py
        pypi_client.py       # PyPI registry HTTP client
        npm_client.py        # NPM registry HTTP client
```

---

## Domain Layer

### `domain/models.py`

Core dataclasses representing domain concepts:

**`PackageMetadata`** – Package information from registries:
- `name: str`
- `version: Optional[str]`
- `summary: Optional[str]`
- `maintainers: Optional[list[str]]`
- `home_page: Optional[str]`
- `project_urls: Optional[dict[str, str]]`
- `requires_dist: Optional[list[str]]`
- `author: Optional[str]`
- `author_email: Optional[str]`
- `license: Optional[str]`
- `release_count: Optional[int]`

**`RepoInfo`** – Repository information:
- `url: Optional[str]`

**`Sbom`** – Software Bill of Materials (placeholder for Trivy output):
- `raw: Optional[dict]`

**`VulnReport`** – Vulnerability report (placeholder for Grype output):
- `raw: Optional[dict]`

**`Finding`** – Security finding from an analyzer:
- `source: str`
- `message: str`
- `severity: str` (`"info"` | `"low"` | `"medium"` | `"high"` | `"critical"`)

**`Context`** – Shared data passed through tasks and analyzers:
- `package_name: str`
- `requested_version: Optional[str]`
- `repo_source: Optional[str]` – Repository source (`"pypi"` or `"npm"`)
- `package: Optional[PackageMetadata]`
- `repo: Optional[RepoInfo]`
- `sbom: Optional[Sbom]`
- `vulns: Optional[VulnReport]`
- `findings: list[Finding]`
- `log_display: Optional[LogDisplay]` – Reference to UI log component
- `status_bar: Optional[StatusBar]` – Reference to UI status bar component

**`AuditResult`** – Final result of the audit pipeline:
- `ctx: Context`
- `score: int`
- `pdf_path: Optional[str]`

### `domain/protocols.py`

Protocol interfaces for extensibility:

**`Analyzer`** – Security analyzer interface:
- `name: str`
- `run(self, ctx: Context) -> Iterable[Finding]`

**`Task`** – Pipeline task interface:
- `name: str`
- `get_status_message(self, ctx: Context) -> str` – Returns status message for UI
- `run(self, ctx: Context) -> Context` – Executes task and returns updated context

### `domain/exceptions.py`

**`PipelineFatalError`** – Exception to signal pipeline termination:
- `message: str` – Error description
- `source: Optional[str]` – Task/component that raised the error

When raised by a task, the pipeline stops execution and returns a partial result.

### `domain/scoring.py`

- `compute_risk_score(result: AuditResult) -> int` – Computes risk score based on findings

---

## Pipeline Architecture

### Task Registry (`services/tasks/__init__.py`)

Tasks are registered by name and resolved at runtime:

```python
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
```

Tasks auto-register themselves at import time:
```python
# At bottom of each task module
register(FetchPyPi())
```

### Chain-Based Pipeline (`services/pipeline.py`)

The pipeline supports multiple repository sources via task chains:

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

**`run_pipeline(ctx: Context) -> AuditResult`**:

1. **Validate** `ctx.repo_source` is set and exists in `CHAINS`
2. **Resolve** task names from registry via `get_task()`
3. **Execute** tasks in order:
   - Update status bar before each task
   - Run task, passing context
   - Catch `PipelineFatalError` and return partial result
4. **Compute** risk score via `compute_risk_score()`
5. **Generate** PDF report via `write_pdf_report()`
6. **Return** `AuditResult` with score and PDF path

### Task Implementations

**`FetchPyPi`** (`services/tasks/fetch_pypi.py`):
- Fetches package metadata from PyPI JSON API
- Sets `ctx.package` with retrieved metadata
- Raises `PipelineFatalError` if package not found

**`FetchNpm`** (`services/tasks/fetch_npm.py`):
- Fetches package metadata from NPM Registry API
- Sets `ctx.package` with retrieved metadata
- Raises `PipelineFatalError` if package not found

**`RunAnalyses`** (`services/tasks/run_analyses.py`):
- Iterates over all registered analyzers
- Extends `ctx.findings` with analyzer results

---

## Adapters (HTTP Clients)

### `adapters/pypi_client.py`

Real HTTP client for PyPI JSON API:

**Exception classes:**
- `PyPIError` – Base exception
- `PackageNotFoundError` – Package or version not found (404)
- `NetworkError` – Network connection issues

**Functions:**
- `fetch_package_metadata(name: str, version: Optional[str] = None) -> PackageMetadata`
  - URL: `https://pypi.org/pypi/{name}/json` or `https://pypi.org/pypi/{name}/{version}/json`
  - Parses JSON response into `PackageMetadata`

### `adapters/npm_client.py`

Real HTTP client for NPM Registry API:

**Exception classes:**
- `NPMError` – Base exception
- `PackageNotFoundError` – Package or version not found (404)
- `NetworkError` – Network connection issues

**Functions:**
- `fetch_package_metadata(name: str, version: Optional[str] = None) -> PackageMetadata`
  - URL: `https://registry.npmjs.org/{name}` or `https://registry.npmjs.org/{name}/{version}`
  - Parses JSON response into `PackageMetadata`

---

## Analyzer System

### Analyzer Registry (`analyzers/__init__.py`)

```python
_ANALYZERS: list[Analyzer] = []

def register(analyzer: Analyzer) -> None:
    """Register an analyzer."""
    _ANALYZERS.append(analyzer)

def all_analyzers() -> list[Analyzer]:
    """Get all registered analyzers."""
    return _ANALYZERS
```

### `MetadataAnalyzer` (`analyzers/metadata.py`)

- `name = "metadata"`
- Analyzes package metadata and produces findings
- Auto-registers at import time

---

## TUI Architecture

The TUI follows an MVC-like pattern (see `architecture_notes.md` for details):

### Components Layer (`app/components/`)

UI widgets with simple interfaces:

- **`LogDisplay`** – Wraps RichLog, provides `write()`, `clear()`, `write_section()`
- **`StatusBar`** – Wraps Static, provides `update()`
- **`InputSection`** – Wraps Input, provides `get_value()`, `set_value()`, `get_package_info()`

### Actions Layer (`app/actions/`)

Independent action handlers:

- **`AuditAction`** – Handles audit execution
  - Takes UI components as constructor dependencies
  - Creates `Context` with `log_display` and `status_bar` references
  - Calls `run_pipeline()` and displays results

### State Layer (`app/state.py`)

Application-wide state:

- **`AppState`** – Tracks `has_run_audit`, `current_package`, `audit_result`

### Main App (`app/main.py`)

Thin orchestrator:
- Composes UI in `compose()`
- Initializes components and actions in `on_mount()`
- Routes events to action handlers
- Updates UI based on state changes

---

## PDF Report Generation

### `services/reporting.py`

Uses **ReportLab** for PDF generation:

- `render_text_report(result: AuditResult) -> str` – Text representation of audit result
- `write_pdf_report(result: AuditResult, output_dir: Path | str | None = None) -> Path` – Creates PDF report

---

## CLI

### `cli.py`

- Uses `argparse` for CLI arguments
- Accepts optional positional `package` argument
- Instantiates and runs `AuditApp`

```toml
[project.scripts]
vibanalyz = "vibanalyz.cli:main"
```

---

## Dockerfile

**CRITICAL**: The Dockerfile **MUST** use Chainguard Python images (`cgr.dev/chainguard/python:latest-dev`) for security and compliance. Do not revert to standard Python images (e.g., `python:3.11-slim`).

The Dockerfile uses a multi-stage build:

1. **Builder stage**: Uses `cgr.dev/chainguard/python:latest-dev` to install build dependencies and compile Python packages
2. **Runtime stage**: Uses `cgr.dev/chainguard/python:latest-dev` with runtime libraries, Syft CLI, and runs as non-root user

Key features:
- Uses `apk` package manager (Wolfi/Alpine-based)
- Runs as `nonroot:nonroot` user for security
- Creates `/app/output` directory for reports and SBOMs (writable by nonroot)
- Sets `WORKDIR /app/output` so generated files are written to a writable location
- Installs Syft CLI using Python's tarfile module (since `tar` package isn't available in Wolfi)

Usage:
```bash
docker build -t vibanalyz .
docker run --rm -it vibanalyz requests
```

To access generated reports and SBOMs:
```bash
docker run --rm -it -v $(pwd)/output:/app/output vibanalyz requests
```

---

## Adding New Repository Sources

To add a new repository source (e.g., RubyGems):

1. **Create adapter** (`adapters/rubygems_client.py`):
   - Exception classes: `RubyGemsError`, `PackageNotFoundError`, `NetworkError`
   - Function: `fetch_package_metadata(name, version) -> PackageMetadata`

2. **Create task** (`services/tasks/fetch_rubygems.py`):
   - Class `FetchRubyGems` implementing `Task` protocol
   - Auto-register at bottom: `register(FetchRubyGems())`

3. **Update pipeline** (`services/pipeline.py`):
   - Add chain: `"rubygems": ["fetch_rubygems", "run_analyses"]`

4. **Update task imports** (`services/tasks/__init__.py`):
   - Add: `from vibanalyz.services.tasks import fetch_rubygems`

---

## Error Handling

### Pipeline Errors

- **Missing repo_source**: `ValueError` raised if `ctx.repo_source` not set
- **Unknown repo_source**: `ValueError` raised if not in `CHAINS`
- **Missing tasks**: `ValueError` raised if task not found in registry
- **Fatal errors**: `PipelineFatalError` caught, partial result returned

### Adapter Errors

- **PackageNotFoundError**: Raised on 404, triggers `PipelineFatalError` in task
- **NetworkError**: Raised on connection issues, added as warning finding
- **Base errors** (PyPIError/NPMError): Caught and added as warning finding

---

## Summary

| Layer | Purpose |
|-------|---------|
| **Domain** | Data models, protocols, exceptions, scoring |
| **Adapters** | HTTP clients for external registries |
| **Services** | Pipeline orchestration, task registry, PDF reporting |
| **Analyzers** | Security analysis plugins |
| **App** | TUI components, actions, state, orchestration |
| **CLI** | Command-line entrypoint |

The architecture supports:
- Multiple repository sources via chain-based pipeline
- Extensible task and analyzer systems via registries
- Clean separation of UI (components), logic (actions), and state
- Graceful error handling with `PipelineFatalError`
