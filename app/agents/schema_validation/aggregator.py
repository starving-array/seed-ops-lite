"""Aggregator responsible for merging, deduplicating, sorting, and summarizing skill results."""

from typing import Any

from app.agents.schema_validation.exceptions import AggregationException
from app.agents.schema_validation.models import (
    AgentFinding,
    ExecutiveSummaryResponse,
    SchemaValidationReport,
)
from app.llm.contracts.normalizer import AIContractNormalizer
from app.llm.contracts.request import AIContractRequest
from app.llm.gateway import LLMGateway
from app.prompts.loader import PromptAssetLoader
from app.prompts.renderer import PromptRenderer
from app.skills.models import SkillResponse


class SchemaValidationAggregator:
    """Aggregator that consolidates individual validation skill outcomes into a single report."""

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        """Initialize the aggregator with an optional LLMGateway."""
        self.gateway = gateway or LLMGateway()
        self.loader = PromptAssetLoader()

    async def aggregate(
        self,
        skill_responses: dict[str, SkillResponse[Any]],
        total_duration_ms: float,
    ) -> SchemaValidationReport:
        """Consolidate skill responses and generate the final unified report.

        Args:
            skill_responses: Mapping from skill name to SkillResponse.
            total_duration_ms: Total execution time for the agent's operations.

        Returns:
            SchemaValidationReport: Unified, validated validation report.

        Raises:
            AggregationException: If report generation fails.
        """
        try:
            findings: list[AgentFinding] = []
            warnings: list[str] = []
            execution_statistics: dict[str, Any] = {}
            executed_skills: list[str] = []

            # 1. Merge findings, collect warnings and statistics
            for name, response in skill_responses.items():
                executed_skills.append(name)
                execution_statistics[name] = {
                    "success": response.success,
                    "latency_ms": response.latency_ms,
                    "error": response.error_message,
                }

                if not response.success:
                    warnings.append(
                        f"Skill '{name}' failed execution: {response.error_message or 'Unknown error'}"
                    )
                    continue

                if response.data is None:
                    continue

                # Get findings from response data if they exist
                skill_findings = getattr(response.data, "findings", [])
                for finding in skill_findings:
                    findings.append(
                        AgentFinding(
                            category=name,
                            severity=finding.severity.lower().strip(),
                            description=finding.description,
                            suggestion=finding.suggestion,
                        )
                    )

            # 2. Deduplicate findings (using category, severity, description, suggestion)
            seen_findings = set()
            deduplicated_findings: list[AgentFinding] = []
            for f in findings:
                key = (f.category, f.severity, f.description, f.suggestion)
                if key not in seen_findings:
                    seen_findings.add(key)
                    deduplicated_findings.append(f)

            # 3. Sort findings by severity, then by category, then by description
            severity_weights = {"high": 3, "medium": 2, "low": 1}

            def sort_key(f: AgentFinding) -> tuple[int, str, str]:
                weight = severity_weights.get(f.severity, 0)
                # Sort weight descending, category and description ascending
                return (-weight, f.category, f.description)

            deduplicated_findings.sort(key=sort_key)

            # 4. Generate recommendations from unique non-empty suggestions
            recommendations: list[str] = []
            seen_recs = set()
            for f in deduplicated_findings:
                if f.suggestion and f.suggestion.strip():
                    clean_sug = f.suggestion.strip()
                    if clean_sug not in seen_recs:
                        seen_recs.add(clean_sug)
                        recommendations.append(clean_sug)

            # 5. Determine overall status based on findings
            high_count = sum(1 for f in deduplicated_findings if f.severity == "high")
            medium_count = sum(
                1 for f in deduplicated_findings if f.severity == "medium"
            )
            low_count = sum(1 for f in deduplicated_findings if f.severity == "low")

            if high_count > 0:
                overall_status = "fail"
            elif medium_count > 0 or low_count > 0:
                overall_status = "warning"
            else:
                overall_status = "pass"

            # 6. Generate Executive Summary (LLM Gateway call with fallback)
            summary = await self._generate_executive_summary(
                deduplicated_findings,
                executed_skills,
                high_count,
                medium_count,
                low_count,
            )

            return SchemaValidationReport(
                overall_status=overall_status,
                summary=summary,
                findings=deduplicated_findings,
                recommendations=recommendations,
                warnings=warnings,
                execution_statistics=execution_statistics,
                executed_skills=executed_skills,
                execution_duration_ms=round(total_duration_ms, 2),
            )

        except Exception as exc:
            if isinstance(exc, AggregationException):
                raise
            raise AggregationException(f"Aggregation process failed: {exc}") from exc

    async def _generate_executive_summary(
        self,
        findings: list[AgentFinding],
        executed_skills: list[str],
        high_cnt: int,
        med_cnt: int,
        low_cnt: int,
    ) -> str:
        """Call LLM via Gateway to summarize findings, with a clean deterministic fallback."""
        fallback_summary = (
            f"Database schema validation completed. Executed skills: {', '.join(executed_skills)}. "
            f"Found {high_cnt} high, {med_cnt} medium, and {low_cnt} low severity issues."
        )

        if not findings:
            return "Database schema validation completed successfully with no findings detected."

        try:
            # Render prompt
            template = self.loader.load_prompt("schema_validation_summary")
            findings_text = "\n".join(
                [
                    f"- [{f.category.upper()}] Severity: {f.severity}. Description: {f.description} (Suggestion: {f.suggestion or 'None'})"
                    for f in findings
                ]
            )
            prepared_prompt = PromptRenderer.render(
                template, {"findings": findings_text}
            )

            # Contract Request
            contract_request = AIContractRequest[ExecutiveSummaryResponse](
                prompt=prepared_prompt,
                response_schema=ExecutiveSummaryResponse,
                json_mode=True,
            )

            response = await AIContractNormalizer.execute_contract(
                self.gateway, contract_request
            )

            if response.success and response.data:
                return response.data.summary.strip()

            return fallback_summary

        except Exception:
            # Graceful fallback to avoid halting execution due to prompt/LLM transient errors
            return fallback_summary
