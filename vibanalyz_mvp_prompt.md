# vibanalyz – MVP Stub Generator Prompt

You are an AI coding assistant. Your task is to generate a **minimal but fully wired MVP** for a Python CLI/TUI application called **`vibanalyz`**.

The goal of this MVP is:
- The project can be installed and run locally.
- The project can be built into a **single container image** using the **latest Chainguard Python** base image (free edition).
- Running the container launches a **Textual** TUI/CLI that:
  - Accepts an optional package name as a CLI argument.
  - If provided, auto-runs a stub “audit” for that package.
  - If not provided, shows an input field in the TUI to type a package name and run the stub audit.
- The internal architecture is modular and ready to be extended, but **all logic is stubbed** (no real network calls, SBOM generation, etc.).

The app will eventually audit software packages (PyPI, etc.), run Trivy and Grype, and combine multiple sources into a security report — but in this MVP, everything is fake/stubbed. The main goal is to prove plumbing and structure.

---

## Requirements

1. **Project name & packaging**
   - Python package name: `vibanalyz`.
   - Use `pyproject.toml` with `hatchling` (or another simple backend) for packaging.
   - Use `src/` layout.
   - Provide a console script entrypoint named `vibanalyz`.

2. **Dependencies**
   - Python version: `>=3.11`.
   - Include `textual` as a primary external dependency for the TUI.
   - Include `reportlab` as the PDF generation library (for now, use it to create a simple stub/template PDF report).

3. **High-level architecture**

Create the following directory structure:

```text
vibanalyz/
  pyproject.toml
  src/
    vibanalyz/
      __init__.py
      cli.py

      app/
        __init__.py
        main.py

      domain/
        __init__.py
        models.py
        protocols.py
        scoring.py

      services/
        __init__.py
        pipeline.py
        reporting.py
        tasks/
          __init__.py
          fetch_pypi.py
          run_analyses.py

      analyzers/
        __init__.py
        metadata.py

      adapters/
        __init__.py
        pypi_client.py
```

All logic should be stubbed, but the relationships should be realistic and future-proof.

---

## Domain layer (data models & protocols)

### `domain/models.py`

Define simple dataclasses to represent core concepts:

- `PackageMetadata` – name, optional version, optional summary.
- `RepoInfo` – URL (optional). (Will be used later.)
- `Sbom` – holds `raw: dict | None` (placeholder for Trivy output).
- `VulnReport` – holds `raw: dict | None` (placeholder for Grype output).
- `Finding` – fields:
  - `source: str`
  - `message: str`
  - `severity: str` (`"info" | "low" | "medium" | "high" | "critical"`)
- `Context` – shared data passed through tasks and analyzers:
  - `package_name: str`
  - `requested_version: str | None`
  - `package: PackageMetadata | None`
  - `repo: RepoInfo | None`
  - `sbom: Sbom | None`
  - `vulns: VulnReport | None`
  - `findings: list[Finding]`
- `AuditResult` – final result of pipeline:
  - `ctx: Context`
  - `score: int`

### `domain/protocols.py`

Define simple `Protocol` interfaces:

- `Analyzer` – has `name: str` and `run(self, ctx: Context) -> Iterable[Finding]`.
- `Task` – has `name: str` and `run(self, ctx: Context) -> Context`.

### `domain/scoring.py`

- Implement `compute_risk_score(result: AuditResult) -> int` as a **stub** that returns a fixed value (e.g. `42`). Later this will inspect findings.

---

## Analyzer plugin system (stubbed)

### `analyzers/__init__.py`

- Maintain a simple registry of analyzers:
  - `_ANALYZERS: list[Analyzer] = []`.
  - `register(analyzer: Analyzer) -> None`.
  - `all_analyzers() -> list[Analyzer]`.

### `analyzers/metadata.py`

- Implement `MetadataAnalyzer` with `name = "metadata"`.
- In `run(self, ctx: Context)`, return:
  - If `ctx.package` is `None`, one `Finding` saying metadata is missing (stub).
  - Else, one `Finding` saying it stub-analyzed the package and version.
- At import time, call `register(MetadataAnalyzer())`.

---

## Adapters (stub external services)

### `adapters/pypi_client.py`

- Implement `fetch_package_metadata_stub(name: str, version: str | None) -> PackageMetadata`.
- Do **not** call the network. Just return a `PackageMetadata` instance with:
  - `name` as provided.
  - `version` set to provided version or a placeholder like `"0.0.0-stub"`.
  - `summary` set to an explanatory stub string.

---

## Services / tasks / pipeline (stub but wired)

### `services/tasks/fetch_pypi.py`

- Implement a `FetchPyPi` class conforming to `Task`.
- In `run(self, ctx: Context) -> Context`:
  - Set `ctx.package = fetch_package_metadata_stub(ctx.package_name, ctx.requested_version)`.
  - Append a `Finding` to `ctx.findings` indicating that stub metadata was fetched.

### `services/tasks/run_analyses.py`

- Implement a `RunAnalyses` class conforming to `Task`.
- In `run(self, ctx: Context) -> Context`:
  - Iterate over all analyzers returned by `analyzers.all_analyzers()`.
  - Extend `ctx.findings` with their results.

### `services/pipeline.py`

- Create a `TASKS` list with the two tasks in order:
  - `FetchPyPi()`
  - `RunAnalyses()`
- Implement `run_pipeline(ctx: Context) -> AuditResult`:
  - Run each task in order, updating `ctx`.
  - Construct an `AuditResult` from the final `ctx`.
  - Compute a stub score via `compute_risk_score` and assign it.
  - Return the `AuditResult`.

---

## PDF report generation

Add a simple PDF reporting module and integrate it into the audit flow.

### `services/reporting.py`

- Use **ReportLab** (`reportlab` package) as the PDF generation library.
- Implement two functions:
  - `render_text_report(result: AuditResult) -> str` – returns a multi-line string representation of the audit result (for now, include only stub information like package name, version, score, and count of findings).
  - `write_pdf_report(result: AuditResult, output_dir: Path | str | None = None) -> Path` – creates a PDF file containing a stub report and returns the path to the generated PDF.

Implementation details (stub version):
- Use `reportlab.pdfgen.canvas.Canvas` to create the PDF.
- Place simple text on the first page, e.g.:
  - Title: `"vibanalyz – Stub Audit Report"`.
  - Package name and version.
  - Stub score and a short note that this is a placeholder report.
- For now, write the PDF into a temporary or current working directory, using a filename like `"vibanalyz-<package-name>-report.pdf"`.
- Return the absolute `Path` to the created file.

Update `AuditResult` in `domain/models.py`:
- Add an optional field `pdf_path: Optional[str] = None` to store the path to the generated PDF report.

Update the pipeline integration (`services/pipeline.py`):
- After building the `AuditResult` and computing the score, call `write_pdf_report(result)`.
- Store the returned path on `result.pdf_path`.


## Textual TUI / CLI

### `app/main.py`

Implement a simple Textual app called `AuditApp` with these behaviors:

- Layout:
  - `Header` and `Footer` widgets.
  - A static title: `"vibanalyz – MVP stub"`.
  - A brief instruction line.
  - An `Input` widget for package name.
  - A `Button` labeled `"Run audit"`.
  - A `TextLog` for showing progress and results.

- Constructor:
  - Accept an optional `package_name: str | None`.
  - Store this for use after mount.

- On mount:
  - If `package_name` is provided, schedule an auto-run (call an async method like `_auto_run`).

- Logic:
  - When the button is pressed, read from `Input` and call an async `run_audit(name: str)` method.
  - `run_audit` should:
    - Clear the `TextLog`.
    - Log a starting message including the package name.
    - Create a `Context` with `package_name=name`.
    - Call `run_pipeline(ctx)`.
    - Log a finishing message including the stub score.
    - Log the findings list with severity, source, and message.
  - If `result.pdf_path` is not `None`, log a final line such as:
    - `"PDF report saved to: <absolute-path>"`
    so that many terminals will let the user click the path to open the PDF on their local machine.

### `cli.py`

- Implement `main()` that:
  - Uses `argparse` to accept an optional positional `package` argument.
  - Instantiates and runs `AuditApp(package_name=args.package)`.

- Ensure `pyproject.toml` defines a console script:

```toml
[project.scripts]
vibanalyz = "vibanalyz.cli:main"
```

---

## Dockerfile (Chainguard Python, single image)

Create a `Dockerfile` that:

- Uses the latest Chainguard Python image:

```dockerfile
FROM cgr.dev/chainguard/python:latest
```

- Sets `WORKDIR /app`.
- Copies `pyproject.toml` and `src/` into the image.
- Installs the project with `pip install --no-cache-dir .`.
- Sets `ENTRYPOINT ["vibanalyz"]` so running the container launches the TUI.

The final image should be runnable like:

```bash
docker build -t vibanalyz .
docker run --rm -it vibanalyz requests
```

This should bring up the Textual UI, auto-run a stub audit for `requests`, and print stub findings and a stub score.

---

## Output format

When you respond to this prompt, generate **all project files** inline, organized by path, like:

```text
pyproject.toml
```toml
# contents
```

```text
src/vibanalyz/cli.py
```python
# contents
```

…and so on for all files described above.

Do not include any real network calls or Trivy/Grype integration yet. All functionality should be stubbed, but the structure should be realistic and ready to extend later.

