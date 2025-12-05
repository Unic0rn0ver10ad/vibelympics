# vibanalyz – TODO / Next Steps

This document enumerates important next steps for expanding the MVP into a functioning package ecosystem auditor. Items are grouped by thematic area. Heavy emphasis is placed on **vulnerability analysis**, **dependency graph inspection**, and **supply chain risk assessment**, as these represent the core upcoming work.

---

## 1. Implement Real PyPI Metadata Fetching

### Tasks
- Replace the stub `fetch_package_metadata_stub` with a real PyPI API integration using the JSON endpoints:
  - `https://pypi.org/pypi/<package>/json`
- Parse:
  - `info` → name, version, summary, project URLs
  - `releases` → release history
  - `requires_dist` → direct dependencies
- Update `PackageMetadata` to hold additional useful fields:
  - `maintainers` (if available)
  - `home_page`, `project_urls`
  - `requires_dist: list[str] | None`

### Integration
- Update the pipeline task `FetchPyPi` to use the new adapter.
- Add a new analyzer to evaluate PyPI metadata (age of project, update frequency, etc.).

---

## 2. Clone or Download the Package Source

### Tasks
- Resolve the repository URL from `project_urls`.
- Implement a `repo_client` module that:
  - Clones a Git repo to a temporary directory.
  - Or downloads the source distribution (`sdist`) if a repo is unavailable.
- Update `RepoInfo` to include:
  - `path: pathlib.Path`
  - `is_git_repo: bool`
  - basic metadata (repo URL, default branch, etc.)

### Integration
- Add a new task: `CloneRepo`.
- Add a new analyzer: `RepoHealthAnalyzer`.

---

## 3. Integrate Trivy for SBOM Generation

### Tasks
- Add a new adapter: `trivy_runner.py`.
  - Command: `trivy fs --format cyclonedx --output sbom.json <repo_path>`
  - Store the parsed JSON in `Sbom.raw`.
- Error-handling rules:
  - If Trivy is missing, generate a `Finding` and continue.
  - If the repo path is missing, skip SBOM generation.

### Integration
- Add a new pipeline task: `GenerateSbom`.
- Add a new analyzer: `SbomAnalyzer`.
  - For now, just count components.
- PDF report: include basic SBOM summary.

---

## 4. Known Vulnerabilities & Dependency Graph (Key Feature)

This is central to supply chain risk evaluation. Multiple concrete steps are required.

### 4.1 Parse and Represent Dependencies

#### Tasks
- Extract `requires_dist` from PyPI metadata.
- Parse dependency strings (e.g., `requests>=2.0,<3.0`) into structured objects.
- Extend `PackageMetadata`:
  - `dependencies: list[Dependency]` where `Dependency` is a dataclass containing:
    - `name`
    - `specifier` (version constraints)

#### Integration
- Add a new analyzer: `DependencyAnalyzer`.
  - Count direct dependencies.
  - Flag packages with unusually large dependency surfaces.

### 4.2 Build a Recursive Dependency Graph

#### Tasks
- Create a graph structure:
  - Nodes: package names
  - Edges: parent → dependency
- Implement a recursive dependency resolver:
  - Max depth configurable (prevent infinite recursion or huge trees).
  - Cache metadata results so each package is fetched once.
  - Record issues such as missing packages or broken metadata.

#### Integration
- Add a task: `ResolveDependencyGraph`.
- Extend `Context` to hold:
  - `dependency_graph: DependencyGraph | None`
- Add PDF and CLI sections summarizing:
  - Node/edge count
  - Maximum depth
  - Breadth at each level

### 4.3 Integrate Grype for CVE Detection

#### Tasks
- Add an adapter: `grype_runner.py`.
  - Preferred mode: run Grype on the **SBOM** output from Trivy.
  - Command: `grype sbom:sbom.json -o json`.
  - Parse into `VulnReport.raw`.

#### Integration
- Add a pipeline task: `AnalyzeVulns`.
- Add a new analyzer: `VulnAnalyzer` that:
  - Counts vulnerabilities by severity.
  - Maps vulnerabilities to the dependency tree when possible.
  - Flags critical issues.

#### Findings to Generate
- Packages with known CVEs.
- Dependencies containing high/critical vulnerabilities.
- Deep dependency chains where CVEs are found near the root.
- Missing fix versions.

### 4.4 Supply Chain Risk Heuristics

Implement heuristics such as:
- Extremely wide or deep dependency graphs → higher risk.
- Single maintainer upstream packages.
- Packages with few downloads but many dependencies.
- Packages depending on deprecated/abandoned dependencies.

Add these as additional analyzers with their own `Finding` messages.

---

## 5. Expand PDF Reporting

### Tasks
- Update stub PDF to contain:
  - Package name
  - Version
  - Summary
  - Risk score
  - Number of findings by severity
  - SBOM component count
  - Vulnerability counts (critical/high/medium/low)
  - Dependency graph statistics

### Future Enhancements
- Multi-page reports.
- Tables of top CVEs.
- Graph visualizations exported as images and embedded into PDF.

---

## 6. Improve CLI and TUI Features

### Tasks
- Add progress indicators for each pipeline task.
- Add detail panes:
  - Findings list
  - Dependency graph summary
  - Vulnerability summary
- Add keyboard shortcuts:
  - `r` – rerun audit
  - `p` – open PDF
  - `j` – export JSON summary

---

## 7. Error Handling and Diagnostics

### Tasks
- When external tools are missing (Trivy/Grype), log a clear warning and continue.
- Handle missing or invalid metadata gracefully.
- Add retry/backoff for network operations.
- Provide a debug mode (`--debug`) to show pipeline internals.

---

## 8. Testing and Validation

### Tasks
- Unit tests for:
  - PyPI metadata parsing
  - SBOM parsing
  - Vulnerability parsing
  - Dependency graph builder
- Mock subprocess calls for Trivy and Grype.
- Integration test: run full pipeline on a known package with expected results.

---

## 9. Container Image Enhancements

### Tasks
- Add healthcheck.
- Add labels/metadata (OCI annotations).
- Ensure Trivy and Grype binary installation works cleanly in Chainguard base image.
- Add multi-stage build option for faster iteration.

---

## 10. Future Major Features (Post-MVP)

- Repository hijacking analysis (RepoJacking detection).
- Maintainer trust scoring.
- Poisoned package heuristics (sudden release spike, README changes, new maintainers).
- Source code static analysis (flag dangerous APIs in installer paths).
- Web UI mode (FastAPI + frontend) using the same pipeline backend.

---

This TODO document will evolve as milestones are completed and the architecture matures.

