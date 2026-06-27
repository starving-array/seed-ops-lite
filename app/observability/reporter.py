"""ExecutionReporter compiling final execution reports."""

from app.observability.aggregator import MetricsAggregator
from app.observability.models import ExecutionReport
from app.observability.telemetry import ObservabilityTelemetry


class ExecutionReporter:
    """Compiles unified execution analytics reports and markdown summaries."""

    def __init__(self, aggregator: MetricsAggregator) -> None:
        """Initialize ExecutionReporter with a metrics aggregator."""
        self.aggregator = aggregator
        self._report: ExecutionReport | None = None

    def generate_report(self) -> ExecutionReport:
        """Generate a complete typed execution analysis report."""
        if self._report is not None:
            return self._report

        summary = self.aggregator.calculate_summary()
        pipeline_metrics = self.aggregator.aggregate_pipeline_metrics()

        report = ExecutionReport(
            execution_id=self.aggregator.collector.execution_id,
            summary=summary,
            pipeline_metrics=pipeline_metrics,
        )

        ObservabilityTelemetry.log_report_generated(
            execution_id=report.execution_id,
            status=summary.status,
            stages_count=summary.stages_executed,
        )

        self.aggregator.collector.release()
        self._report = report

        return report

    def generate_markdown_summary(self) -> str:
        """Expose execution metrics and summaries as a structured markdown document."""
        report = self.generate_report()
        summary = report.summary
        metrics = report.pipeline_metrics

        md = []
        md.append(f"# Pipeline Execution Report (ID: {report.execution_id})")
        md.append("")
        md.append("## Summary")
        md.append(f"- **Status**: `{summary.status.upper()}`")
        md.append(f"- **Start Time**: {summary.start_time or 'Unknown'}")
        md.append(f"- **End Time**: {summary.end_time or 'Unknown'}")

        dur_str = (
            f"{summary.duration_ms:.2f} ms"
            if isinstance(summary.duration_ms, int | float)
            else f"`{summary.duration_ms}`"
        )
        md.append(f"- **Duration**: {dur_str}")
        md.append(f"- **Stages Executed**: {summary.stages_executed}")
        md.append(f"- **Success Count**: {summary.success_count}")
        md.append(f"- **Failure Count**: {summary.failure_count}")
        md.append("")
        md.append("## Stage Breakdowns")
        md.append("")
        md.append(
            "| Stage Name | Status | Duration (ms) | Memory | CPU | LLM Calls | Cost (USD) | Errors / Warnings |"
        )
        md.append("|---|---|---|---|---|---|---|---|")

        for name, stage in metrics.stages.items():
            res = stage.metrics.resource_usage
            mem = (
                f"{res.memory_bytes} bytes"
                if isinstance(res.memory_bytes, int)
                else f"`{res.memory_bytes}`"
            )
            cpu = (
                f"{res.cpu_percent}%"
                if isinstance(res.cpu_percent, int | float)
                else f"`{res.cpu_percent}`"
            )

            dur = (
                f"{stage.metrics.duration_ms:.2f}"
                if isinstance(stage.metrics.duration_ms, int | float)
                else f"`{stage.metrics.duration_ms}`"
            )
            cost = (
                f"${stage.metrics.llm_cost_usd:.4f}"
                if isinstance(stage.metrics.llm_cost_usd, int | float)
                else f"`{stage.metrics.llm_cost_usd}`"
            )

            issues = []
            if stage.errors:
                issues.append(f"Errors: {len(stage.errors)}")
            if stage.warnings:
                issues.append(f"Warnings: {len(stage.warnings)}")
            issues_str = ", ".join(issues) if issues else "None"

            md.append(
                f"| {name} | `{stage.status}` | {dur} | {mem} | {cpu} | {stage.metrics.llm_calls} | {cost} | {issues_str} |"
            )

        return "\n".join(md)
