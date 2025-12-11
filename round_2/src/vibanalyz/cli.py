"""CLI entry point."""

import argparse
import sys

from vibanalyz.app.main import AuditApp


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="vibanalyz - Package security auditing tool (MVP stub)"
    )
    parser.add_argument(
        "package",
        nargs="?",
        help="Package name to audit (optional, can be entered in TUI)",
    )
    
    args = parser.parse_args()
    
    app = AuditApp(package_name=args.package)
    app.run()


if __name__ == "__main__":
    main()

