"""Shared utilities for resolving the artifacts output directory."""

import os
from pathlib import Path


DEFAULT_ARTIFACTS_DIR = "/artifacts"
HOST_HINT_ENV = "ARTIFACTS_HOST_PATH"
ARTIFACTS_DIR_ENV = "ARTIFACTS_DIR"


def get_artifacts_dir() -> Path:
    """
    Resolve the artifacts directory, ensuring it exists.

    Uses ARTIFACTS_DIR if set, otherwise defaults to /artifacts.
    """
    target = os.getenv(ARTIFACTS_DIR_ENV, DEFAULT_ARTIFACTS_DIR)
    path = Path(target).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def get_host_hint(artifacts_dir: Path) -> str | None:
    """
    Return a host-friendly hint for where artifacts should appear.

    If ARTIFACTS_HOST_PATH is set, return that value.
    Otherwise, if ARTIFACTS_DIR was customized, provide a generic hint
    prompting users to check their bind mount for that container path.
    """
    host_hint = os.getenv(HOST_HINT_ENV)
    if host_hint:
        return host_hint

    # If ARTIFACTS_DIR is customized, remind users to check their mount
    env_dir = os.getenv(ARTIFACTS_DIR_ENV)
    if env_dir and env_dir != DEFAULT_ARTIFACTS_DIR:
        return f"Host bind mount for {artifacts_dir}"

    return None

