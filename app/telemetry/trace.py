"""Tracing interfaces to support future OpenTelemetry integrations."""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any


class Span(ABC):
    """Abstract interface representing a single tracing Span."""

    @abstractmethod
    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute tag on the span.

        Args:
            key: Attribute string key.
            value: Attribute value of any serializable type.
        """
        pass

    @abstractmethod
    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the span.

        Args:
            exception: Python exception instance.
        """
        pass

    @abstractmethod
    def end(self) -> None:
        """Terminate the span execution."""
        pass


class Tracer(ABC):
    """Abstract interface for tracing executions across the system."""

    @abstractmethod
    def start_span(self, name: str, parent_span: Span | None = None) -> Span:
        """Start a new span.

        Args:
            name: Span identifier name.
            parent_span: Optional parent span context.

        Returns:
            Span: The initialized Span instance.
        """
        pass

    @abstractmethod
    def span_context(self, name: str) -> AbstractContextManager[Span]:
        """Context manager to scope a block of code within a span.

        Args:
            name: Span identifier name.

        Returns:
            AbstractContextManager[Span]: Context manager yielding the Span.
        """
        pass


class NoOpSpan(Span):
    """No-op implementation of a tracing Span."""

    def set_attribute(self, key: str, value: Any) -> None:
        """Set attribute (No-op)."""
        pass

    def record_exception(self, exception: Exception) -> None:
        """Record exception (No-op)."""
        pass

    def end(self) -> None:
        """End span (No-op)."""
        pass


class NoOpTracer(Tracer):
    """No-op implementation of a Tracer."""

    def start_span(self, _name: str, _parent_span: Span | None = None) -> Span:
        """Start a new span (No-op)."""
        return NoOpSpan()

    def span_context(self, _name: str) -> AbstractContextManager[Span]:
        """Context manager to scope code in a no-op span."""

        class ContextManager(AbstractContextManager[Span]):
            def __enter__(self) -> Span:
                return NoOpSpan()

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_val: BaseException | None,
                exc_tb: Any,
            ) -> None:
                pass

        return ContextManager()
