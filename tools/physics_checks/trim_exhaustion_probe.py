"""Probe the bisection-trim reporting contract after iteration exhaustion."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zbemt import api  # noqa: E402
from zbemt.models import FlightCondition  # noqa: E402


DEFAULT_PROJECT = ROOT / "projects" / "starter_rotor"
DEFAULT_TARGET_THRUST_N = 400.0
DEFAULT_MAX_ITER = 1


def run_probe(
    project_path: Path = DEFAULT_PROJECT,
    target_thrust_n: float = DEFAULT_TARGET_THRUST_N,
    max_iter: int = DEFAULT_MAX_ITER,
) -> dict[str, object]:
    """Run one deliberately iteration-limited trim and return its record."""
    project = api.open_project(str(project_path))
    condition = FlightCondition(
        name="Trim exhaustion probe",
        mu_x=0.0,
        collective_deg=8.0,
        rpm=400.0,
    )
    result = api.run_case_trimmed(
        project,
        condition,
        trim_mode="solve_collective",
        target_kind="thrust",
        target_value=target_thrust_n,
        bracket=(-10.0, 30.0),
        max_iter=max_iter,
    )
    summary = result.summary
    return {
        "target_thrust_n": target_thrust_n,
        "max_iter": max_iter,
        "measured_thrust_n": summary.get("Thrust"),
        "trim_target": summary.get("trim_target"),
        "trim_dof": summary.get("trim_dof"),
        "trim_residual": summary.get("trim_residual"),
        "trim_converged": summary.get("trim_converged"),
        "report_fields_present": all(
            key in summary
            for key in ("trim_target", "trim_dof", "trim_residual", "trim_converged")
        ),
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe trim reporting after a deliberately short bisection."
    )
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--target-thrust", type=float, default=DEFAULT_TARGET_THRUST_N)
    parser.add_argument("--max-iter", type=int, default=DEFAULT_MAX_ITER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the probe, print structured evidence, and return its status."""
    args = _parse_args(argv)
    if args.max_iter < 1:
        print("--max-iter must be at least 1.", file=sys.stderr)
        return 2
    evidence = run_probe(args.project, args.target_thrust, args.max_iter)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
