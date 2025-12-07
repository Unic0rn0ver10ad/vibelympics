# vibanalyz

A package security auditing tool for PyPI and NPM packages.

## Overview

vibanalyz is a Python CLI/TUI application for auditing software packages from multiple repository sources. It fetches real package metadata from PyPI and NPM registries, runs security analyses, and generates PDF audit reports.

## Current Features

- **Multi-Repository Support**: Audit packages from PyPI or NPM registries
- **Real Metadata Fetching**: Live HTTP calls to PyPI JSON API and NPM Registry API
- **Textual TUI**: Modern terminal interface with:
  - Package name input with version support (`package==1.0.0`)
  - Repository source selection (PyPI/NPM)
  - Real-time status updates and detailed logging
  - Error handling with user-friendly messages
- **Modular Pipeline**: Chain-based task execution system
- **Analyzer Plugin System**: Extensible security analysis framework
- **PDF Report Generation**: Automated audit reports using ReportLab
- **Docker Support**: Containerized deployment with Chainguard Python base image

## Installation

### Local Development

```bash
pip install -e .
```

### Docker

Build the container image:

```bash
docker build -t vibanalyz .
```

## Usage

### Local

Run without arguments to open the TUI:

```bash
vibanalyz
```

Or provide a package name as an argument:

```bash
vibanalyz requests
```

### Docker

Run the container:

```bash
docker run --rm -it vibanalyz
```

Or with a package name:

```bash
docker run --rm -it vibanalyz requests
```

### In the TUI

1. Enter a package name (optionally with version: `requests==2.31.0`)
2. Select the repository source (PyPI or NPM)
3. Click "Run audit" or press Enter
4. View real-time progress and findings in the log
5. PDF report is generated automatically

## Project Structure

```
vibanalyz/
  src/vibanalyz/
    app/                    # Textual TUI application
      main.py               # Main app orchestrator
      state.py              # Application state management
      actions/              # Action handlers (audit, etc.)
      components/           # UI components (log, status, input)
    domain/                 # Domain models and protocols
      models.py             # PackageMetadata, Context, Finding, etc.
      protocols.py          # Task and Analyzer interfaces
      exceptions.py         # PipelineFatalError
      scoring.py            # Risk score computation
    services/               # Pipeline and reporting
      pipeline.py           # Chain-based task orchestration
      reporting.py          # PDF report generation
      tasks/                # Pipeline tasks
        fetch_pypi.py       # PyPI metadata fetching
        fetch_npm.py        # NPM metadata fetching
        run_analyses.py     # Run all analyzers
    analyzers/              # Security analyzer plugins
      metadata.py           # Metadata analyzer
    adapters/               # External service clients
      pypi_client.py        # PyPI Registry HTTP client
      npm_client.py         # NPM Registry HTTP client
    cli.py                  # CLI entry point
```

## Architecture

### Pipeline System

The audit pipeline uses a chain-based architecture where each repository source has its own task chain:

```python
CHAINS = {
    "pypi": ["fetch_pypi", "run_analyses"],
    "npm": ["fetch_npm", "run_analyses"],
}
```

Tasks are registered in a central registry and resolved by name at runtime, making it easy to add new repository sources.

### Error Handling

- **Package Not Found**: Raises `PipelineFatalError`, stops pipeline, returns partial result
- **Network Errors**: Logged as warnings, pipeline continues if possible
- **Invalid Repository Source**: Raises `ValueError` with available sources

### TUI Architecture

The TUI follows an MVC-like pattern:
- **Components**: UI widgets with simple interfaces (`LogDisplay`, `StatusBar`, `InputSection`)
- **Actions**: Independent business logic handlers (`AuditAction`)
- **State**: Application-wide state tracking (`AppState`)
- **Main App**: Thin orchestrator routing events to handlers

See `architecture_notes.md` for detailed guidelines.

## Roadmap

Future enhancements planned:

- [ ] **SBOM Generation**: Integrate Trivy for Software Bill of Materials
- [ ] **Vulnerability Scanning**: Integrate Grype for CVE detection
- [ ] **Dependency Graph Analysis**: Visualize and analyze dependency trees
- [ ] **Advanced Risk Scoring**: ML-based risk assessment algorithms
- [ ] **Additional Registries**: RubyGems, Cargo, Go modules, etc.
- [ ] **CI/CD Integration**: GitHub Actions, GitLab CI support
- [ ] **Policy Engine**: Custom security policy definitions

## Adding New Repository Sources

To add support for a new registry (e.g., RubyGems):

1. Create adapter: `adapters/rubygems_client.py`
2. Create task: `services/tasks/fetch_rubygems.py`
3. Add chain to `pipeline.py`: `"rubygems": ["fetch_rubygems", "run_analyses"]`
4. Import task in `services/tasks/__init__.py`

See `vibanalyz_mvp_prompt.md` for detailed instructions.

## License

See [LICENSE](LICENSE) for details.
