# vibanalyz

Package security auditing tool - MVP stub

## Overview

vibanalyz is a Python CLI/TUI application for auditing software packages. This MVP provides a stubbed implementation with a modular architecture ready for extension.

## Features

- Textual-based TUI interface
- Modular analyzer plugin system
- PDF report generation
- Docker containerization with Chainguard Python base image

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

## Project Structure

```
vibanalyz/
  src/vibanalyz/
    app/          # Textual TUI application
    domain/       # Domain models, protocols, and scoring
    services/     # Pipeline, reporting, and tasks
    analyzers/    # Analyzer plugins
    adapters/     # External service adapters
    cli.py        # CLI entry point
```

## Development

This is an MVP with stubbed implementations. All logic is placeholder, but the architecture is designed to be extended with real implementations for:

- PyPI metadata fetching
- SBOM generation (Trivy)
- Vulnerability scanning (Grype)
- Dependency graph analysis
- Risk scoring algorithms
