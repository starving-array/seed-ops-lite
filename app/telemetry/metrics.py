"""Metrics recording interfaces to support future OpenTelemetry integrations."""

from abc import ABC, abstractmethod
from typing import Any


class Counter(ABC):
    """Abstract interface representing a monotonic accumulator counter metric."""

    @abstractmethod
    def add(self, value: int, tags: dict[str, Any] | None = None) -> None:
        """Add a value to the counter.

        Args:
            value: Monotonically increasing integer.
            tags: Optional dimensional metadata key-value pairs.
        """
        pass


class Histogram(ABC):
    """Abstract interface representing a distribution histogram metric."""

    @abstractmethod
    def record(self, value: float, tags: dict[str, Any] | None = None) -> None:
        """Record a performance value or distribution observation.

        Args:
            value: Float measurement value.
            tags: Optional dimensional metadata key-value pairs.
        """
        pass


class MetricsProvider(ABC):
    """Abstract interface representing a metrics recording engine provider."""

    @abstractmethod
    def get_counter(self, name: str, description: str) -> Counter:
        """Create or fetch a Counter metric instrument.

        Args:
            name: Metric identifier name.
            description: Narrative describing what the metric measures.

        Returns:
            Counter: Monotonic counter instance.
        """
        pass

    @abstractmethod
    def get_histogram(self, name: str, description: str) -> Histogram:
        """Create or fetch a Histogram metric instrument.

        Args:
            name: Metric identifier name.
            description: Narrative describing what the metric measures.

        Returns:
            Histogram: Histogram distribution instance.
        """
        pass


class NoOpCounter(Counter):
    """No-op implementation of a metrics Counter."""

    def add(self, value: int, tags: dict[str, Any] | None = None) -> None:
        """Add value (No-op)."""
        pass


class NoOpHistogram(Histogram):
    """No-op implementation of a metrics Histogram."""

    def record(self, value: float, tags: dict[str, Any] | None = None) -> None:
        """Record value (No-op)."""
        pass


class NoOpMetricsProvider(MetricsProvider):
    """No-op implementation of a MetricsProvider."""

    def get_counter(self, _name: str, _description: str) -> Counter:
        """Fetch counter (No-op)."""
        return NoOpCounter()

    def get_histogram(self, _name: str, _description: str) -> Histogram:
        """Fetch histogram (No-op)."""
        return NoOpHistogram()
