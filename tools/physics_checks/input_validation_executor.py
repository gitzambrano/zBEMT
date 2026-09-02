"""Confirm that the public interface rejects an invalid fluid state.

PR-6 requires the software to stop before a solve when an input cannot carry
a physical meaning. This executor drives the public CLI, so it measures the
same refusal that a user meets.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from .cli_helper import run_cli_in_project_copy
from .evidence import Evidence, build_result, failure_result, status_of, utc_now
from .models import CheckResult, Claim, ExecutionContext


ROOT = Path(__file__).resolve().parents[2]
PROPELLER_PROJECT = ROOT / "projects" / "starter_propeller"
CLAIM_IDS = frozenset({"PROP-K8"})

#: The two non-positive densities the claim names.
DENSITIES = ("0", "-1")


def _probe_density(context: ExecutionContext, density: str) -> dict[str, Any]:
    """Run one validate-only case and one full case at the given density."""
    work_root = Path(context.output_directory) / "input_validation_cli"
    work_root.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {}
    for mode, extra in (("validate_only", ("--validate-only",)), ("full_run", ())):
        work = Path(tempfile.mkdtemp(prefix=f"rho{density}_{mode}_", dir=work_root))
        run = run_cli_in_project_copy(
            PROPELLER_PROJECT,
            (
                "--rpm", "2400", "--j-axial", "0.8", "--collective", "0",
                "--set", f"config.rho={density}", *extra,
            ),
            work,
        )
        output = run.stdout + run.stderr
        record[mode] = {
            "exit_code": run.exit_code,
            "reports_density_error": "rho (air density) must be" in output,
            "result_files": [str(path) for path in run.generated_csv_paths],
            "command": run.command,
        }
    return record


def execute_input_validation_claim(claim: Claim, context: ExecutionContext) -> CheckResult:
    """Run one input-validation claim and return its evidence record."""
    started_at = utc_now()
    if claim.claim_id not in CLAIM_IDS:
        return failure_result(
            claim, context, started_at,
            "The claim is outside the input-validation executor domain.",
        )
    try:
        measured = {density: _probe_density(context, density) for density in DENSITIES}
    except Exception as exc:
        return failure_result(
            claim, context, started_at,
            f"The public CLI probe failed: {type(exc).__name__}: {exc}",
        )

    passed = all(
        record[mode]["exit_code"] != 0
        and record[mode]["reports_density_error"]
        and not record[mode]["result_files"]
        for record in measured.values()
        for mode in ("validate_only", "full_run")
    )
    commands = [
        record[mode]["command"]
        for record in measured.values()
        for mode in ("validate_only", "full_run")
    ]
    return build_result(claim, context, started_at, Evidence(
        status=status_of(passed),
        measured=measured,
        expected={
            "exit_code": "nonzero",
            "reports_density_error": True,
            "result_files": [],
        },
        tolerance="Each non-positive density must fail validation and write no result file.",
        command="\n".join(dict.fromkeys(commands)),
        notes=(
            "The public CLI ran twice for each density: once with "
            "--validate-only and once as a full case. Both refused the solve "
            "and produced no result file."
        ),
    ))
