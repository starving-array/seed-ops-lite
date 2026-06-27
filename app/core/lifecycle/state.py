"""Application operational state tracking."""

import sys
import time
from datetime import UTC, datetime

# Capture app startup timestamps
START_TIME = time.time()
START_DATETIME = datetime.now(UTC)


def get_uptime() -> float:
    """Calculate the system uptime in seconds.

    Returns:
        float: Uptime in seconds.
    """
    return time.time() - START_TIME


def get_startup_time_iso() -> str:
    """Get the startup time formatted as ISO 8601 string.

    Returns:
        str: ISO 8601 formatted startup time.
    """
    return START_DATETIME.isoformat()


def get_python_version() -> str:
    """Retrieve the runtime Python version.

    Returns:
        str: Python version string.
    """
    return sys.version
