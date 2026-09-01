"""Execute selected physics claims and write structured result files."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .models import CampaignOutcome, CheckResult, Claim, ExecutionContext, FinalStatus
from .registry import ExecutorRegistry


def _now() -> str:
    """Return one UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _inconclusive_result(
    claim: Claim,
    context: ExecutionContext,
    started_at: str,
    notes: str,
) -> CheckResult:
    """Build a complete result for an unavailable or failed executor."""
    return CheckResult(
        claim_id=claim.claim_id,
        final_status=FinalStatus.INCONCLUSIVE,
        measured_data={},
        expected_data={},
        tolerance_rule=claim.acceptance_rule,
        command=claim.cli_route,
        artifacts=(),
        notes=notes,
        started_at=started_at,
        ended_at=_now(),
        commit=context.commit,
        environment=context.environment,
    )


def _write_outputs(
    output_directory: Path,
    claims: list[Claim],
    results: list[CheckResult],
    execution_failures: int,
    commit: str,
    environment: Mapping[str, str],
) -> None:
    """Write the JSON ledger result and the readable summary."""
    output_directory.mkdir(parents=True, exist_ok=True)
    status_counts = Counter(result.final_status.value for result in results)
    payload = {
        "commit": commit,
        "environment": dict(environment),
        "execution_failures": execution_failures,
        "status_counts": dict(sorted(status_counts.items())),
        "claims": [claim.to_dict() for claim in claims],
        "results": [result.to_dict() for result in results],
    }
    (output_directory / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "Physics check summary",
        f"Commit: {commit}",
        f"Selected claims: {len(claims)}",
        f"Execution failures: {execution_failures}",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"{status}: {count}")
    lines.append("")
    for claim, result in zip(claims, results):
        lines.append(f"{claim.claim_id} [{result.final_status.value}] {claim.title}")
        if result.notes:
            lines.append(f"  Notes: {result.notes}")
    (output_directory / "summary.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def run_campaign(
    claims: list[Claim],
    registry: ExecutorRegistry,
    output_directory: Path,
    *,
    fail_on_defect: bool = False,
    commit: str,
    environment: Mapping[str, str],
) -> CampaignOutcome:
    """Run every selected claim and return the aggregate status."""
    ordered_claims = sorted(claims, key=lambda item: item.claim_id)
    context = ExecutionContext(
        output_directory=Path(output_directory),
        commit=commit,
        environment=environment,
    )
    results: list[CheckResult] = []
    execution_failures = 0

    for claim in ordered_claims:
        started_at = _now()
        executor = registry.get(claim.executor_name)
        if executor is None:
            results.append(_inconclusive_result(
                claim,
                context,
                started_at,
                f"Executor '{claim.executor_name}' is not implemented.",
            ))
            continue

        try:
            result = executor(claim, context)
            if not isinstance(result, CheckResult):
                raise TypeError("The executor did not return a CheckResult.")
            if result.claim_id != claim.claim_id:
                raise ValueError(
                    f"Executor returned claim {result.claim_id} for {claim.claim_id}."
                )
            if not isinstance(result.final_status, FinalStatus):
                raise ValueError(
                    f"Executor returned invalid final status: {result.final_status!r}."
                )
            results.append(result)
        except Exception as exc:  # The campaign must preserve later claim executions.
            execution_failures += 1
            results.append(_inconclusive_result(
                claim,
                context,
                started_at,
                f"Executor failure: {type(exc).__name__}: {exc}",
            ))

    _write_outputs(
        Path(output_directory),
        ordered_claims,
        results,
        execution_failures,
        commit,
        environment,
    )
    has_defect = any(
        result.final_status is FinalStatus.CONFIRMED_DEFECT for result in results
    )
    exit_code = 1 if execution_failures or (fail_on_defect and has_defect) else 0
    return CampaignOutcome(tuple(results), execution_failures, exit_code)
