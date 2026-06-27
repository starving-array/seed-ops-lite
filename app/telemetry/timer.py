"""Performance timing utility for measuring execution durations."""

import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any


class Timer(AbstractContextManager["Timer"]):
    """A context manager to measure execution time of blocks of code."""

    def __init__(
        self,
        name: str,
        callback: Callable[[str, float], None] | None = None,
    ) -> None:
        """Initialize the Timer.

        Args:
            name: Name of the timed block of code.
            callback: Optional callback receiving (name, elapsed_ms) when block exits.
        """
        self.name = name
        self.callback = callback
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.elapsed_ms: float | None = None

    def __enter__(self) -> "Timer":
        """Enter the timed block."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the timed block and calculate elapsed duration."""
        self.end_time = time.perf_counter()
        if self.start_time is not None:
            self.elapsed_ms = (self.end_time - self.start_time) * 1000.0
            if self.callback:
                self.callback(self.name, self.elapsed_ms)


def timer(name: str, callback: Callable[[str, float], None] | None = None) -> Timer:
    """Helper function to instantiate a new Timer context manager.

    Args:
        name: Name of the timed block.
        callback: Optional callback receiving (name, elapsed_ms) when block exits.

    Returns:
        Timer: The timer context manager instance.
    """
    return Timer(name, callback)
