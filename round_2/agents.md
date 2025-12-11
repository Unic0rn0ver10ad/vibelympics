# Agent Guidelines for vibanalyz

Use these guardrails when modifying the codebase. They consolidate the architectural and process guidance from existing markdown files.

## Core Principles
- Maintain the modular monolith shape: one process, cleanly separated layers, no cross-layer leakage.
- Prefer isolation: one action/task/analyzer per file with a single responsibility and no dependencies on siblings.
- Keep the main app thin: it wires components and actions, routes events, and reacts to state; it should not host business logic.

## TUI Architecture (Textual)
- **Components (`src/vibanalyz/app/components/`)**: wrap widgets only. Provide focused helpers (`write()`, `clear()`, `update()`, `get_package_info()`). Never embed business logic or reference other components/main app.
- **Actions (`src/vibanalyz/app/actions/`)**: each file handles one user action. Accept only the components needed. Update UI through component methods, return results/raise errors, and never call other actions or the main app.
- **State (`src/vibanalyz/app/state.py`)**: track app-wide facts (e.g., whether an audit ran, current package, audit result). Update state in the main app after actions complete; use it to drive UI enablement/visibility.
- **Main App (`src/vibanalyz/app/main.py`)**: compose UI, instantiate components/actions, route events, and call `_update_ui_for_state()` to adjust the interface based on `AppState`.

## Pipeline & Analyzer Architecture
- **Task pattern (`src/vibanalyz/services/tasks/`)**: one task per file with `name`, `get_status_message(ctx)`, and `run(ctx)` that reads/writes the shared `Context`. Tasks auto-register via `register(...)` at module import.
- **Chains (`src/vibanalyz/services/pipeline.py`)**: declare task order per repository source in `CHAINS`. Modify chains (order/add/remove tasks) here only; do not alter pipeline execution logic.
- **Registry (`src/vibanalyz/services/tasks/__init__.py`)**: only add task imports to trigger registration; leave registry internals unchanged.
- **Context (`src/vibanalyz/domain/models.py`)**: pass data between tasks/analyzers via `Context`; avoid structural changes without architectural agreement.
- **Error handling**: raise `PipelineFatalError` for stop-the-world failures; log warnings/add findings for recoverable issues. Always gate UI logging on `ctx.log_display`/`ctx.status_bar` existence.
- **Analyzers (`src/vibanalyz/analyzers/`)**: register via `register(...)` in `__init__.py`. Keep analyzers independent and focused; they emit `Finding` instances.

## Coding Conventions
- One responsibility per module/class; avoid circular dependencies.
- Use descriptive names (tasks lowercase with underscores; classes in PascalCase).
- Never wrap imports in try/except.
- Logging format for tasks/analyzers: `f"[{self.name}] <message>"`; do not clear logs.
- Update `_update_ui_for_state()` when state changes affect UI availability/visibility.

## Feature Extension Checklist
- New UI behavior: create an action file, wire it in `on_mount()`, route events, update state, and adjust `_update_ui_for_state()` if visibility/enablement changes.
- New task: create the module, implement protocol, register via `register(...)`, import in `services/tasks/__init__.py`, and add to `CHAINS`.
- New repo source: add adapter client, create fetch task, import it for registration, and add a chain entry.

## Testing & Validation
- Test components by mocking widgets; test actions/tasks/analyzers by mocking dependencies/context.
- Verify pipelines by ensuring tasks register, appear in the correct chain, emit status messages/logs, and update context/findings as expected.

## Docker & Containerization
- **CRITICAL**: The Dockerfile **MUST** use Chainguard Python images (`cgr.dev/chainguard/python:latest-dev`). Do not revert to standard Python images (e.g., `python:3.11-slim`).
- Uses multi-stage build: builder stage compiles packages, runtime stage runs as `nonroot:nonroot` user.
- Uses `apk` package manager (Wolfi/Alpine-based), not `apt-get`.
- Creates `/app/output` directory owned by `nonroot` for reports and SBOMs.
- Sets `WORKDIR /app/output` so `Path.cwd()` resolves to a writable location.
- When modifying the Dockerfile, maintain security best practices: run as non-root, use minimal base images, keep attack surface small.

## Roadmap Hints
- Planned expansions include real PyPI/NPM integrations, repo cloning/downloading, SBOM and vulnerability scanning, dependency graph analysis, richer PDF reporting, additional TUI affordances, and container hardening. Align new work with these directions when choosing implementations.
