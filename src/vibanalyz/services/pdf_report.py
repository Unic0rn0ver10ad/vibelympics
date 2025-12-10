"""HTML-based PDF report generation using WeasyPrint and Jinja2."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError
from weasyprint import HTML

from vibanalyz.domain.exceptions import PipelineFatalError

logger = logging.getLogger(__name__)


def extract_template_variables(data: dict) -> dict:
    """Map structured report data to template variables."""
    variables: dict[str, str | int | None] = {}

    # Extract package information
    variables["package_name"] = data.get("package_name", "N/A")
    variables["package_version"] = data.get("package_version", "N/A")
    variables["repo_name"] = data.get("repo_name", "N/A")
    variables["package_url"] = data.get("package_url", "N/A")

    components = data.get("components") or {}
    variables["total_components"] = components.get("total_components", "N/A")
    variables["direct_dependencies"] = components.get("direct_dependencies", "N/A")
    variables["transitive_dependencies"] = components.get("transitive_dependencies", "N/A")
    variables["dependency_depth"] = components.get("dependency_depth", "N/A")

    repo_health = data.get("repository_health") or {}
    variables["license"] = repo_health.get("license", "N/A")
    variables["repository_url"] = repo_health.get("repository", "N/A")
    variables["total_releases"] = repo_health.get("total_releases", "N/A")

    vulns = data.get("vulnerabilities") or {}
    variables["total_matches"] = vulns.get("total_matches", "N/A")
    variables["unique_vulnerabilities"] = vulns.get("unique_vulnerabilities", "N/A")
    variables["high_severity"] = vulns.get("high_severity", "N/A")
    variables["moderate_severity"] = vulns.get("moderate_severity", "N/A")
    variables["low_severity"] = vulns.get("low_severity", "N/A")

    return variables


def get_template_path() -> Path:
    """Resolve the bundled XHTML template path, with optional override."""
    env_value = os.environ.get("VIBANALYZ_TEMPLATE_PATH")
    if env_value:
        candidate = Path(env_value)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Template file not found at VIBANALYZ_TEMPLATE_PATH: {candidate}")

    try:
        from importlib import resources

        template = resources.files("vibanalyz.data") / "vibanalyz_audit_template.xhtml"  # type: ignore[attr-defined]
        if template.exists():
            return Path(template)
    except Exception as exc:  # pragma: no cover - defensive
        raise PipelineFatalError(
            message=f"Failed to resolve template path: {exc}",
            source="get_template_path",
        ) from exc

    raise FileNotFoundError("Bundled template vibanalyz_audit_template.xhtml not found.")


def render_html_template(template_path: str | Path, variables: dict) -> str:
    """Render the XHTML template with the provided variables using Jinja2."""
    template_path = Path(template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    try:
        env = Environment(
            loader=FileSystemLoader(template_path.parent),
            autoescape=True,
        )
        template = env.get_template(template_path.name)
        return template.render(**variables)
    except TemplateError as exc:
        raise PipelineFatalError(
            message=f"Failed to render template: {exc}",
            source="render_html_template",
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise PipelineFatalError(
            message=f"Unexpected error rendering template: {exc}",
            source="render_html_template",
        ) from exc


def convert_html_to_pdf(html_content: str, pdf_path: str | Path) -> Path:
    """Render HTML content to a PDF file using WeasyPrint."""
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        HTML(string=html_content, base_url=str(pdf_path.parent)).write_pdf(str(pdf_path))
    except Exception as exc:
        raise PipelineFatalError(
            message=f"WeasyPrint failed to generate PDF: {exc}",
            source="convert_html_to_pdf",
        ) from exc

    if not pdf_path.exists():
        raise PipelineFatalError(
            message=f"PDF not created at expected location: {pdf_path}",
            source="convert_html_to_pdf",
        )

    return pdf_path

