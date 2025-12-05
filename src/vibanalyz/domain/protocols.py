"""Protocols (interfaces) for analyzers and tasks."""

from typing import Iterable, Protocol

from vibanalyz.domain.models import Context, Finding


class Analyzer(Protocol):
    """Protocol for security analyzers."""

    name: str

    def run(self, ctx: Context) -> Iterable[Finding]:
        """Run the analyzer and yield findings."""
        ...


class Task(Protocol):
    """Protocol for pipeline tasks."""

    name: str

    def run(self, ctx: Context) -> Context:
        """Run the task and return updated context."""
        ...

