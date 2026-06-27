"""CLI Commands synchronous main function entry points."""

import asyncio
import sys
from collections.abc import Sequence

from app.cli.cli import CLIApplication


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous entry point mapping to async CLIApplication runtime."""
    if argv is None:
        argv = sys.argv[1:]
    app = CLIApplication()
    return asyncio.run(app.run(argv))


if __name__ == "__main__":
    sys.exit(main())
