"""Human-in-the-Loop (HITL) Approval Workflow Engine."""

# ruff: noqa: RET508, RET505, S110, PLR0911, SIM102

import time

from app.core.logging.logging import logger
from app.platform.hitl.models import (
    ApprovalDecision,
    ApprovalLifecycle,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalSession,
    ApprovalStatistics,
    DecisionType,
    Reviewer,
)
from app.telemetry.events import EventID


class ReviewerResolver:
    """Resolves reviewer assignments and checks reviewer validity."""

    def __init__(self) -> None:
        pass

    def resolve_reviewers(
        self,
        target_reviewers: list[Reviewer],
        active_registry_users: list[str] | None = None,
    ) -> list[Reviewer]:
        """Validate and resolve active reviewers from candidates."""
        resolved: list[Reviewer] = []
        seen_ids = set()

        for reviewer in target_reviewers:
            # Enforce unique assignment checks
            if reviewer.reviewer_id in seen_ids:
                continue

            # Basic eligibility checks
            if not reviewer.reviewer_id or not reviewer.name:
                raise ValueError(f"Invalid reviewer model parameters: {reviewer}")

            if active_registry_users is not None:
                if reviewer.reviewer_id not in active_registry_users:
                    raise PermissionError(
                        f"Reviewer '{reviewer.reviewer_id}' not present in active user registry."
                    )

            seen_ids.add(reviewer.reviewer_id)
            resolved.append(reviewer)

        return resolved


class ApprovalPolicyEvaluator:
    """Evaluates consensus policies across reviewer decisions."""

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        policy: ApprovalPolicy,
        reviewers: list[Reviewer],
        decisions: list[ApprovalDecision],
    ) -> ApprovalLifecycle:
        """Determines approval completion state based on the consensus policy."""
        if not decisions:
            return ApprovalLifecycle.PENDING

        assigned_ids = {r.reviewer_id for r in reviewers}
        valid_decisions = [d for d in decisions if d.reviewer_id in assigned_ids]

        # Index latest decision per reviewer to avoid double votes
        latest_decisions: dict[str, ApprovalDecision] = {}
        for d in valid_decisions:
            latest_decisions[d.reviewer_id] = d

        total_reviewers = len(reviewers)
        decision_counts = {t: 0 for t in DecisionType}
        for d in latest_decisions.values():
            decision_counts[d.decision_type] += 1

        # Check terminal overrides like cancellations or manual escalations
        if decision_counts[DecisionType.CANCELLED] > 0:
            return ApprovalLifecycle.CANCELLED
        if decision_counts[DecisionType.ESCALATED] > 0:
            return ApprovalLifecycle.ESCALATED
        if decision_counts[DecisionType.EXPIRED] > 0:
            return ApprovalLifecycle.EXPIRED

        # 1. ANY_REVIEWER Policy
        if policy == ApprovalPolicy.ANY_REVIEWER:
            if decision_counts[DecisionType.APPROVED] > 0:
                return ApprovalLifecycle.APPROVED
            if decision_counts[DecisionType.REJECTED] > 0:
                return ApprovalLifecycle.REJECTED
            if decision_counts[DecisionType.CHANGES_REQUESTED] > 0:
                return ApprovalLifecycle.CHANGES_REQUESTED

        # 2. ALL_REVIEWERS / UNANIMOUS Policy
        elif policy in (ApprovalPolicy.ALL_REVIEWERS, ApprovalPolicy.UNANIMOUS):
            if decision_counts[DecisionType.REJECTED] > 0:
                return ApprovalLifecycle.REJECTED
            if decision_counts[DecisionType.CHANGES_REQUESTED] > 0:
                return ApprovalLifecycle.CHANGES_REQUESTED
            if len(latest_decisions) >= total_reviewers:
                if decision_counts[DecisionType.APPROVED] == total_reviewers:
                    return ApprovalLifecycle.APPROVED
                return ApprovalLifecycle.REJECTED

        # 3. MAJORITY Policy
        elif policy == ApprovalPolicy.MAJORITY:
            half = total_reviewers / 2
            if decision_counts[DecisionType.APPROVED] > half:
                return ApprovalLifecycle.APPROVED
            if decision_counts[DecisionType.REJECTED] > half:
                return ApprovalLifecycle.REJECTED
            if decision_counts[DecisionType.CHANGES_REQUESTED] > half:
                return ApprovalLifecycle.CHANGES_REQUESTED

            # If all responded and no clear majority is met
            if len(latest_decisions) >= total_reviewers:
                return ApprovalLifecycle.REJECTED

        # 4. FIRST_RESPONSE Policy
        elif policy == ApprovalPolicy.FIRST_RESPONSE:
            # Use chronological sorting to locate first response
            sorted_decisions = sorted(valid_decisions, key=lambda x: x.timestamp)
            if sorted_decisions:
                first = sorted_decisions[0].decision_type
                if first == DecisionType.APPROVED:
                    return ApprovalLifecycle.APPROVED
                if first == DecisionType.REJECTED:
                    return ApprovalLifecycle.REJECTED
                if first == DecisionType.CHANGES_REQUESTED:
                    return ApprovalLifecycle.CHANGES_REQUESTED

        return ApprovalLifecycle.IN_REVIEW


class ApprovalStatisticsCollector:
    """Collects aggregate telemetry and stats metadata."""

    def __init__(self) -> None:
        self.stats = ApprovalStatistics()

    def record_creation(self) -> None:
        self.stats.approvals_created += 1

    def record_resolution(self, status: ApprovalLifecycle) -> None:
        if status == ApprovalLifecycle.APPROVED:
            self.stats.approvals_completed += 1
        elif status == ApprovalLifecycle.REJECTED:
            self.stats.approvals_rejected += 1
        elif status == ApprovalLifecycle.ESCALATED:
            self.stats.escalations += 1
        elif status == ApprovalLifecycle.EXPIRED:
            self.stats.expired_requests += 1

    def update_averages(self, duration: float) -> None:
        total = self.stats.approvals_completed + self.stats.approvals_rejected
        if total <= 1:
            self.stats.average_approval_time = duration
        else:
            prev = self.stats.average_approval_time
            self.stats.average_approval_time = prev + (duration - prev) / total


class ApprovalEngine:
    """Workflow component coordinating approval sessions and outcomes."""

    def __init__(self) -> None:
        self.resolver = ReviewerResolver()
        self.evaluator = ApprovalPolicyEvaluator()
        self.stats_collector = ApprovalStatisticsCollector()
        self.sessions: dict[str, ApprovalSession] = {}
        self.decisions_registry: dict[str, list[ApprovalDecision]] = {}

    def create_session(
        self,
        approval_id: str,
        request: ApprovalRequest,
    ) -> ApprovalSession:
        """Create a new stateful approval session validation checks."""
        if approval_id in self.sessions:
            raise ValueError(f"Approval session '{approval_id}' already exists.")

        # Resolve reviewers
        resolved = self.resolver.resolve_reviewers(request.reviewers)
        request = request.model_copy(update={"reviewers": resolved})

        # Instantiate session
        session = ApprovalSession(
            approval_id=approval_id,
            request=request,
            status=ApprovalLifecycle.CREATED,
            history=[],
        )
        session.transition_to(ApprovalLifecycle.PENDING, reason="Session initialized")

        self.sessions[approval_id] = session
        self.decisions_registry[approval_id] = []
        self.stats_collector.record_creation()

        logger.info(
            EventID.LOG_INFO,
            f"Approval request '{approval_id}' created successfully.",
            component="ApprovalEngine",
        )
        return session

    def submit_decision(
        self,
        approval_id: str,
        decision: ApprovalDecision,
    ) -> ApprovalResponse:
        """Process reviewer decision, evaluate policy rules, and update session lifecycle."""
        session = self.sessions.get(approval_id)
        if not session:
            raise KeyError(f"Approval session '{approval_id}' not found.")

        # Check expiration status
        if time.time() > session.request.expires_at:
            session.transition_to(
                ApprovalLifecycle.EXPIRED, reason="TTL expiration limit hit"
            )
            self.stats_collector.record_resolution(ApprovalLifecycle.EXPIRED)
            return ApprovalResponse(
                approval_id=approval_id,
                status=session.status,
                decisions=self.decisions_registry[approval_id],
                resolved_at=time.time(),
            )

        if session.status in (
            ApprovalLifecycle.APPROVED,
            ApprovalLifecycle.REJECTED,
            ApprovalLifecycle.EXPIRED,
            ApprovalLifecycle.CANCELLED,
        ):
            raise PermissionError(
                "Cannot submit decisions to a resolved approval session."
            )

        # Record decision
        self.decisions_registry[approval_id].append(decision)

        # Transition to InReview on first response
        if session.status == ApprovalLifecycle.PENDING:
            session.transition_to(
                ApprovalLifecycle.IN_REVIEW, reason="First decision received"
            )

        # Evaluate consensus
        next_status = self.evaluator.evaluate(
            policy=session.request.policy,
            reviewers=session.request.reviewers,
            decisions=self.decisions_registry[approval_id],
        )

        resolved_time = None
        if next_status != session.status:
            session.transition_to(next_status, reason="Policy consensus evaluated")
            if next_status in (
                ApprovalLifecycle.APPROVED,
                ApprovalLifecycle.REJECTED,
                ApprovalLifecycle.EXPIRED,
                ApprovalLifecycle.CANCELLED,
            ):
                resolved_time = time.time()
                duration = resolved_time - session.request.created_at
                self.stats_collector.record_resolution(next_status)
                self.stats_collector.update_averages(duration)

                logger.info(
                    EventID.LOG_INFO,
                    f"Approval request '{approval_id}' resolved with outcome: {next_status.value}",
                    component="ApprovalEngine",
                )

        return ApprovalResponse(
            approval_id=approval_id,
            status=session.status,
            decisions=self.decisions_registry[approval_id],
            resolved_at=resolved_time,
        )


class ApprovalManager:
    """Manages multi-tenant approval engines and lifecycle metrics."""

    def __init__(self, engine: ApprovalEngine | None = None) -> None:
        self.engine = engine or ApprovalEngine()

    def get_metrics(self) -> ApprovalStatistics:
        """Retrieve aggregated stats collected by the manager."""
        return self.engine.stats_collector.stats
