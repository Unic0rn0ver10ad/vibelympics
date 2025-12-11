"""Analyzer plugin system."""

from typing import List

from vibanalyz.domain.protocols import Analyzer

_ANALYZERS: List[Analyzer] = []


def register(analyzer: Analyzer) -> None:
    """Register an analyzer."""
    _ANALYZERS.append(analyzer)


def all_analyzers() -> List[Analyzer]:
    """Get all registered analyzers."""
    return list(_ANALYZERS)


# Import analyzers to trigger their registration
from vibanalyz.analyzers import metadata  # noqa: E402, F401

