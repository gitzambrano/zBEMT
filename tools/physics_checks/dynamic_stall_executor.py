"""Confirm dynamic-stall claims through the public Python API."""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from zbemt import api
from zbemt.models import FlightCondition, Results

from .models import CheckResult, Claim, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = ROOT / "projects" / "starter_rotor"
CLAIM_IDS = frozenset({
    "DS-A1", "DS-A2", "DS-A3", "DS-A4", "DS-A5", "DS-A6", "DS-A7",
    "DS-A8", "DS-A9", "DS-A10", "DS-A11", "DS-A12", "DS-A13",
    "DS-A14", "DS-A15", "DS-A16", "DS-A17", "DS-A18",
    "DS-D3-HYSTERESIS-DIRECTION", "DS-D3B-FADE-50", "DS-H4",
})


@dataclass(frozen=True)
class _Case:
    result: Results
    command: str
    artifact: str


@dataclass(frozen=True)
class _Evaluation:
    status: FinalStatus
    measured: Mapping[str, Any]
    expected: Mapping[str, Any]
    tolerance: str
    notes: str
    cases: tuple[_Case, ...] = ()


def _utc_now() -> str:
    """Return the current UTC time."""
    return datetime.now(timezone.utc).isoformat()


def _relative_change(value: float, reference: float) -> float:
    """Return an absolute relative change."""
    return abs(value - reference) / max(abs(reference), 1e-15)


class DynamicStallExecutor:
    """Evaluate each dynamic-stall claim that has a reproducible public route."""

    def __init__(self, source_project: Path = DEFAULT_PROJECT) -> None:
        self._source_project = Path(source_project)
        self._project = api.open_project(str(self._source_project))
        self._cache: dict[tuple[Any, ...], _Case] = {}
        self._evaluators = {
            "DS-A1": self._steady_state,
            "DS-A7": self._hover_invariance,
            "DS-A8": self._method_agreement,
            "DS-A14": self._fade_55,
            "DS-A15": self._time_constant_ordering,
            "DS-A16": self._integrated_load_magnitude,
            "DS-D3B-FADE-50": self._fade_50,
        }

    def __call__(self, claim: Claim, context: ExecutionContext) -> CheckResult:
        """Run one declared claim and return its evidence record."""
        started_at = _utc_now()
        if claim.claim_id not in CLAIM_IDS:
            return self._inconclusive(
                claim, context, started_at,
                "The claim is outside the dynamic-stall executor domain.",
            )
        try:
            evaluator = self._evaluators.get(claim.claim_id)
            if evaluator is None:
                return self._missing_fixture(claim, context, started_at)
            evaluation = evaluator(context)
            return CheckResult(
                claim_id=claim.claim_id,
                final_status=evaluation.status,
                measured_data=evaluation.measured,
                expected_data=evaluation.expected,
                tolerance_rule=evaluation.tolerance,
                command="\n".join(dict.fromkeys(case.command for case in evaluation.cases)),
                artifacts=tuple(dict.fromkeys(case.artifact for case in evaluation.cases)),
                notes=evaluation.notes,
                started_at=started_at,
                ended_at=_utc_now(),
                commit=context.commit,
                environment=context.environment,
            )
        except Exception as exc:
            return self._inconclusive(
                claim, context, started_at,
                f"The public API execution failed: {type(exc).__name__}: {exc}",
            )

    def _inconclusive(
        self,
        claim: Claim,
        context: ExecutionContext,
        started_at: str,
        notes: str,
    ) -> CheckResult:
        return CheckResult(
            claim_id=claim.claim_id,
            final_status=FinalStatus.INCONCLUSIVE,
            measured_data={"reason": notes},
            expected_data={"acceptance_rule": claim.acceptance_rule},
            tolerance_rule=claim.acceptance_rule,
            command=claim.cli_route,
            artifacts=(),
            notes=notes,
            started_at=started_at,
            ended_at=_utc_now(),
            commit=context.commit,
            environment=context.environment,
        )

    def _missing_fixture(
        self,
        claim: Claim,
        context: ExecutionContext,
        started_at: str,
    ) -> CheckResult:
        return self._inconclusive(
            claim,
            context,
            started_at,
            "The source fixture does not specify the numerical polar, trajectory, "
            "and element probe needed to apply this acceptance rule. The executor "
            "did not substitute a different physical case.",
        )

    def _case(
        self,
        context: ExecutionContext,
        *,
        dynamic: bool,
        method: str = "frequency",
        mu_x: float = 0.0,
        collective_deg: float = 16.0,
        lag_constant: float = 8.0,
        revolutions: int = 16,
        fade_start_deg: float = 40.0,
        fade_end_deg: float = 50.0,
    ) -> _Case:
        key = (
            str(Path(context.output_directory).resolve()), dynamic, method, mu_x,
            collective_deg, lag_constant, revolutions, fade_start_deg, fade_end_deg,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        project = copy.deepcopy(self._project)
        project.config.update({
            "Ne": 16,
            "Npsi": 36,
            "solver": "newton",
            "max_iter": 200,
            "prandtl_loss_mode": "off",
            "use_compressibility": False,
        })
        project.airfoil.use_dynamic_stall = dynamic
        project.airfoil.dynamic_stall_method = method
        project.airfoil.dynamic_stall_A = lag_constant
        project.airfoil.dynamic_stall_time_march_revolutions = revolutions
        project.airfoil.dynamic_stall_time_march_avg_last = min(2, revolutions)
        project.airfoil.dynamic_stall_fade_start_deg = fade_start_deg
        project.airfoil.dynamic_stall_fade_end_deg = fade_end_deg
        condition = FlightCondition(
            name="dynamic-stall-check",
            rpm=400.0,
            mu_x=mu_x,
            Vz=0.0,
            collective_deg=collective_deg,
        )
        result = api.run_case(project, condition)
        command = (
            "Python public API: api.open_project('projects/starter_rotor'); "
            f"api.run_case(project, FlightCondition(rpm=400, mu_x={mu_x:g}, "
            f"collective_deg={collective_deg:g})); dynamic_stall={dynamic}, "
            f"method={method}, A={lag_constant:g}, revolutions={revolutions}, "
            f"fade={fade_start_deg:g} to {fade_end_deg:g} deg"
        )
        artifact_path = self._write_case_artifact(context, key[1:], result)
        case = _Case(result, command, str(artifact_path.resolve()))
        self._cache[key] = case
        return case

    def _write_case_artifact(
        self,
        context: ExecutionContext,
        key: tuple[Any, ...],
        result: Results,
    ) -> Path:
        output = Path(context.output_directory) / "dynamic_stall_api_work"
        output.mkdir(parents=True, exist_ok=True)
        label = "_".join(str(value).lower().replace(".", "p") for value in key)
        path = output / f"case_{label}.json"
        maps = result.maps
        payload = {
            "summary": {
                name: float(value) if isinstance(value, (int, float, np.number)) else value
                for name, value in result.summary.items()
                if name in {"CT", "CP", "CQ", "Thrust", "Power", "dynamic_stall_periodic_residual"}
            },
            "maps": {
                "maximum_abs_alpha_deg": float(np.max(np.abs(np.degrees(maps["alpha_eff"])))),
                "maximum_abs_Cl_change": float(np.max(np.abs(
                    np.asarray(maps.get("Cl", 0.0)) - np.asarray(maps.get("Cl_static", maps.get("Cl", 0.0)))
                ))),
                "maximum_abs_Cd_change": float(np.max(np.abs(
                    np.asarray(maps.get("Cd", 0.0)) - np.asarray(maps.get("Cd_static", maps.get("Cd", 0.0)))
                ))),
                "dynamic_stall_warning": maps.get("dynamic_stall_warning"),
            },
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @staticmethod
    def _evaluation(
        passed: bool,
        measured: Mapping[str, Any],
        expected: Mapping[str, Any],
        tolerance: str,
        notes: str,
        cases: tuple[_Case, ...],
    ) -> _Evaluation:
        status = FinalStatus.CONFIRMED_CORRECT if passed else FinalStatus.CONFIRMED_DEFECT
        return _Evaluation(status, measured, expected, tolerance, notes, cases)

    def _steady_state(self, context: ExecutionContext) -> _Evaluation:
        cases = (
            self._case(context, dynamic=True, method="frequency", mu_x=0.0),
            self._case(context, dynamic=True, method="time_march", mu_x=0.0),
        )
        errors = [float(np.max(np.abs(
            np.asarray(case.result.maps["f_oye"]) - np.asarray(case.result.maps["f_st_oye"])
        ))) for case in cases]
        maximum = max(errors)
        return self._evaluation(
            maximum <= 1e-12,
            {"methods": ["frequency", "time_march"], "maximum_errors": errors,
             "maximum_absolute_error": maximum},
            {"maximum_absolute_error": 1e-12},
            "max(abs(f_dynamic - f_static)) <= 1e-12 in steady hover",
            "A steady separation state is the fixed point of both implementations.",
            cases,
        )

    def _hover_invariance(self, context: ExecutionContext) -> _Evaluation:
        static = self._case(context, dynamic=False, mu_x=0.0)
        frequency = self._case(context, dynamic=True, method="frequency", mu_x=0.0)
        march = self._case(context, dynamic=True, method="time_march", mu_x=0.0)
        reference = float(static.result.summary["CT"])
        changes = [abs(float(case.result.summary["CT"]) - reference)
                   for case in (frequency, march)]
        maximum = max(changes)
        return self._evaluation(
            maximum <= 1e-12,
            {"CT_static": reference, "CT_frequency": float(frequency.result.summary["CT"]),
             "CT_time_march": float(march.result.summary["CT"]),
             "maximum_absolute_CT_change": maximum},
            {"maximum_absolute_CT_change": 1e-12},
            "max(abs(CT_dynamic - CT_static)) <= 1e-12",
            "Hover has no azimuthal incidence cycle. Therefore, separation lag cannot change CT.",
            (static, frequency, march),
        )

    def _method_agreement(self, context: ExecutionContext) -> _Evaluation:
        advance_ratios = (0.02, 0.05, 0.20)
        cases: list[_Case] = []
        differences = []
        for mu_x in advance_ratios:
            frequency = self._case(context, dynamic=True, method="frequency", mu_x=mu_x)
            march = self._case(context, dynamic=True, method="time_march", mu_x=mu_x)
            cases.extend((frequency, march))
            differences.append(_relative_change(
                float(march.result.summary["CT"]), float(frequency.result.summary["CT"])
            ))
        low_advance_maximum = max(differences[:2])
        finite = all(np.isfinite(value) for value in differences)
        passed = (
            finite
            and low_advance_maximum < 0.01
            and differences[-1] > differences[1]
        )
        return self._evaluation(
            passed,
            {"mu_x": list(advance_ratios), "relative_CT_differences": differences,
             "low_advance_maximum": low_advance_maximum},
            {"low_advance_maximum": 0.01,
             "forward_difference_greater_than_near_hover": True},
            "differences below 1% at mu_x 0.02 and 0.05; finite at 0.20; difference at 0.20 greater than at 0.05",
            "The frequency approximation is expected to separate from the time march when higher harmonics become important.",
            tuple(cases),
        )

    def _fade(self, context: ExecutionContext, boundary: float) -> _Evaluation:
        case = self._case(
            context, dynamic=True, method="time_march", mu_x=0.60,
            fade_start_deg=40.0, fade_end_deg=boundary,
        )
        maps = case.result.maps
        outside = np.abs(np.degrees(np.asarray(maps["alpha_eff"]))) >= boundary
        sample_count = int(np.count_nonzero(outside))
        if sample_count == 0:
            return _Evaluation(
                FinalStatus.INCONCLUSIVE,
                {"outside_sample_count": 0},
                {"outside_sample_count_minimum": 1},
                f"At least one element must lie outside plus or minus {boundary:g} degrees.",
                "The public case did not reach the declared fade boundary.",
                (case,),
            )
        lift_error = float(np.max(np.abs(
            np.asarray(maps["Cl"])[outside] - np.asarray(maps["Cl_static"])[outside]
        )))
        drag_error = float(np.max(np.abs(
            np.asarray(maps["Cd"])[outside] - np.asarray(maps["Cd_static"])[outside]
        )))
        maximum = max(lift_error, drag_error)
        return self._evaluation(
            maximum <= 1e-12,
            {"boundary_deg": boundary, "outside_sample_count": sample_count,
             "maximum_lift_error": lift_error, "maximum_drag_error": drag_error,
             "maximum_absolute_error": maximum},
            {"maximum_absolute_error": 1e-12},
            f"max coefficient error outside plus or minus {boundary:g} degrees <= 1e-12",
            "The declared fade boundary must return both coefficients to the static polar.",
            (case,),
        )

    def _fade_55(self, context: ExecutionContext) -> _Evaluation:
        return self._fade(context, 55.0)

    def _fade_50(self, context: ExecutionContext) -> _Evaluation:
        return self._fade(context, 50.0)

    def _time_constant_ordering(self, context: ExecutionContext) -> _Evaluation:
        lag_constants = (2.0, 8.0, 20.0)
        cases = tuple(self._case(
            context, dynamic=True, method="time_march", mu_x=0.20,
            lag_constant=value,
        ) for value in lag_constants)
        rms_lags = []
        for case in cases:
            maps = case.result.maps
            delta = np.asarray(maps["f_oye"]) - np.asarray(maps["f_st_oye"])
            rms_lags.append(float(math.sqrt(float(np.mean(delta**2)))))
        passed = all(right > left for left, right in zip(rms_lags, rms_lags[1:]))
        return self._evaluation(
            passed,
            {"A": list(lag_constants), "rms_separation_lag": rms_lags},
            {"trend": "strictly increasing"},
            "RMS separation lag(A=2) < lag(A=8) < lag(A=20)",
            "A larger time constant must increase the separation-state lag for the same cycle.",
            cases,
        )

    def _integrated_load_magnitude(self, context: ExecutionContext) -> _Evaluation:
        static = self._case(context, dynamic=False, mu_x=0.20)
        frequency = self._case(context, dynamic=True, method="frequency", mu_x=0.20)
        march = self._case(context, dynamic=True, method="time_march", mu_x=0.20)
        values = {}
        changes = []
        for method, case in (("frequency", frequency), ("time_march", march)):
            thrust_change = _relative_change(
                float(case.result.summary["CT"]), float(static.result.summary["CT"])
            )
            power_change = _relative_change(
                float(case.result.summary["CP"]), float(static.result.summary["CP"])
            )
            values[method] = {"relative_CT_change": thrust_change,
                              "relative_CP_change": power_change}
            changes.extend((thrust_change, power_change))
        passed = all(0.0 <= value <= 0.05 for value in changes)
        return self._evaluation(
            passed,
            {"mu_x": 0.20, "methods": values},
            {"relative_change_range": [0.0, 0.05]},
            "Each relative CT and CP change at mu_x=0.20 must lie from 0 to 0.05.",
            "The rule bounds the integrated effect of separation lag at the source condition.",
            (static, frequency, march),
        )
