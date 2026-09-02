"""Confirm that a marched result reports what EN-9 requires.

A time-marched result is only readable when the report states the interval it
covered, how finely it was integrated, and how far the state still moved at
the end. These checks run a prescribed maneuver through the public API and
read those fields back from the history and from the maps.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from zbemt import api
from zbemt.models import ManeuverDefinition, ManeuverPoint

from .evidence import Evidence, build_result, failure_result, status_of, utc_now
from .models import CheckResult, Claim, ExecutionContext


ROOT = Path(__file__).resolve().parents[2]
ROTOR_PROJECT = ROOT / "projects" / "starter_rotor"
CLAIM_IDS = frozenset({"DS-MANEUVER-REPORTING", "PP-B9"})

#: The azimuth resolution and revolution count the claim names.
AZIMUTH_STEPS = 72
REVOLUTIONS = 4


def _marched_project():
    """Return the reference rotor prepared for a marched dynamic-stall run."""
    project = api.open_project(ROTOR_PROJECT)
    config = dict(project.config)
    config.update({
        "Ne": 16, "Npsi": AZIMUTH_STEPS, "solver": "newton", "max_iter": 300,
        "use_compressibility": False, "prandtl_loss_mode": "off",
    })
    airfoil = replace(
        project.airfoil,
        use_dynamic_stall=True,
        dynamic_stall_method="time_march",
        dynamic_stall_time_march_revolutions=REVOLUTIONS,
        dynamic_stall_time_march_avg_last=2,
    )
    return replace(project, config=config, airfoil=airfoil)


def _maneuver() -> ManeuverDefinition:
    """Return the prescribed maneuver both reporting claims use."""
    return ManeuverDefinition(
        name="ds-reporting",
        points=[
            ManeuverPoint(t_s=0.0, mu_x=0.20, Vz=0.0, collective_deg=12.0, rpm=400.0),
            ManeuverPoint(t_s=0.30, mu_x=0.20, Vz=0.0, collective_deg=16.0, rpm=400.0),
        ],
        dt_s=0.05,
        substeps_per_step=8,
        initial_state="equilibrium",
        march_dynamic_stall=True,
    )


def _run(context: ExecutionContext) -> tuple[Any, list[dict], str]:
    """Run the prescribed maneuver once and write its evidence artifact."""
    history, maps_list = api.run_maneuver(_marched_project(), _maneuver())
    directory = Path(context.output_directory) / "reporting"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "maneuver_history.json"
    path.write_text(json.dumps({
        "columns": list(history.columns),
        "rows": int(len(history)),
        "marched_interval_s": [float(value) for value in history["marched_interval_s"]],
        "substeps": [int(value) for value in history["substeps"]],
    }, indent=2, sort_keys=True), encoding="utf-8")
    return history, maps_list, str(path.resolve())


class ReportingExecutor:
    """Evaluate the reporting claims of a marched result."""

    def __init__(self) -> None:
        self._probes = {
            "DS-MANEUVER-REPORTING": self._history_dimensions,
            "PP-B9": self._time_march_fields,
        }

    def __call__(self, claim: Claim, context: ExecutionContext) -> CheckResult:
        """Run one reporting claim and return its evidence record."""
        started_at = utc_now()
        probe = self._probes.get(claim.claim_id)
        if probe is None:
            return failure_result(
                claim, context, started_at,
                "The claim is outside the reporting executor domain.",
            )
        try:
            evidence = probe(context)
        except Exception as exc:
            return failure_result(
                claim, context, started_at,
                f"The public API probe failed: {type(exc).__name__}: {exc}",
            )
        return build_result(claim, context, started_at, evidence)

    def _history_dimensions(self, context: ExecutionContext) -> Evidence:
        """Confirm the separation history shape and the per-sample residual."""
        history, maps_list, artifact = _run(context)
        shapes = [np.asarray(maps["dynamic_stall_time_march_history"]).shape
                  for maps in maps_list]
        residuals = [float(maps["dynamic_stall_periodic_residual"])
                     for maps in maps_list]
        radial_stations = int(shapes[0][1]) if shapes else 0
        measured = {
            "sample_count": int(len(history)),
            "history_shape": [int(value) for value in shapes[0]] if shapes else [],
            "history_dimension_names": ["revolution", "radius", "azimuth"],
            "marched_steps": int(shapes[0][0] * shapes[0][2]) if shapes else 0,
            "every_sample_reports_residual": all(
                np.isfinite(value) for value in residuals),
            "distinct_shapes": len({shape for shape in shapes}),
            "residuals": residuals,
        }
        passed = (
            bool(shapes)
            and len(shapes[0]) == 3
            and int(shapes[0][0]) == REVOLUTIONS
            and int(shapes[0][2]) == AZIMUTH_STEPS
            and radial_stations > 0
            and measured["marched_steps"] == REVOLUTIONS * AZIMUTH_STEPS
            and measured["every_sample_reports_residual"]
            and measured["distinct_shapes"] == 1
        )
        return Evidence(
            status=status_of(passed),
            measured=measured,
            expected={
                "history_dimensions": 3,
                "revolutions": REVOLUTIONS,
                "azimuth_steps": AZIMUTH_STEPS,
                "marched_steps": REVOLUTIONS * AZIMUTH_STEPS,
                "every_sample_reports_residual": True,
            },
            tolerance=(
                "The separation history must carry a revolution, a radius, "
                "and an azimuth axis, and every sample must report its "
                "periodic residual."
            ),
            command=(
                "Python public API: api.run_maneuver(project, "
                "ManeuverDefinition(march_dynamic_stall=True)) with "
                f"Npsi={AZIMUTH_STEPS} and {REVOLUTIONS} marched revolutions"
            ),
            notes=(
                "The marched separation state is stored for every revolution "
                "on the full radial and azimuthal mesh. The periodic residual "
                "of each sample comes from the last two marched revolutions."
            ),
            artifacts=(artifact,),
        )

    def _time_march_fields(self, context: ExecutionContext) -> Evidence:
        """Confirm the interval, the substep count, and the residual."""
        history, maps_list, artifact = _run(context)
        columns = set(history.columns)
        required = ("marched_interval_s", "substeps",
                    "dynamic_stall_periodic_residual")
        present = {name: name in columns for name in required}
        intervals = [float(value) for value in history["marched_interval_s"]]
        substeps = [int(value) for value in history["substeps"]]
        residuals = [float(value) for value in
                     history.get("dynamic_stall_periodic_residual", [])]
        unsettled = [
            index for index, value in enumerate(residuals) if value > 1e-3]
        warnings_present = [
            bool(maps_list[index].get("dynamic_stall_warning"))
            for index in unsettled
        ]
        measured = {
            "required_fields_present": present,
            "marched_interval_s": intervals,
            "substeps": substeps,
            "periodic_residual": residuals,
            "unsettled_samples": unsettled,
            "unsettled_samples_carry_a_warning": all(warnings_present),
            "first_sample_interval_is_zero": bool(intervals and intervals[0] == 0.0),
            "later_samples_have_substeps": all(
                value > 0 for value in substeps[1:]),
        }
        passed = (
            all(present.values())
            and len(residuals) == len(history)
            and all(warnings_present)
            and measured["first_sample_interval_is_zero"]
            and measured["later_samples_have_substeps"]
        )
        return Evidence(
            status=status_of(passed),
            measured=measured,
            expected={
                "required_fields_present": {name: True for name in required},
                "unsettled_samples_carry_a_warning": True,
            },
            tolerance=(
                "Every marched sample must carry its interval, its substep "
                "count, and its periodic residual. An unsettled state must "
                "carry a warning."
            ),
            command=(
                "Python public API: api.run_maneuver(project, "
                "ManeuverDefinition(substeps_per_step=8, "
                "march_dynamic_stall=True))"
            ),
            notes=(
                "The first sample marches no interval, so its interval is "
                "zero and it uses no substep. Every later sample records the "
                "interval it covered and the substeps it used."
            ),
            artifacts=(artifact,),
        )
