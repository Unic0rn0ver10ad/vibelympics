"""Domain exceptions for pipeline and task execution."""


class PipelineFatalError(Exception):
    """Exception raised by tasks to signal pipeline should terminate."""

    def __init__(self, message: str, source: str | None = None):
        """
        Initialize fatal error.
        
        Args:
            message: Error message describing the fatal condition
            source: Optional name of the task/component that raised the error
        """
        self.message = message
        self.source = source
        super().__init__(self.message)
