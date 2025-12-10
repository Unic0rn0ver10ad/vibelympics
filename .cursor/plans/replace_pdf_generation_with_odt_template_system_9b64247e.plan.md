---
name: Replace PDF generation with ODT template system
overview: Replace the current ReportLab-based PDF generation with an ODT template-based system that uses LibreOffice for conversion. The new system will fill ODT templates with report data and convert them to PDF, providing more professional and customizable reports. All ReportLab code and dependencies must be completely removed.
todos:
  - id: adapt-pdf-service
    content: Replace ReportLab functions in pdf_report.py with ODT-based functions (extract_template_variables, fill_odt_template, convert_odt_to_pdf, get_template_path, find_libreoffice). Remove ALL ReportLab imports and code. Remove hardcoded test data from if __name__ block.
    status: pending
  - id: update-pdf-task
    content: Update generate_pdf_report.py task to use new ODT functions, wrap blocking operations in executor, maintain error handling patterns
    status: pending
    dependencies:
      - adapt-pdf-service
  - id: setup-template-location
    content: Create src/vibanalyz/data/ directory, copy template file, implement get_template_path() using importlib.resources or __file__
    status: pending
  - id: remove-reportlab-dockerfile
    content: "Remove ALL ReportLab/Pillow dependencies from Dockerfile: remove builder stage dependencies (lines 11-21), remove runtime stage libraries (lines 40-50), remove all comments referencing reportlab/Pillow"
    status: pending
  - id: install-libreoffice-dockerfile
    content: "Add LibreOffice manual installation to Dockerfile: download tarball from official site, extract to /usr/local/libreoffice, create symlink, install fonts (check Wolfi repos first, then manual if needed), verify installation"
    status: pending
    dependencies:
      - remove-reportlab-dockerfile
  - id: update-dependencies
    content: Remove reportlab from pyproject.toml completely, update pyproject.toml to include data files in package build
    status: pending
  - id: verify-template-variables
    content: Verify ODT template placeholder format matches variable names from extract_template_variables function
    status: pending
    dependencies:
      - adapt-pdf-service
---

# Replace PDF Generation with ODT Template System

## Overview

Replace the current ReportLab-based PDF generation (`services/pdf_report.py`) with an ODT template-based system that uses LibreOffice for conversion. The new system fills ODT templates with report data and converts them to PDF.

## Current State Analysis

**Current System:**

- Uses ReportLab (`reportlab` library) to generate PDFs from plain text
- `services/pdf_report.py` contains `format_report_text()` and `write_pdf_from_text()`
- `services/tasks/generate_pdf_report.py` task orchestrates PDF generation
- Data structure from `extract_report_data` matches new system expectations
- Dockerfile includes Pillow dependencies (used by reportlab)

**New System Requirements:**

- Uses LibreOffice headless mode to convert ODT templates to PDF
- Template file: `vibanalyz_audit_template.odt` (exists in project root)
- Functions: extract variables, fill ODT template, convert to PDF
- Same data structure: `repository_health`, `components`, `vulnerabilities`

## Implementation Plan

### 1. Adapt ODT PDF Generation Service

**File: `src/vibanalyz/services/pdf_report.py`**

Replace the current ReportLab-based implementation with ODT-based functions adapted from the provided code:

- **Remove**: `format_report_text()`, `write_pdf_from_text()`, `_wrap_lines()`, all ReportLab imports
- **Add**: 
- `extract_template_variables(data: dict) -> dict`: Extract variables from report data structure
- `fill_odt_template(template_path: str, variables: dict, output_path: str) -> None`: Fill ODT template with variables
- `convert_odt_to_pdf(odt_path: str, pdf_path: str, libreoffice_path: str | None = None) -> bool`: Convert ODT to PDF using LibreOffice
- `get_template_path() -> Path`: Resolve ODT template file location (handles both dev and Docker)
- `find_libreoffice() -> str | None`: Detect LibreOffice installation path

**Key Adaptations:**

- Remove print statements, use logging or return errors instead
- **Remove hardcoded test data**: Remove the entire `if __name__ == "__main__"` block with sample data dictionary (lines 485-556 in provided code)
- Handle template path resolution (package data or environment variable)
- Simplify LibreOffice detection for Docker (check `/usr/local/bin/soffice`, `/usr/local/libreoffice/program/soffice`, and other common paths)
- Raise `PipelineFatalError`-compatible exceptions
- Remove `process_report_data()` (not needed in service layer)

### 2. Update PDF Generation Task

**File: `src/vibanalyz/services/tasks/generate_pdf_report.py`**

Update the task to use the new ODT-based functions:

- Replace `format_report_text()` and `write_pdf_from_text()` calls
- Call new functions: `extract_template_variables()`, `fill_odt_template()`, `convert_odt_to_pdf()`
- Wrap blocking operations in `loop.run_in_executor()` (LibreOffice conversion is blocking)
- Handle template path resolution via `get_template_path()`
- Maintain existing error handling patterns (log to `ctx.log_display`, raise `PipelineFatalError`)
- Keep same async interface and status messages

### 3. Handle Template File Location

**Options:**

- **Option A (Recommended)**: Copy template to package data directory
- Create `src/vibanalyz/data/` directory
- Copy `vibanalyz_audit_template.odt` to `src/vibanalyz/data/`
- Use `importlib.resources` or `__file__` to locate template at runtime
- Update `pyproject.toml` to include data files in package

- **Option B**: Use environment variable for template path
- Allow `VIBANALYZ_TEMPLATE_PATH` environment variable override
- Default to relative path from package root or absolute path in Docker

**Implementation**: Use Option A for portability, with Option B as fallback.

### 4. Update Dockerfile

**File: `Dockerfile`**

**CRITICAL: Remove ALL ReportLab/Pillow dependencies first:**

- **Remove from builder stage** (lines 11-21): 
- Remove entire RUN block with Pillow build dependencies: `libjpeg-turbo-dev`, `zlib-dev`, `freetype-dev`, `lcms2-dev`, `openjpeg-dev`, `tiff-dev`, `libwebp-dev`
- Remove comment about "Pillow (used by reportlab)"

- **Remove from runtime stage** (lines 40-50):
- Remove from apk install: `libjpeg-turbo`, `zlib`, `freetype`, `lcms2`, `openjpeg`, `tiff`, `libwebp`
- Keep `curl`, `nodejs`, `npm`, `gcc`, `openssl-dev` (needed for other tools)
- Update comment to remove reference to Pillow

**Then add LibreOffice installation:**

- **LibreOffice is NOT available in Wolfi repos** - must install manually
- Download LibreOffice Linux tarball from official releases (e.g., `https://download.libreoffice.org/libreoffice/stable/`)
- Extract tarball and install to `/usr/local/libreoffice`
- Create symlink: `ln -s /usr/local/libreoffice/program/soffice /usr/local/bin/soffice`
- Make executable and accessible to nonroot user
- **Install fonts** (absolutely necessary for headless mode):
- Check Wolfi repos for font packages (`ttf-dejavu`, `ttf-liberation`, or similar)
- If not available, download and install fonts manually to `/usr/share/fonts/`
- Install minimal X11 libraries if needed (may be required even in headless mode)
- Verify installation with `soffice --version`
- Note: LibreOffice is large (~200MB+), but user confirmed this is acceptable

**Location**: Add after removing Pillow dependencies, before copying packages from builder.

### 5. Update Dependencies

**File: `pyproject.toml`**

- **Remove**: `reportlab>=4.0.0` completely (remove all remnants)
- **Keep**: No new Python dependencies needed (uses stdlib: `zipfile`, `xml.etree.ElementTree`, `subprocess`, `tempfile`)
- Update to include data files in package build (for template file)

### 6. Template Variable Mapping

Ensure variable names match between `extract_report_data` output and ODT template placeholders:

**Current mapping** (from provided code):

- `total_components`, `direct_dependencies`, `transitive_dependencies`, `dependency_depth`
- `license`, `repository_url`, `total_releases`
- `total_matches`, `unique_vulnerabilities`, `high_severity`, `moderate_severity`, `low_severity`

**Action**: Verify template uses `{{ variable_name }}` format and matches these names.

## Red Flags and Considerations

### 🚩 Red Flag 1: LibreOffice Size in Docker

- **Issue**: LibreOffice is large (~200MB+) and may increase image size significantly
- **Status**: User confirmed this is acceptable - no action needed

### 🚩 Red Flag 2: LibreOffice in Chainguard Images

- **Issue**: **CONFIRMED** - LibreOffice is NOT available in Wolfi package repositories via `apk`
- **Solution**: Must download and install LibreOffice manually from official releases
- Download LibreOffice Linux tarball from official site
- Extract and install similar to how Syft/Grype are installed
- May need to handle AppImage format or extract from DEB/RPM packages
- **Note**: Alternative base image is not an option per contest rules

### 🚩 Red Flag 3: Headless Mode Dependencies

- **Issue**: LibreOffice headless mode requires fonts for proper document rendering
- **Solution**: **User confirmed fonts are absolutely necessary**
- Install font packages available in Wolfi (check for `ttf-dejavu`, `ttf-liberation`, or similar)
- If fonts not available in Wolfi repos, download and install fonts manually
- May also need minimal X11 libraries even in headless mode (test during implementation)

### 🚩 Red Flag 4: Template File in Package

- **Issue**: Template file needs to be accessible in both dev and Docker environments
- **Mitigation**: Use `importlib.resources` (Python 3.9+) or `pkg_resources` to bundle template as package data.

### 🚩 Red Flag 5: Async Wrapper for Blocking Operations

- **Issue**: LibreOffice conversion is blocking and may take time
- **Mitigation**: Already handled in current task pattern - wrap in `loop.run_in_executor()`.

### 🚩 Red Flag 6: Error Handling Consistency

- **Issue**: New code uses different error patterns than existing codebase
- **Mitigation**: Adapt error handling to raise `PipelineFatalError` and log via `ctx.log_display`.

## Testing Considerations

- Test template variable extraction matches ODT placeholders
- Test LibreOffice detection in both dev and Docker environments
- Test PDF generation with various data combinations (missing fields, empty lists, etc.)
- Verify template file is accessible in Docker container
- Test error handling when LibreOffice is not found
- Verify async execution doesn't block UI
- Verify all ReportLab code is removed (no imports, no references)

## Files to Modify

1. `src/vibanalyz/services/pdf_report.py` - Complete rewrite with ODT functions, remove ALL ReportLab code and hardcoded test data
2. `src/vibanalyz/services/tasks/generate_pdf_report.py` - Update to use new functions
3. `Dockerfile` - Remove ALL ReportLab/Pillow dependencies (builder and runtime), add LibreOffice manual installation, add fonts
4. `pyproject.toml` - Remove `reportlab` dependency completely, add data files configuration
5. Create `src/vibanalyz/data/vibanalyz_audit_template.odt` - Copy template to package data
6. Update `pyproject.toml` to include data files in package build

## Files to Create

- `src/vibanalyz/data/__init__.py` - Make data directory a package
- `src/vibanalyz/data/vibanalyz_audit_template.odt` - Template file (copied from root)

## Migration Notes

- The `extract_report_data` task output structure already matches the new system's expectations
- No changes needed to data extraction or pipeline flow
- PDF output filename format remains the same: `vibanalyz-{package_name}-report.pdf`
- Report data structure is compatible (repository_health, components, vulnerabilities)
- **All ReportLab code must be completely removed** - verify no imports or references remain