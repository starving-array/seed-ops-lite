import time

import pytest

from app.export.models import ExportResult, ExportStatistics
from app.llm.models import LLMResponse
from app.observability.aggregator import MetricsAggregator
from app.observability.collector import MetricsCollector
from app.observability.exceptions import MetricsCollectionException
from app.observability.metrics import ResourceUsage
from app.observability.reporter import ExecutionReporter
from app.telemetry.token_usage import TokenUsage


def test_metrics_collection_defaults() -> None:
    collector = MetricsCollector()
    data = collector.get_data()

    assert data["total_records"] == "Not Yet Measured"
    assert data["total_tables"] == "Not Yet Measured"
    assert data["total_file_size_bytes"] == "Not Yet Measured"
    assert data["start_time"] is None
    assert data["end_time"] is None


def test_pipeline_start_and_end() -> None:
    collector = MetricsCollector()
    t_start = time.time()
    collector.start_pipeline(t_start)
    t_end = t_start + 5.0
    collector.end_pipeline(t_end)

    data = collector.get_data()
    assert data["start_time"] == t_start
    assert data["end_time"] == t_end


def test_record_stage_and_update() -> None:
    collector = MetricsCollector()
    resource = ResourceUsage(memory_bytes=1024, cpu_percent=12.5)

    collector.record_stage(
        stage_name="seeder",
        status="completed",
        duration_ms=150.0,
        resource_usage=resource,
        errors=["err1"],
        warnings=["warn1"],
        metadata={"tables": ["users"]},
    )

    data = collector.get_data()
    assert "seeder" in data["stages"]
    stage = data["stages"]["seeder"]
    assert stage.status == "completed"
    assert stage.metrics.duration_ms == 150.0
    assert stage.metrics.resource_usage.memory_bytes == 1024
    assert stage.errors == ["err1"]
    assert stage.warnings == ["warn1"]

    # Test updating existing stage
    collector.record_stage(
        stage_name="seeder",
        status="failed",
        errors=["err2"],
    )
    assert stage.status == "failed"
    assert stage.errors == ["err1", "err2"]


def test_record_llm_and_gateway_usage() -> None:
    collector = MetricsCollector()

    # 1. Direct LLM record
    collector.record_llm_usage(
        stage_name="seeder",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.003,
        calls_count=2,
    )

    data = collector.get_data()
    stage = data["stages"]["seeder"]
    assert stage.metrics.llm_calls == 2
    assert stage.metrics.prompt_tokens == 100
    assert stage.metrics.completion_tokens == 50
    assert stage.metrics.llm_cost_usd == 0.003

    # 2. Extract from LLMResponse
    usage = TokenUsage(
        model="gemini-1.5-pro",
        provider="Google",
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
        estimated_cost=0.006,
        latency_ms=1200.0,
    )
    response = LLMResponse(
        text="Hello",
        usage=usage,
    )

    collector.record_gateway_response(stage_name="seeder", response=response)
    assert stage.metrics.llm_calls == 3
    assert stage.metrics.prompt_tokens == 300
    assert stage.metrics.completion_tokens == 150
    assert stage.metrics.llm_cost_usd == pytest.approx(0.009)


def test_record_export_result() -> None:
    collector = MetricsCollector()
    stats = ExportStatistics(
        total_records=500,
        total_tables=5,
        file_size_bytes=10240,
        duration_ms=45.0,
    )
    result = ExportResult(
        success=True,
        serialized_data={},
        output_files={},
        statistics=stats,
    )

    collector.record_export_result(result)
    data = collector.get_data()

    assert data["total_records"] == 500
    assert data["total_tables"] == 5
    assert data["total_file_size_bytes"] == 10240


def test_metrics_collection_exception() -> None:
    collector = MetricsCollector(execution_id="non_existent")
    # Delete it from class dictionary to force error
    MetricsCollector._global_data.pop("non_existent", None)

    with pytest.raises(MetricsCollectionException):
        collector.get_data()


def test_aggregation_and_reporting() -> None:
    collector = MetricsCollector()
    collector.start_pipeline(time.time() - 10)

    # Successful stage
    collector.record_stage(
        stage_name="seeder",
        status="completed",
        duration_ms=100.0,
        resource_usage=ResourceUsage(memory_bytes=1000, cpu_percent=1.0),
    )

    # Failed stage
    collector.record_stage(
        stage_name="binding",
        status="failed",
        duration_ms=50.0,
        resource_usage=ResourceUsage(memory_bytes=2000, cpu_percent=2.0),
        errors=["integrity error"],
    )

    collector.end_pipeline(time.time())

    aggregator = MetricsAggregator(collector)
    summary = aggregator.calculate_summary()

    # Since binding stage failed, overall status must be failed
    assert summary.status == "failed"
    assert summary.stages_executed == 2
    assert summary.success_count == 1
    assert summary.failure_count == 1
    assert summary.duration_ms > 0.0

    pipeline_metrics = aggregator.aggregate_pipeline_metrics()
    assert len(pipeline_metrics.stages) == 2

    reporter = ExecutionReporter(aggregator)
    report = reporter.generate_report()

    assert report.execution_id == collector.execution_id
    assert report.summary.status == "failed"

    # Verify markdown report format
    md_summary = reporter.generate_markdown_summary()
    assert "# Pipeline Execution Report" in md_summary
    assert "| Stage Name | Status |" in md_summary
    assert "seeder" in md_summary
    assert "binding" in md_summary


def test_execution_context_cleanup_success() -> None:
    collector = MetricsCollector()
    collector.start_pipeline()
    collector.record_stage("seeder", "completed", 50.0)
    collector.end_pipeline()

    aggregator = MetricsAggregator(collector)
    reporter = ExecutionReporter(aggregator)

    # Before report generation, data is present
    assert collector.execution_id in MetricsCollector._global_data

    # Generate report
    report = reporter.generate_report()
    assert report.summary.status == "completed"

    # After report generation, data must be cleaned up from global dict
    assert collector.execution_id not in MetricsCollector._global_data


def test_execution_context_cleanup_failure() -> None:
    collector = MetricsCollector()
    collector.start_pipeline()
    collector.record_stage("seeder", "failed", 50.0)
    collector.end_pipeline()

    aggregator = MetricsAggregator(collector)
    reporter = ExecutionReporter(aggregator)

    # Generate report
    report = reporter.generate_report()
    assert report.summary.status == "failed"

    # After report generation, data must be cleaned up even on failed executions
    assert collector.execution_id not in MetricsCollector._global_data


def test_repeated_executions_do_not_leak_memory() -> None:
    initial_count = len(MetricsCollector._global_data)

    for i in range(10):
        collector = MetricsCollector()
        collector.start_pipeline()
        collector.record_stage(f"stage_{i}", "completed", 10.0)
        collector.end_pipeline()

        agg = MetricsAggregator(collector)
        rep = ExecutionReporter(agg)
        rep.generate_report()

    # The length of _global_data should remain equal to the initial count
    assert len(MetricsCollector._global_data) == initial_count


def test_context_manager_cleanup() -> None:
    exec_id = None
    with MetricsCollector() as collector:
        exec_id = collector.execution_id
        collector.start_pipeline()
        collector.record_stage("seeder", "completed", 30.0)
        assert exec_id in MetricsCollector._global_data

    # Exiting the block should trigger release automatically
    assert exec_id not in MetricsCollector._global_data


def test_concurrent_metric_collection() -> None:
    import concurrent.futures

    collector = MetricsCollector()
    collector.start_pipeline()

    def record_dummy_stage(stage_num: int) -> None:
        # Record stage timing and LLM usage concurrently
        collector.record_stage(f"stage_{stage_num}", "completed", 10.0)
        collector.record_llm_usage(
            stage_name=f"stage_{stage_num}",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_usd=0.0001,
        )

    # Execute 20 concurrent stage recordings
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(record_dummy_stage, i) for i in range(20)]
        concurrent.futures.wait(futures)

    data = collector.get_data()
    assert len(data["stages"]) == 20

    # Ensure all stages are present and correctly aggregated
    for i in range(20):
        stage = data["stages"][f"stage_{i}"]
        assert stage.metrics.llm_calls == 1
        assert stage.metrics.total_tokens == 15

    # Clean up at the end
    collector.release()
