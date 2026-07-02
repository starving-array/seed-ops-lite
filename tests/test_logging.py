"""Tests for Phase 2.4.4A — Production Logging Foundation.

Covers:
* Environment-aware formatter selection (pretty vs JSON)
* PrettyConsoleFormatter rendering
* ExceptionDeduplicator deduplication logic
* StructuredLogger level methods (trace, debug, info, success, warning, error, critical)
* PerformanceLogger / AsyncPerformanceLogger threshold detection
* log_llm_observation — only present values emitted
* Correlation context automatic injection from ExecutionContext
* workflow_id propagation through ExecutionContext
* EventID catalogue completeness
* Backward-compatibility of all public exports
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event_dict(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event": "Test message",
        "log_level": "info",
        "timestamp": "2026-07-03T00:00:00+00:00",
    }
    base.update(kwargs)
    return base


# ===========================================================================
# 1. EventID catalogue
# ===========================================================================


class TestEventIDCatalogue:
    def test_lifecycle_events_present(self) -> None:
        from app.telemetry.events import EventID

        required = [
            "APP_STARTED",
            "APP_STOPPED",
            "REDIS_CONNECTED",
            "REDIS_DISCONNECTED",
            "LLM_REQUEST",
            "LLM_RESPONSE",
            "LLM_ERROR",
            "EXPORT_STARTED",
            "EXPORT_COMPLETED",
            "GENERATION_STARTED",
            "GENERATION_COMPLETED",
            "SQLITE_CONNECTED",
            "RUNTIME_INITIALIZED",
            "RUNTIME_MEMORY_ACTIVATED",
            "RUNTIME_REDIS_LOST",
            "RUNTIME_REDIS_RECOVERED",
            "CARETAKER_STARTED",
            "PERF_SLOW_OPERATION",
        ]
        for name in required:
            assert hasattr(EventID, name), f"Missing EventID: {name}"

    def test_all_values_unique(self) -> None:
        from app.telemetry.events import EventID

        values = [e.value for e in EventID]
        assert len(values) == len(set(values)), "Duplicate EventID values detected"

    def test_event_id_is_str_enum(self) -> None:
        from app.telemetry.events import EventID

        assert isinstance(EventID.APP_STARTED, str)
        assert EventID.APP_STARTED == "APP-1001"


# ===========================================================================
# 2. Settings
# ===========================================================================


class TestLoggingSettings:
    def test_slow_log_threshold_default(self) -> None:
        from app.core.settings.config import settings

        assert settings.SLOW_LOG_THRESHOLD_MS == 500.0

    def test_log_pretty_default_false(self) -> None:
        from app.core.settings.config import settings

        assert settings.LOG_PRETTY is False

    def test_settings_fields_exist(self) -> None:
        from app.core.settings.config import Settings

        fields = Settings.model_fields
        assert "LOG_PRETTY" in fields
        assert "SLOW_LOG_THRESHOLD_MS" in fields


# ===========================================================================
# 3. ExecutionContext — workflow_id
# ===========================================================================


class TestExecutionContextWorkflowId:
    def test_workflow_id_field_exists(self) -> None:
        from app.core.context.context import ExecutionContext

        ctx = ExecutionContext(workflow_id="wf-abc-123")
        assert ctx.workflow_id == "wf-abc-123"

    def test_workflow_id_defaults_none(self) -> None:
        from app.core.context.context import ExecutionContext

        ctx = ExecutionContext()
        assert ctx.workflow_id is None

    def test_workflow_id_update_via_update_context(self) -> None:
        from app.core.context.context import (
            ExecutionContext,
            get_context,
            reset_context,
            set_context,
            update_context,
        )

        token = set_context(ExecutionContext())
        update_context(workflow_id="wf-xyz")
        assert get_context().workflow_id == "wf-xyz"
        reset_context(token)


# ===========================================================================
# 4. PrettyConsoleFormatter
# ===========================================================================


class TestPrettyConsoleFormatter:
    def _formatter(self) -> Any:
        from app.core.logging.formatters import PrettyConsoleFormatter

        return PrettyConsoleFormatter()

    def test_returns_string(self) -> None:
        fmt = self._formatter()
        result = fmt(MagicMock(), "info", _make_event_dict())
        assert isinstance(result, str)

    def test_message_in_output(self) -> None:
        fmt = self._formatter()
        result = fmt(MagicMock(), "info", _make_event_dict(event="Hello World"))
        assert "Hello World" in result

    def test_component_extracted(self) -> None:
        fmt = self._formatter()
        ed = _make_event_dict(component="LLMGateway")
        result = fmt(MagicMock(), "info", ed)
        assert "LLMGateway" in result

    def test_error_level_box(self) -> None:
        from app.core.logging.formatters import PrettyConsoleFormatter

        fmt = PrettyConsoleFormatter()
        ed = _make_event_dict(log_level="error", event="Something failed")
        result = fmt(MagicMock(), "error", ed)
        # Error output should include box-drawing chars
        assert "┌" in result or "└" in result or "│" in result

    def test_section_event_box(self) -> None:
        fmt = self._formatter()
        ed = _make_event_dict(
            event_id="APP-1001",
            event="Application Started",
            log_level="info",
        )
        result = fmt(MagicMock(), "info", ed)
        # Section events get a double-border box
        assert "╔" in result

    def test_duration_formatted(self) -> None:
        fmt = self._formatter()
        ed = _make_event_dict(duration_ms=142.5)
        result = fmt(MagicMock(), "info", ed)
        assert "142" in result or "duration" in result

    def test_does_not_crash_on_empty_event(self) -> None:
        fmt = self._formatter()
        result = fmt(
            MagicMock(), "info", {"event": "", "log_level": "debug", "timestamp": ""}
        )
        assert isinstance(result, str)

    def test_exc_info_renders_traceback(self) -> None:
        fmt = self._formatter()
        try:
            raise ValueError("kaboom")
        except ValueError as exc:
            ed = _make_event_dict(exc_info=exc)
            result = fmt(MagicMock(), "error", ed)
        assert "ValueError" in result or "kaboom" in result


# ===========================================================================
# 5. ExceptionDeduplicator
# ===========================================================================


class TestExceptionDeduplicator:
    def _dedup(self) -> Any:
        from app.core.logging.formatters import ExceptionDeduplicator

        return ExceptionDeduplicator()

    def test_first_exc_passes_through(self) -> None:
        dedup = self._dedup()
        exc = ValueError("test")
        ed = {"exc_info": exc}
        result = dedup(MagicMock(), "error", ed)
        assert "exc_info" in result

    def test_second_exc_stripped(self) -> None:
        dedup = self._dedup()
        exc = ValueError("test")
        ed1: dict[str, Any] = {"exc_info": exc}
        ed2: dict[str, Any] = {"exc_info": exc}
        dedup(MagicMock(), "error", ed1)  # first — passes through
        result = dedup(MagicMock(), "error", ed2)  # second — should be stripped
        assert "exc_info" not in result

    def test_different_exceptions_both_pass(self) -> None:
        dedup = self._dedup()
        exc1 = ValueError("one")
        exc2 = RuntimeError("two")
        ed1: dict[str, Any] = {"exc_info": exc1}
        ed2: dict[str, Any] = {"exc_info": exc2}
        r1 = dedup(MagicMock(), "error", ed1)
        r2 = dedup(MagicMock(), "error", ed2)
        assert "exc_info" in r1
        assert "exc_info" in r2

    def test_reset_clears_registry(self) -> None:
        dedup = self._dedup()
        exc = ValueError("test")
        ed1: dict[str, Any] = {"exc_info": exc}
        dedup(MagicMock(), "error", ed1)  # mark as seen
        dedup.reset()
        ed2: dict[str, Any] = {"exc_info": exc}
        result = dedup(MagicMock(), "error", ed2)  # should pass again
        assert "exc_info" in result

    def test_no_exc_info_passthrough(self) -> None:
        dedup = self._dedup()
        ed: dict[str, Any] = {"event": "no exception here"}
        result = dedup(MagicMock(), "info", ed)
        assert result == ed


# ===========================================================================
# 6. StructuredLogger level coverage
# ===========================================================================


class TestStructuredLoggerLevels:
    def _make_logger(self) -> Any:
        from app.telemetry.logger import StructuredLogger

        return StructuredLogger("test")

    def test_info_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.info(EventID.LOG_INFO, "test info")

    def test_debug_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.debug(EventID.LOG_INFO, "test debug")

    def test_warning_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.warning(EventID.LOG_WARNING, "test warning")

    def test_error_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.error(EventID.LOG_ERROR, "test error")

    def test_critical_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.critical(EventID.LOG_ERROR, "test critical")

    def test_trace_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.trace(EventID.LOG_INFO, "test trace")

    def test_success_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.success(EventID.LOG_INFO, "test success")

    def test_exception_does_not_raise(self) -> None:
        lg = self._make_logger()
        from app.telemetry.events import EventID

        lg.exception(EventID.LOG_ERROR, "test exception")

    def test_workflow_id_injected_from_context(self) -> None:
        """workflow_id from ExecutionContext flows into every log call."""
        from app.core.context.context import (
            ExecutionContext,
            reset_context,
            set_context,
        )
        from app.telemetry.events import EventID
        from app.telemetry.logger import StructuredLogger

        captured: dict[str, Any] = {}

        class _CapturingLogger:
            def info(self, _msg: str, **kwargs: Any) -> None:
                captured.update(kwargs)

        lg = StructuredLogger("wf-test")
        token = set_context(ExecutionContext(workflow_id="wf-capture"))

        with patch.object(lg, "_logger", _CapturingLogger()):
            lg.info(EventID.LOG_INFO, "workflow test")

        reset_context(token)
        assert captured.get("workflow_id") == "wf-capture"


# ===========================================================================
# 7. configure_logging() — environment selection
# ===========================================================================


class TestConfigureLoggingEnvironment:
    def test_configure_logging_runs_without_error(self) -> None:
        from app.core.logging.logging import configure_logging

        configure_logging()  # should not raise

    def test_pretty_mode_uses_pretty_formatter(self) -> None:
        from app.core.logging.formatters import PrettyConsoleFormatter
        from app.core.logging.logging import configure_logging

        with (
            patch("app.core.logging.logging.settings") as mock_settings,
            patch(
                "app.core.logging.formatters.PrettyConsoleFormatter",
                PrettyConsoleFormatter,
            ),
        ):
            mock_settings.LOG_PRETTY = True
            mock_settings.APP_ENV = "development"
            mock_settings.LOG_JSON_FORMAT = True
            mock_settings.LOG_LEVEL = "info"
            mock_settings.SLOW_LOG_THRESHOLD_MS = 500.0
            configure_logging()

    def test_is_pretty_mode_development(self) -> None:
        from app.core.logging.logging import _is_pretty_mode

        with patch("app.core.logging.logging.settings") as ms:
            ms.LOG_PRETTY = False
            ms.APP_ENV = "development"
            assert _is_pretty_mode() is True

    def test_is_pretty_mode_production(self) -> None:
        from app.core.logging.logging import _is_pretty_mode

        with patch("app.core.logging.logging.settings") as ms:
            ms.LOG_PRETTY = False
            ms.APP_ENV = "production"
            assert _is_pretty_mode() is False

    def test_is_pretty_mode_explicit_override(self) -> None:
        from app.core.logging.logging import _is_pretty_mode

        with patch("app.core.logging.logging.settings") as ms:
            ms.LOG_PRETTY = True
            ms.APP_ENV = "production"
            assert _is_pretty_mode() is True


# ===========================================================================
# 8. PerformanceLogger
# ===========================================================================


class TestPerformanceLogger:
    def test_elapsed_ms_populated(self) -> None:
        from app.telemetry.performance import PerformanceLogger

        with PerformanceLogger("test.op", threshold_ms=9999) as pl:
            pass
        assert pl.elapsed_ms >= 0.0

    def test_slow_op_emits_warning(self) -> None:
        """When elapsed_ms > threshold, a warning should be emitted."""
        from app.telemetry.performance import PerformanceLogger

        with patch("app.telemetry.performance.PerformanceLogger._emit") as mock_emit:
            with PerformanceLogger("test.slow", threshold_ms=0.0):
                pass
            mock_emit.assert_called_once()

    def test_fast_op_emits_debug(self) -> None:
        """When elapsed_ms < threshold, a debug event is emitted (not warning)."""
        from app.telemetry.performance import PerformanceLogger

        emitted: list[tuple[Any, str]] = []

        class _FakeLogger:
            def debug(self, _event_id: Any, msg: str, **_kwargs: Any) -> None:
                emitted.append(("debug", msg))

            def warning(self, _event_id: Any, msg: str, **_kwargs: Any) -> None:
                emitted.append(("warning", msg))

        pl = PerformanceLogger("test.fast", threshold_ms=99999)
        with patch("app.telemetry.performance.PerformanceLogger._emit"):
            pl.elapsed_ms = 1.0  # pretend very fast

        # Now test _emit directly with a mock logger
        pl2 = PerformanceLogger("test.fast2", threshold_ms=99999)
        pl2.elapsed_ms = 1.0
        with patch("app.telemetry.performance.logger", _FakeLogger()):
            pl2._emit()

        assert any(level == "debug" for level, _ in emitted)

    def test_context_manager_protocol(self) -> None:
        from app.telemetry.performance import PerformanceLogger

        pl = PerformanceLogger("cm.test", threshold_ms=9999)
        assert pl.__enter__() is pl
        pl.__exit__(None, None, None)
        assert pl.elapsed_ms >= 0.0


class TestAsyncPerformanceLogger:
    async def test_async_elapsed_populated(self) -> None:
        from app.telemetry.performance import AsyncPerformanceLogger

        async with AsyncPerformanceLogger("async.op", threshold_ms=9999) as apl:
            await asyncio.sleep(0)
        assert apl.elapsed_ms >= 0.0

    async def test_async_slow_op_warning(self) -> None:
        from app.telemetry.performance import AsyncPerformanceLogger

        with patch("app.telemetry.performance.PerformanceLogger._emit") as mock_emit:
            async with AsyncPerformanceLogger("async.slow", threshold_ms=0.0):
                await asyncio.sleep(0)
            mock_emit.assert_called_once()


# ===========================================================================
# 9. log_llm_observation
# ===========================================================================


class TestLLMObservabilityLogger:
    def test_success_emits_info(self) -> None:
        from app.telemetry.performance import log_llm_observation

        captured: dict[str, Any] = {}

        class _FakeLogger:
            def info(self, _event_id: Any, _msg: str, **kwargs: Any) -> None:
                captured["level"] = "info"
                captured.update(kwargs)

            def error(self, _event_id: Any, _msg: str, **_kwargs: Any) -> None:
                captured["level"] = "error"

        with patch("app.telemetry.performance.logger", _FakeLogger()):
            log_llm_observation(
                success=True,
                provider="Google",
                model="gemini-1.5-pro",
                prompt_tokens=100,
                completion_tokens=200,
                total_tokens=300,
                latency_ms=145.7,
            )

        assert captured.get("level") == "info"
        assert captured.get("provider") == "Google"
        assert captured.get("total_tokens") == 300

    def test_failure_emits_error(self) -> None:
        from app.telemetry.performance import log_llm_observation

        captured: dict[str, Any] = {}

        class _FakeLogger:
            def info(self, _event_id: Any, _msg: str, **_kwargs: Any) -> None:
                captured["level"] = "info"

            def error(self, _event_id: Any, _msg: str, **kwargs: Any) -> None:
                captured["level"] = "error"
                captured.update(kwargs)

        with patch("app.telemetry.performance.logger", _FakeLogger()):
            log_llm_observation(success=False, error="timeout")

        assert captured.get("level") == "error"
        assert captured.get("error") == "timeout"

    def test_none_values_not_emitted(self) -> None:
        """Fields that are None should never appear in the log payload."""
        from app.telemetry.performance import log_llm_observation

        captured: dict[str, Any] = {}

        class _FakeLogger:
            def info(self, _event_id: Any, _msg: str, **kwargs: Any) -> None:
                captured.update(kwargs)

            def error(self, _event_id: Any, _msg: str, **_kwargs: Any) -> None:
                pass

        with patch("app.telemetry.performance.logger", _FakeLogger()):
            log_llm_observation(
                success=True,
                provider="Google",
                # thinking_tokens intentionally omitted
            )

        assert "thinking_tokens" not in captured
        assert "cached_tokens" not in captured
        assert "finish_reason" not in captured

    def test_latency_rounded(self) -> None:
        from app.telemetry.performance import log_llm_observation

        captured: dict[str, Any] = {}

        class _FakeLogger:
            def info(self, _event_id: Any, _msg: str, **kwargs: Any) -> None:
                captured.update(kwargs)

            def error(self, _event_id: Any, _msg: str, **_kwargs: Any) -> None:
                pass

        with patch("app.telemetry.performance.logger", _FakeLogger()):
            log_llm_observation(success=True, latency_ms=142.12345678)

        assert captured.get("latency_ms") == 142.12


# ===========================================================================
# 10. Backward compatibility
# ===========================================================================


class TestBackwardCompatibility:
    def test_core_logging_exports(self) -> None:
        from app.core.logging import (
            add_correlation_id,
            configure_logging,
            correlation_id_ctx,
            logger,
        )

        assert callable(configure_logging)
        assert callable(add_correlation_id)
        assert logger is not None
        assert correlation_id_ctx is not None

    def test_core_logging_shim_proxy(self) -> None:
        """The legacy app/core/logging.py shim still resolves all names."""
        import importlib

        mod = importlib.import_module("app.core.logging")
        assert hasattr(mod, "configure_logging")
        assert hasattr(mod, "logger")
        assert hasattr(mod, "add_correlation_id")
        assert hasattr(mod, "correlation_id_ctx")

    def test_telemetry_logger_old_api(self) -> None:
        from app.telemetry.logger import StructuredLogger, logger

        assert isinstance(logger, StructuredLogger)

    def test_telemetry_package_exports(self) -> None:
        import app.telemetry as t

        assert hasattr(t, "PerformanceLogger")
        assert hasattr(t, "AsyncPerformanceLogger")
        assert hasattr(t, "log_llm_observation")

    def test_new_formatter_exports(self) -> None:
        from app.core.logging import (
            ExceptionDeduplicator,
            PrettyConsoleFormatter,
            exception_deduplicator,
        )

        assert PrettyConsoleFormatter is not None
        assert ExceptionDeduplicator is not None
        assert exception_deduplicator is not None


# ===========================================================================
# 11. Correlation context injection
# ===========================================================================


class TestCorrelationContextInjection:
    def test_correlation_id_from_context(self) -> None:
        from app.core.context.context import (
            ExecutionContext,
            reset_context,
            set_context,
        )
        from app.core.logging.logging import add_correlation_id

        token = set_context(
            ExecutionContext(correlation_id="corr-xyz", request_id="req-abc")
        )
        ed: dict[str, Any] = {}
        result = add_correlation_id(MagicMock(), "info", ed)
        reset_context(token)

        assert result.get("correlation_id") == "corr-xyz"
        assert result.get("request_id") == "req-abc"

    def test_workflow_id_from_context(self) -> None:
        from app.core.context.context import (
            ExecutionContext,
            reset_context,
            set_context,
        )
        from app.core.logging.logging import add_correlation_id

        token = set_context(ExecutionContext(workflow_id="wf-999"))
        ed: dict[str, Any] = {}
        add_correlation_id(MagicMock(), "info", ed)
        reset_context(token)

        assert ed.get("workflow_id") == "wf-999"

    def test_legacy_context_var_fallback(self) -> None:
        from app.core.logging.logging import add_correlation_id, correlation_id_ctx

        token = correlation_id_ctx.set("legacy-corr")
        ed: dict[str, Any] = {}
        add_correlation_id(MagicMock(), "info", ed)
        correlation_id_ctx.reset(token)

        assert ed.get("correlation_id") == "legacy-corr"
