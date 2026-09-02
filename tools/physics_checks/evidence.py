"""Build complete claim results from one measured evidence record.

Every executor must return a `CheckResult` with the same fields. This module
holds the small record that a probe produces and the single function that
turns it into a result. It keeps each new executor free of result plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .models import CheckResult, Claim, ExecutionContext, FinalStatus


def utc_now() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Evidence:
    """Hold the measured evidence of one claim probe."""

    status: FinalStatus
    measured: Mapping[str, Any]
    expected: Mapping[str, Any]
    tolerance: str
    command: str
    notes: str
    artifacts: tuple[str, ...] = field(default=())


def status_of(passed: bool) -> FinalStatus:
    """Return the confirmed status that matches one acceptance decision."""
    return FinalStatus.CONFIRMED_CORRECT if passed else FinalStatus.CONFIRMED_DEFECT


def build_result(
    claim: Claim,
    context: ExecutionContext,
    started_at: str,
    evidence: Evidence,
) -> CheckResult:
    """Return the complete result record of one executed claim."""
    return CheckResult(
        claim_id=claim.claim_id,
        final_status=evidence.status,
        measured_data=evidence.measured,
        expected_data=evidence.expected,
        tolerance_rule=evidence.tolerance,
        command=evidence.command,
        artifacts=evidence.artifacts,
        notes=evidence.notes,
        started_at=started_at,
        ended_at=utc_now(),
        commit=context.commit,
        environment=context.environment,
    )


def failure_result(
    claim: Claim,
    context: ExecutionContext,
    started_at: str,
    notes: str,
) -> CheckResult:
    """Return an inconclusive result for a probe that could not complete."""
    return CheckResult(
        claim_id=claim.claim_id,
        final_status=FinalStatus.INCONCLUSIVE,
        measured_data={"error": notes},
        expected_data={"acceptance_rule": claim.acceptance_rule},
        tolerance_rule=claim.acceptance_rule,
        command=claim.cli_route,
        artifacts=(),
        notes=notes,
        started_at=started_at,
        ended_at=utc_now(),
        commit=context.commit,
        environment=context.environment,
    )
