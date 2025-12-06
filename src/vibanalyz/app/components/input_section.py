"""Input section component wrapper."""

from textual.widgets import Input


class InputSection:
    """Wrapper for Input widget with helper methods."""

    def __init__(self, widget: Input):
        """Initialize with an Input widget."""
        self.widget = widget

    def get_value(self) -> str:
        """Get the current input value."""
        return self.widget.value.strip()

    def set_value(self, value: str) -> None:
        """Set the input value."""
        self.widget.value = value

    def clear(self) -> None:
        """Clear the input field."""
        self.widget.value = ""

    def get_package_info(self) -> tuple[str, str | None]:
        """
        Parse input to extract package name and optional version.
        
        Supports format: package==version or package@version
        
        Returns:
            Tuple of (package_name, version) where version may be None
        """
        input_text = self.get_value()
        
        # Check for == format (PEP 440 compatible)
        if "==" in input_text:
            parts = input_text.split("==", 1)
            package_name = parts[0].strip()
            version = parts[1].strip() if len(parts) > 1 else None
            return package_name, version
        
        # Check for @ format (alternative)
        if "@" in input_text:
            parts = input_text.split("@", 1)
            package_name = parts[0].strip()
            version = parts[1].strip() if len(parts) > 1 else None
            return package_name, version
        
        # No version specified
        return input_text, None

