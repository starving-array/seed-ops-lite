"""Production-grade logging formatters for SeedOps Lite.

Two formatters are provided:

* ``PrettyConsoleFormatter`` — a structlog processor that renders
  human-readable, color-coded output for local development.  Never
  used in production (APP_ENV != "development" unless LOG_PRETTY is
  explicitly set to True).

* ``ExceptionDeduplicator`` — a structlog processor that prevents
  duplicate stack traces from appearing at multiple layers.  Only the
  *innermost* site that sets ``exc_info=True`` emits the traceback;
  all outer sites receive a cleaned-up context-only log line.
"""

from __future__ import annotations

import threading
import traceback
from typing import Any

from structlog.types import EventDict

# ---------------------------------------------------------------------------
# ANSI colour palette
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"

_COLOURS: dict[str, str] = {
    "trace": "\033[38;5;244m",  # grey
    "debug": "\033[38;5;75m",  # steel-blue
    "info": "\033[38;5;39m",  # bright-blue
    "success": "\033[38;5;82m",  # bright-green
    "warning": "\033[38;5;214m",  # orange
    "error": "\033[38;5;196m",  # bright-red
    "critical": "\033[38;5;201m",  # magenta
}

_LEVEL_LABELS: dict[str, str] = {
    "trace": " TRACE ",
    "debug": " DEBUG ",
    "info": " INFO  ",
    "success": "SUCCESS",
    "warning": " WARN  ",
    "error": " ERROR ",
    "critical": " CRIT  ",
}

# Structured-data keys that are rendered inline on the first line.
_INLINE_KEYS = frozenset(
    {
        "component",
        "event_id",
        "correlation_id",
        "request_id",
        "workflow_id",
        "duration_ms",
        "phase",
    }
)

# Keys that should never be shown in pretty output (they're already in the
# header or are infrastructure noise).
_SUPPRESSED_KEYS = frozenset({"logger", "_logger", "level", "timestamp", "environment"})


class PrettyConsoleFormatter:
    """Structlog processor rendering colorised, human-readable log lines.

    Renders each event as::

        ┌─[ INFO  ]─[ LLMGateway ]────────────────────────────────────┐
        │ LLM API request succeeded  (duration_ms=142.3)
        │   provider        = Google
        │   model           = gemini-2.5-flash
        │   correlation_id  = abc-123
        └─────────────────────────────────────────────────────────────┘

    The box style varies by level (error/critical get a full double border).
    """

    # Lifecycle headings that get their own styled box header
    _SECTION_EVENTS: frozenset[str] = frozenset(
        {
            "APP-1001",  # Application Started
            "APP-1002",  # Application Stopped
            "RUNTIME-1004",  # Runtime Initialized
            "SQLITE-1001",  # SQLite Connected
            "REDIS-1001",  # Redis Connected
            "GEN-1001",  # Generation Started
            "GEN-1002",  # Generation Completed
            "EXPORT-1001",  # Export Started
            "EXPORT-1002",  # Export Completed
            "CARETAKER-1001",  # Caretaker Started
            "APP-STOPPED",  # Shutdown Complete
        }
    )

    def __call__(self, _logger: Any, _method: str, event_dict: EventDict) -> str:
        """Render *event_dict* as a pretty console string."""
        level = str(
            event_dict.pop("log_level", event_dict.pop("level", "info"))
        ).lower()
        event = str(event_dict.pop("event", ""))
        timestamp = str(event_dict.pop("timestamp", ""))
        event_id = str(event_dict.get("event_id", ""))

        colour = _COLOURS.get(level, _COLOURS["info"])
        label = _LEVEL_LABELS.get(level, " INFO  ")

        # Extract inline context fields
        inline_parts: list[str] = []
        for key in _INLINE_KEYS:
            if key in event_dict and key not in {"event_id"}:
                val = event_dict.get(key)
                if key == "duration_ms" and isinstance(val, int | float):
                    inline_parts.append(f"duration={val:.1f}ms")
                else:
                    inline_parts.append(f"{key}={val}")

        # Clean remaining dict of inline keys for clean display
        for key in _INLINE_KEYS:
            event_dict.pop(key, None)

        component = event_dict.pop("component", None)

        # Build header components
        level_badge = f"{colour}{_BOLD}[{label}]{_RESET}"
        comp_badge = f"{_DIM}[{component}]{_RESET}" if component else ""
        ts_badge = (
            f"{_DIM}{timestamp[:19].replace('T', ' ')}{_RESET}" if timestamp else ""
        )

        header_parts = [p for p in [ts_badge, level_badge, comp_badge] if p]
        header = "  ".join(header_parts)

        # Inline suffix (duration, correlation, etc.)
        inline_str = (
            f"  {_DIM}({', '.join(inline_parts)}){_RESET}" if inline_parts else ""
        )

        # Remaining structured keys (skip suppressed + already consumed)
        remaining: dict[str, Any] = {
            k: v
            for k, v in event_dict.items()
            if k not in _SUPPRESSED_KEYS and v is not None
        }

        exc_info = remaining.pop("exc_info", None)

        is_section = (
            event_id in self._SECTION_EVENTS
            or "summary" in event.lower()
            or "started" in event.lower()
            or "completed" in event.lower()
        )
        is_error = level in ("error", "critical")
        is_llm = (
            event_id in ("LLM-1001", "LLM-1002", "LLM-1003")
            or "llm" in str(component).lower()
        )

        lines: list[str] = []

        if is_llm:
            border_color = "\033[38;5;75m"  # Steel-blue for LLM
            lines.append(
                f"{border_color}┌───[ LLM OBSERVABILITY ]────────────────────────────────────────────────────┐{_RESET}"
            )
            lines.append(f"{border_color}│{_RESET}  {_BOLD}{event}{_RESET}{inline_str}")
            for k, v in remaining.items():
                lines.append(f"{border_color}│{_RESET}    {_DIM}{k:<20}{_RESET}: {v}")
            lines.append(
                f"{border_color}└────────────────────────────────────────────────────────────────────────────┘{_RESET}"
            )
        elif is_section:
            # Spring Boot style high impact startup/shutdown/workflow completion blocks
            width = 76
            border_color = (
                "\033[38;5;82m"
                if "completed" in event.lower() or "success" in event.lower()
                else colour
            )
            lines.append(f"{border_color}╔{'═' * width}╗{_RESET}")
            lines.append(
                f"{border_color}║{_RESET}  {_BOLD}{event!s:<{width - 4}}{_RESET}  {border_color}║{_RESET}"
            )
            if remaining:
                lines.append(f"{border_color}╠{'═' * width}╣{_RESET}")
                for k, v in remaining.items():
                    line_val = f"   {k:<24}: {v}"
                    lines.append(
                        f"{border_color}║{_RESET}  {_DIM}{line_val:<{width - 4}}{_RESET}  {border_color}║{_RESET}"
                    )
            lines.append(f"{border_color}╚{'═' * width}╝{_RESET}")
        elif is_error:
            # Standardized boxed error presenting component, cause, action, root cause
            border_color = _COLOURS["error"]
            lines.append(
                f"{border_color}┌───[ {label} ]─────────────────────────────────────────────────────────────┐{_RESET}"
            )
            lines.append(f"{border_color}│{_RESET}  {_BOLD}{event}{_RESET}{inline_str}")
            lines.append(
                f"{border_color}├────────────────────────────────────────────────────────────────────────────┤{_RESET}"
            )
            lines.append(
                f"{border_color}│{_RESET}  {_BOLD}Component{_RESET}  : {component or 'Unknown'}"
            )

            # Extract Cause & Action if present, else default
            cause = remaining.pop(
                "cause", remaining.pop("error", "An unexpected system error occurred.")
            )
            action = remaining.pop(
                "action",
                "Check logs, verify connection settings and configuration parameters.",
            )
            root_cause = remaining.pop("root_cause", None) or cause

            lines.append(
                f"{border_color}│{_RESET}  {_BOLD}Cause{_RESET}      : {cause}"
            )
            lines.append(
                f"{border_color}│{_RESET}  {_BOLD}Action{_RESET}     : {action}"
            )
            lines.append(
                f"{border_color}│{_RESET}  {_BOLD}Root Cause{_RESET} : {root_cause}"
            )

            if remaining:
                lines.append(f"{border_color}│{_RESET}  -- Context Details --")
                for k, v in remaining.items():
                    lines.append(
                        f"{border_color}│{_RESET}    {_DIM}{k:<18}{_RESET}: {v}"
                    )
            lines.append(
                f"{border_color}└────────────────────────────────────────────────────────────────────────────┘{_RESET}"
            )
        else:
            lines = [f"{header}  {event}{inline_str}"]
            for k, v in remaining.items():
                lines.append(f"    {_DIM}{k:<18}{_RESET}{v}")

        output = "\n".join(lines)

        # Append traceback if present
        if exc_info:
            if isinstance(exc_info, BaseException):
                tb = "".join(
                    traceback.format_exception(
                        type(exc_info), exc_info, exc_info.__traceback__
                    )
                )
            else:
                tb = "".join(traceback.format_exc())
            output += f"\n{colour}{tb}{_RESET}"

        return output


class ExceptionDeduplicator:
    """Structlog processor preventing duplicate stack traces in nested layers.

    When an exception propagates upward through multiple log calls (e.g.
    LLMGateway → AIContract → HybridSeeder → Workflow), only the *first*
    (innermost) site that passes ``exc_info=True`` emits the full traceback.
    All outer callers receive a clean context-only log line.

    The deduplication key is the exception's identity (``id(exc)``), tracked
    in a thread-local set that is reset at the start of each request by the
    ``reset_exception_registry`` processor (called automatically in the
    processor chain).

    Usage::

        # Innermost layer — logs full traceback:
        logger.exception(EventID.LLM_ERROR, "LLM call failed", exc_info=True)

        # Outer layer — logs context only (no dupe stack):
        logger.error(EventID.LOG_ERROR, "Generation aborted")
    """

    def __init__(self) -> None:
        self._local: threading.local = threading.local()

    def _registry(self) -> set[int]:
        if not hasattr(self._local, "seen"):
            self._local.seen = set()
        return self._local.seen  # type: ignore[no-any-return]

    def reset(self) -> None:
        """Clear the per-request exception registry.  Call at request start."""
        self._local.seen = set()

    def __call__(self, _logger: Any, _method: str, event_dict: EventDict) -> EventDict:
        """Strip duplicate exc_info from the event dict when already seen."""
        exc_info = event_dict.get("exc_info")
        if exc_info is None:
            return event_dict

        exc: BaseException | None = None
        if isinstance(exc_info, BaseException):
            exc = exc_info
        elif exc_info is True:
            import sys

            ei = sys.exc_info()
            exc = ei[1] if ei[1] is not None else None

        if exc is None:
            return event_dict

        key = id(exc)
        registry = self._registry()
        if key in registry:
            # Already logged — suppress traceback, keep context message
            event_dict.pop("exc_info", None)
        else:
            registry.add(key)

        return event_dict


# Module-level singleton — imported by the processor chain in logging.py
exception_deduplicator = ExceptionDeduplicator()
