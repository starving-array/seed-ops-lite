"""Telemetry framework package.

Supports structured logging, metrics, tracing, and benchmarks.
"""

from app.telemetry.benchmark import BenchmarkReport
from app.telemetry.events import EventID, TelemetryEvent
from app.telemetry.logger import StructuredLogger, logger
from app.telemetry.metrics import (
    Counter,
    Histogram,
    MetricsProvider,
    NoOpCounter,
    NoOpHistogram,
    NoOpMetricsProvider,
)
from app.telemetry.performance import (
    AsyncPerformanceLogger,
    PerformanceLogger,
    log_llm_observation,
)
from app.telemetry.timer import Timer, timer
from app.telemetry.token_usage import TokenUsage
from app.telemetry.trace import NoOpSpan, NoOpTracer, Span, Tracer

__all__ = [
    "BenchmarkReport",
    "EventID",
    "TelemetryEvent",
    "StructuredLogger",
    "logger",
    "Counter",
    "Histogram",
    "MetricsProvider",
    "NoOpCounter",
    "NoOpHistogram",
    "NoOpMetricsProvider",
    "PerformanceLogger",
    "AsyncPerformanceLogger",
    "log_llm_observation",
    "Timer",
    "timer",
    "TokenUsage",
    "Span",
    "Tracer",
    "NoOpSpan",
    "NoOpTracer",
]
