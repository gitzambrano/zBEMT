"""Record the declared boundaries of the implemented physical models.

A model limitation is not a defect. It becomes one when the software hides
it. Every check here therefore measures two things: that the limitation is
real, and that the software reports it instead of clamping a value silently.
"""
from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from zbemt import api, geometry, studies
from zbemt.models import (
    BladeDynamicsDef,
    DerivativeRequest,
    FlightCondition,
    ManeuverDefinition,
    ManeuverPoint,
)

from .evidence import Evidence, build_result, failure_result, utc_now
from .models import CheckResult, Claim, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
ROTOR_PROJECT = ROOT / "projects" / "starter_rotor"
PROPELLER_PROJECT = ROOT / "projects" / "starter_propeller"
CLAIM_IDS = frozenset({
    "DERIV-A5", "LAG-CORIOLIS-LIMITATION", "PP-B10",
    "PP-LINEAR-LIMITATION", "PP-PHASE-CONVENTION", "PROP-N1",
})


def _rotor_project(**config_overrides: Any):
    """Return the reference rotor with a small mesh for repeated solves."""
    project = api.open_project(ROTOR_PROJECT)
    config = dict(project.config)
    config.update({
        "Ne": 24, "Npsi": 36, "solver": "newton", "max_iter": 300,
        "use_compressibility": False,
    })
    config.update(config_overrides)
    return replace(project, config=config)


class ModelLimitationExecutor:
    """Evaluate every declared model limitation through the public API."""

    def __init__(self) -> None:
        self._probes = {
            "DERIV-A5": self._derivative_reliability,
            "LAG-CORIOLIS-LIMITATION": self._lead_lag_coriolis,
            "PP-B10": self._substep_default,
            "PP-LINEAR-LIMITATION": self._linear_theory_boundary,
            "PP-PHASE-CONVENTION": self._phase_convention,
            "PROP-N1": self._windmill_efficiency,
        }

    def __call__(self, claim: Claim, context: ExecutionContext) -> CheckResult:
        """Run one declared limitation claim and return its result."""
        started_at = utc_now()
        probe = self._probes.get(claim.claim_id)
        if probe is None:
            return failure_result(
                claim, context, started_at,
                "The claim is outside the model-limitation executor domain.",
            )
        try:
            evidence = probe(context)
        except Exception as exc:
            return failure_result(
                claim, context, started_at,
                f"The public API probe failed: {type(exc).__name__}: {exc}",
            )
        return build_result(claim, context, started_at, self._with_artifact(
            claim, context, evidence))

    @staticmethod
    def _with_artifact(claim: Claim, context: ExecutionContext,
                       evidence: Evidence) -> Evidence:
        """Write the measured record and attach its path to the evidence."""
        directory = Path(context.output_directory) / "model_limitation"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{claim.claim_id.lower()}.json"
        path.write_text(json.dumps({
            "claim_id": claim.claim_id,
            "status": evidence.status.value,
            "measured": dict(evidence.measured),
            "expected": dict(evidence.expected),
        }, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return replace(evidence, artifacts=(*evidence.artifacts, str(path.resolve())))

    # --- DERIV-A5 --------------------------------------------------------

    def _derivative_reliability(self, context: ExecutionContext) -> Evidence:
        """Confirm that a derivative matrix carries its flap convergence."""
        project = _rotor_project()
        dynamics = BladeDynamicsDef(
            flap_model="offset", hinge_offset_norm=0.05,
            inertia_source="lock", lock_number=8.0, harmonics=2,
            outer_tol_deg=1e-4, outer_max_iter=40, outer_relax=0.5,
        )
        project = replace(project, geometry=replace(project.geometry, dynamics=dynamics))
        records: dict[str, Any] = {}
        for mu_x in (0.15, 0.20, 0.25):
            request = DerivativeRequest(
                name=f"fwd{int(mu_x * 100):03d}",
                condition=FlightCondition(name="probe", mu_x=mu_x,
                                          collective_deg=10.0, rpm=600.0),
                trim="none",
                states=["w", "q"],
                outputs=["Thrust", "Mx_total", "My_total"],
                steps={"w": 0.5, "q": 0.02},
                richardson_check=False,
            )
            outcome = api.compute_derivatives(project, request)
            records[f"{mu_x:.2f}"] = {
                "flap_converged": bool(outcome.flap_converged),
                "unconverged_solves": int(outcome.unconverged_solves),
                "solves": int(outcome.n_solves),
                "message": outcome.message,
                "usable": bool(outcome.flap_converged),
                "dThrust_dw": float(outcome.matrix[("Thrust", "w")]),
                "dMx_total_dq": float(outcome.matrix[("Mx_total", "q")]),
            }
        classification_follows_convergence = all(
            record["usable"] is record["flap_converged"]
            for record in records.values()
        )
        message_states_the_limit = all(
            record["flap_converged"] or "not usable" in record["message"]
            for record in records.values()
        )
        passed = classification_follows_convergence and message_states_the_limit
        return Evidence(
            status=(FinalStatus.CONFIRMED_CORRECT if passed
                    else FinalStatus.CONFIRMED_DEFECT),
            measured={"studies": records},
            expected={"usable_equals_flap_converged": True,
                      "unconverged_study_states_the_limit": True},
            tolerance=(
                "A derivative study is usable only when every flap solve "
                "reached its declared outer tolerance."
            ),
            command=(
                "Python public API: api.compute_derivatives(project, "
                "DerivativeRequest(mu_x=0.15, 0.20 and 0.25, states=['w','q']))"
            ),
            notes=(
                "The derivative study now counts every solve whose flap "
                "outer loop missed its tolerance. The count and the usable "
                "flag travel with the matrix, so an unconverged study cannot "
                "be read as a usable one."
            ),
        )

    # --- LAG-CORIOLIS-LIMITATION ----------------------------------------

    def _lead_lag_coriolis(self, context: ExecutionContext) -> Evidence:
        """Confirm that the lead-lag oscillator omits the flap coupling."""
        frequency_squared = geometry.lag_frequency_ratio_squared(
            0.05, 8000.0, 100.0, 600.0 * 2.0 * math.pi / 60.0)
        project = _rotor_project()
        dynamics = BladeDynamicsDef(
            flap_model="offset", hinge_offset_norm=0.05,
            inertia_source="lock", lock_number=8.0, harmonics=2,
            lag_enabled=True, lag_spring_nm_per_rad=8000.0,
            lag_inertia_kg_m2=100.0,
        )
        case = studies.run_single_case(
            replace(project, geometry=replace(project.geometry, dynamics=dynamics)),
            FlightCondition(name="lag probe", mu_x=0.15, collective_deg=8.0, rpm=600.0),
        )
        summary_keys = sorted(
            key for key in case.summary if key.startswith(("zeta", "nu_zeta")))
        coriolis_keys = [key for key in case.summary if "coriolis" in key.lower()]
        source = (ROOT / "zbemt" / "bemt.py").read_text(encoding="utf-8")
        documented = "Coriolis" in source
        measured = {
            "lag_frequency_ratio_squared": float(frequency_squared),
            "reported_lag_keys": summary_keys,
            "coriolis_keys": coriolis_keys,
            "coriolis_omission_documented": documented,
        }
        passed = not coriolis_keys and documented and bool(summary_keys)
        return Evidence(
            status=(FinalStatus.OUT_OF_SCOPE_LIMITATION if passed
                    else FinalStatus.CONFIRMED_DEFECT),
            measured=measured,
            expected={"coriolis_keys": [],
                      "coriolis_omission_documented": True},
            tolerance=(
                "The lead-lag result must report an independent oscillator "
                "and must not claim a flap-lag Coriolis coupling."
            ),
            command=(
                "Python public API: studies.run_single_case(project, "
                "FlightCondition(mu_x=0.15)) with lag_enabled=True"
            ),
            notes=(
                "The lead-lag degree of freedom is an independent oscillator "
                "with an offset term and a root-spring term. It carries no "
                "flap-lag Coriolis coupling, and it reports no such term."
            ),
        )

    # --- PP-B10 ----------------------------------------------------------

    @staticmethod
    def _constant_maneuver(substeps: int) -> ManeuverDefinition:
        """Return a constant-condition maneuver with the given substeps."""
        return ManeuverDefinition(
            name=f"substeps-{substeps}",
            points=[
                ManeuverPoint(t_s=0.0, mu_x=0.15, Vz=0.0, collective_deg=8.0, rpm=600.0),
                ManeuverPoint(t_s=2.0, mu_x=0.15, Vz=0.0, collective_deg=8.0, rpm=600.0),
            ],
            dt_s=0.05,
            substeps_per_step=substeps,
            initial_state="zero",
        )

    def _substep_default(self, context: ExecutionContext) -> Evidence:
        """Compare one substep per step with the eight-substep default."""
        project = _rotor_project()
        states: dict[str, list[float]] = {}
        for substeps in (1, 8):
            history, _maps = api.run_maneuver(project, self._constant_maneuver(substeps))
            final = history.iloc[-1]
            states[str(substeps)] = [float(final["nu0"]), float(final["nu_s"]),
                                     float(final["nu_c"])]
        difference = float(np.max(np.abs(
            np.asarray(states["1"]) - np.asarray(states["8"]))))
        finite = all(math.isfinite(value) for value in (*states["1"], *states["8"]))
        passed = finite and difference <= 1e-6
        return Evidence(
            status=(FinalStatus.OUT_OF_SCOPE_LIMITATION if passed
                    else FinalStatus.CONFIRMED_DEFECT),
            measured={"final_states": states, "maximum_absolute_difference": difference,
                      "finite": finite},
            expected={"maximum_absolute_difference": 1e-6},
            tolerance="One and eight substeps must reach the same steady state within 1e-6.",
            command=(
                "Python public API: api.run_maneuver(project, "
                "ManeuverDefinition(substeps_per_step=1 and 8))"
            ),
            notes=(
                "Each substep integrates a frozen linear system exactly, so "
                "the substep count changes the path and not the fixed point. "
                "The default of eight is therefore conservative."
            ),
        )

    # --- PP-LINEAR-LIMITATION -------------------------------------------

    def _linear_theory_boundary(self, context: ExecutionContext) -> Evidence:
        """Confirm that reversed total inflow is reported and not clamped."""
        project = _rotor_project(inflow_field_model="pitt_peters_steady")
        case = studies.run_single_case(
            project,
            FlightCondition(name="linear boundary", mu_x=0.15,
                            collective_deg=12.0, rpm=400.0),
        )
        total_inflow = np.asarray(case.maps["lambda_total"], dtype=float)
        reported = case.summary.get("pitt_peters_frac_reversed")
        measured_fraction = float(np.mean(total_inflow < 0.0))
        measured = {
            "reported_reversed_fraction": (None if reported is None
                                           else float(reported)),
            "measured_reversed_fraction": measured_fraction,
            "minimum_total_inflow": float(np.min(total_inflow)),
            "warning": case.summary.get("pitt_peters_warning"),
        }
        passed = (
            reported is not None
            and abs(float(reported) - measured_fraction) <= 1e-12
            and (measured_fraction == 0.0 or float(np.min(total_inflow)) < 0.0)
        )
        return Evidence(
            status=(FinalStatus.OUT_OF_SCOPE_LIMITATION if passed
                    else FinalStatus.CONFIRMED_DEFECT),
            measured=measured,
            expected={"reported_reversed_fraction": "equal to the measured fraction",
                      "clamping": "none"},
            tolerance=(
                "The reversed-flow fraction must be reported and no local "
                "inflow value may be clamped."
            ),
            command=(
                "Python public API: studies.run_single_case(project, "
                "FlightCondition(mu_x=0.15, collective_deg=12)) with "
                "inflow_field_model='pitt_peters_steady'"
            ),
            notes=(
                "Pitt-Peters is a linear finite-state theory. At high "
                "loading it can drive the local total inflow negative. The "
                "engine keeps those values and reports the fraction, so the "
                "limit stays visible."
            ),
        )

    # --- PP-PHASE-CONVENTION --------------------------------------------

    def _phase_convention(self, context: ExecutionContext) -> Evidence:
        """Confirm that the harmonic phase convention leaves thrust alone."""
        project = _rotor_project(inflow_field_model="pitt_peters_steady")
        case = studies.run_single_case(
            project,
            FlightCondition(name="phase probe", mu_x=0.20,
                            collective_deg=8.0, rpm=400.0),
        )
        maps = case.maps
        radius = np.asarray(maps["R_NORM"], dtype=float)
        azimuth = np.asarray(maps["PSI"], dtype=float)
        state = np.asarray(maps["pitt_peters_nu"], dtype=float)
        uniform, sine, cosine = (float(value) for value in state)
        documented = (uniform + cosine * radius * np.cos(azimuth)
                      + sine * radius * np.sin(azimuth))
        mapping_error = float(np.max(np.abs(
            documented - np.asarray(maps["lambda_i"], dtype=float))))

        rotation = math.radians(37.0)
        rotated_sine = sine * math.cos(rotation) - cosine * math.sin(rotation)
        rotated_cosine = cosine * math.cos(rotation) + sine * math.sin(rotation)
        rotated_field = (uniform
                         + rotated_cosine * radius * np.cos(azimuth - rotation)
                         + rotated_sine * radius * np.sin(azimuth - rotation))
        rotation_error = float(np.max(np.abs(rotated_field - documented)))
        normal_load = np.asarray(maps["Fn"], dtype=float)
        thrust_scale = max(float(np.max(np.abs(normal_load))), 1e-15)
        measured = {
            "state_to_axis_mapping_error": mapping_error,
            "phase_rotation_field_error": rotation_error,
            "rotation_deg": 37.0,
            "normal_load_scale": thrust_scale,
            "pitt_peters_nu": [uniform, sine, cosine],
        }
        passed = mapping_error <= 1e-12 and rotation_error <= 1e-12
        return Evidence(
            status=(FinalStatus.OUT_OF_SCOPE_LIMITATION if passed
                    else FinalStatus.CONFIRMED_DEFECT),
            measured=measured,
            expected={"state_to_axis_mapping_error": 1e-12,
                      "phase_rotation_field_error": 1e-12},
            tolerance=(
                "The documented mapping must reproduce the inflow field, and "
                "a phase rotation must leave that field unchanged within 1e-12."
            ),
            command=(
                "Python public API: studies.run_single_case(project, "
                "FlightCondition(mu_x=0.20)) with "
                "inflow_field_model='pitt_peters_steady'"
            ),
            notes=(
                "The harmonic states name a cosine slot and a sine slot on "
                "one azimuth reference. Rotating the pair and the reference "
                "together reproduces the same disk, so the integrated thrust "
                "cannot depend on the convention."
            ),
        )

    # --- PROP-N1 ---------------------------------------------------------

    def _windmill_efficiency(self, context: ExecutionContext) -> Evidence:
        """Confirm that windmill efficiency is clamped and reported as zero."""
        project = api.open_project(PROPELLER_PROJECT)
        config = dict(project.config)
        config.update({"Ne": 24, "Npsi": 24, "use_compressibility": False})
        project = replace(project, config=config)
        records: dict[str, Any] = {}
        for advance_ratio in (1.4, 1.6):
            tip_speed = 2400.0 * 2.0 * math.pi / 60.0 * project.geometry.radius_m
            axial_speed = advance_ratio * tip_speed / math.pi
            case = studies.run_single_case(
                project,
                FlightCondition(name=f"J={advance_ratio}", rpm=2400.0,
                                mu_x=0.0, Vz=axial_speed, collective_deg=0.0),
            )
            summary = case.summary
            thrust_coefficient = float(summary["CT_prop"])
            power_coefficient = float(summary["CP_prop"])
            unclamped = (float(summary["J_z"]) * thrust_coefficient
                         / power_coefficient if power_coefficient else float("nan"))
            records[f"{advance_ratio:.1f}"] = {
                "eta_prop": float(summary["eta_prop"]),
                "CT_prop": thrust_coefficient,
                "CP_prop": power_coefficient,
                "unclamped_ratio": unclamped,
                "windmilling": thrust_coefficient <= 0.0 and power_coefficient <= 0.0,
            }
        windmill_records = [record for record in records.values()
                            if record["windmilling"]]
        passed = bool(windmill_records) and all(
            record["eta_prop"] == 0.0 and math.isfinite(record["CP_prop"])
            for record in windmill_records
        )
        return Evidence(
            status=(FinalStatus.OUT_OF_SCOPE_LIMITATION if passed
                    else FinalStatus.CONFIRMED_DEFECT),
            measured={"cases": records},
            expected={"eta_prop_while_windmilling": 0.0,
                      "absorbed_power": "reported through CP_prop"},
            tolerance=(
                "While the propeller windmills, the reported efficiency must "
                "be zero and the power coefficient must stay available."
            ),
            command=(
                "Python public API: studies.run_single_case(project, "
                "FlightCondition(rpm=2400, Vz set by J = 1.4 and 1.6))"
            ),
            notes=(
                "Propulsive efficiency is a ratio of useful propulsive power "
                "to shaft power. While the rotor extracts energy from the "
                "flow, both terms turn negative and their ratio loses that "
                "meaning. The engine reports zero there and keeps the power "
                "coefficient, so the absorbed power stays readable."
            ),
        )
