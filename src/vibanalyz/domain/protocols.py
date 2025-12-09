"""Protocols (interfaces) for analyzers and tasks."""

from typing import Awaitable, Iterable, Protocol

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

    def get_status_message(self, ctx: Context) -> str:
        """Generate status message for this task."""
        ...

    def run(self, ctx: Context) -> Awaitable[Context] | Context:
        """Run the task and return updated context. Can be async or sync."""
        ...

