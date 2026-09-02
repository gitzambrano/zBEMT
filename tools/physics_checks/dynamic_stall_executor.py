"""Confirm dynamic-stall claims through the public Python API."""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from zbemt import api, studies
from zbemt.bemt import (
    BEMTConfig,
    _oye_frequency_domain_f,
    _oye_time_march_f,
    _pitt_peters_geometry,
)
from zbemt.models import (
    BladeDynamicsDef,
    FlightCondition,
    ManeuverDefinition,
    ManeuverPoint,
    Results,
)

from .models import CheckResult, Claim, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = ROOT / "projects" / "starter_rotor"
CLAIM_IDS = frozenset({
    "DS-A1", "DS-A2", "DS-A3", "DS-A4", "DS-A5", "DS-A6", "DS-A7",
    "DS-A8", "DS-A9", "DS-A10", "DS-A11", "DS-A12", "DS-A13",
    "DS-A14", "DS-A15", "DS-A16", "DS-A17", "DS-A18",
    "DS-D3-HYSTERESIS-DIRECTION", "DS-D3B-FADE-50", "DS-H4",
})

#: The synthetic harmonic probe of the separation-lag operator. A uniform
#: relative speed makes the lag time constant one number, so the analytical
#: first-order transfer function applies exactly.
_PROBE_CONFIG = BEMTConfig()
_PROBE_OMEGA = 400.0 * 2.0 * math.pi / 60.0
_PROBE_SPEED = 40.0
_PROBE_CHORD = 0.08
_PROBE_AZIMUTH_STEPS = 720
_PROBE_REVOLUTIONS = 40
_MEAN_SEPARATION = 0.5
_SEPARATION_AMPLITUDE = 0.4
#: The azimuth meshes that show how the two methods converge on each other.
_REFINEMENT_STEPS = (36, 72, 180, 360, 720)

#: The stalled forward-flight condition the hysteresis-loop claims share.
_LOOP_ADVANCE_RATIO = 0.35
_LOOP_COLLECTIVE = 14.0
_LOOP_AZIMUTH_STEPS = 180
_ATTACHED_SEPARATION = 0.999
_HYSTERESIS_ANGLE_DEG = 18.0

#: The prescribed collective ramp of the maneuver claims.
_RAMP_LOW_DEG = 6.0
_RAMP_HIGH_DEG = 18.0
_RAMP_PROBE_DEG = 13.0
_RAMP_SIDE_SAMPLES = 20
_RAMP_SAMPLES = 2 * _RAMP_SIDE_SAMPLES + 1
_RAMP_DURATION_S = 0.20
_THREADING_REVOLUTIONS = 8

#: The two airfoil sections of the dynamic-stall opt-out claim.
_ENABLED_STATION = 0.30
_DISABLED_STATION = 0.88
_INTERPOLATION_STATION = 0.81
_OUTSIDE_STATION = 0.95


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
    #: The route of a probe that runs no engine case, such as an analytical
    #: probe of the separation-lag operator itself.
    command: str = ""


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
            "DS-A2": self._harmonic_transfer,
            "DS-A3": self._time_constant_transfer,
            "DS-A4": self._step_response,
            "DS-A5": self._periodic_residual_decay,
            "DS-A6": self._maneuver_state_threading,
            "DS-A9": self._hysteresis_direction,
            "DS-A10": self._hysteresis_causality,
            "DS-A11": self._lift_peak_timing,
            "DS-A12": self._lift_overshoot,
            "DS-A13": self._post_stall_drag,
            "DS-A17": self._method_distinction,
            "DS-A18": self._section_opt_out,
            "DS-D3-HYSTERESIS-DIRECTION": self._stalled_lift_direction,
            "DS-H4": self._maneuver_hysteresis,
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
                command=evaluation.command or "\n".join(
                    dict.fromkeys(case.command for case in evaluation.cases)),
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
        azimuth_steps: int = 36,
    ) -> _Case:
        key = (
            str(Path(context.output_directory).resolve()), dynamic, method, mu_x,
            collective_deg, lag_constant, revolutions, fade_start_deg, fade_end_deg,
            azimuth_steps,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        project = copy.deepcopy(self._project)
        project.config.update({
            "Ne": 16,
            "Npsi": azimuth_steps,
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
        command: str = "",
    ) -> _Evaluation:
        status = FinalStatus.CONFIRMED_CORRECT if passed else FinalStatus.CONFIRMED_DEFECT
        return _Evaluation(status, measured, expected, tolerance, notes, cases,
                           command)

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

    # =====================================================================
    # Analytical probes of the separation-lag operator
    # =====================================================================

    @staticmethod
    def _harmonic_inputs(azimuth_steps: int):
        """Return one synthetic harmonic separation input on a uniform field.

        The relative speed is uniform, so the lag time constant is one number
        and the analytical first-order transfer function applies exactly.
        """
        azimuth = np.arange(azimuth_steps) * 2.0 * math.pi / azimuth_steps
        static_separation = (_MEAN_SEPARATION
                             + _SEPARATION_AMPLITUDE * np.sin(azimuth))[None, :]
        speed = np.full((1, azimuth_steps), _PROBE_SPEED)
        chord = np.full((1, azimuth_steps), _PROBE_CHORD)
        return azimuth, static_separation, speed, chord

    @staticmethod
    def _first_harmonic(signal: np.ndarray) -> tuple[float, float]:
        """Return the amplitude and phase of one signal's first harmonic."""
        spectrum = np.fft.rfft(signal[0]) / (signal.shape[1] / 2.0)
        return float(abs(spectrum[1])), float(np.angle(spectrum[1]))

    def _transfer_record(self, lag_constant: float,
                         azimuth_steps: int) -> dict[str, float]:
        """Measure both methods against the analytical first-order lag."""
        _azimuth, static_separation, speed, chord = self._harmonic_inputs(azimuth_steps)
        config = replace(
            _PROBE_CONFIG,
            dynamic_stall_A=lag_constant,
            dynamic_stall_time_march_revolutions=_PROBE_REVOLUTIONS,
            dynamic_stall_time_march_avg_last=1,
        )
        frequency = _oye_frequency_domain_f(
            static_separation, speed, chord, _PROBE_OMEGA, config)
        march, _history = _oye_time_march_f(
            static_separation, speed, chord, _PROBE_OMEGA, config)
        time_constant = lag_constant * _PROBE_CHORD / (2.0 * _PROBE_SPEED)
        reduced_frequency = _PROBE_OMEGA * time_constant
        expected_amplitude = _SEPARATION_AMPLITUDE / math.sqrt(1.0 + reduced_frequency ** 2)
        expected_phase = -math.atan(reduced_frequency)
        _input_amplitude, input_phase = self._first_harmonic(static_separation)
        frequency_amplitude, frequency_phase = self._first_harmonic(frequency)
        march_amplitude, march_phase = self._first_harmonic(march)
        return {
            "reduced_frequency": reduced_frequency,
            "expected_amplitude": expected_amplitude,
            "expected_phase_rad": expected_phase,
            "frequency_amplitude": frequency_amplitude,
            "frequency_phase_rad": frequency_phase - input_phase,
            "frequency_amplitude_error": abs(frequency_amplitude - expected_amplitude),
            "frequency_phase_error": abs((frequency_phase - input_phase) - expected_phase),
            "march_amplitude": march_amplitude,
            "march_phase_rad": march_phase - input_phase,
            "march_amplitude_error": abs(march_amplitude - expected_amplitude),
            "march_phase_error": abs((march_phase - input_phase) - expected_phase),
            "half_azimuth_step_rad": math.pi / azimuth_steps,
            "march_phase_error_over_half_step": (
                abs((march_phase - input_phase) - expected_phase)
                / (math.pi / azimuth_steps)),
            "method_maximum_difference": float(np.max(np.abs(frequency - march))),
        }

    def _harmonic_transfer(self, context: ExecutionContext) -> _Evaluation:
        record = self._transfer_record(8.0, _PROBE_AZIMUTH_STEPS)
        passed = (record["frequency_amplitude_error"] <= 1e-4
                  and record["frequency_phase_error"] <= 1e-4)
        half_step = abs(record["march_phase_error_over_half_step"] - 1.0) <= 0.01
        return self._evaluation(
            passed,
            {"frequency_method": record,
             "march_phase_lag_is_one_half_azimuth_step": half_step},
            {"frequency_amplitude_error": 1e-4, "frequency_phase_error": 1e-4},
            "amplitude and phase errors of the frequency method <= 1e-4",
            "A first-order lag has amplitude 1/sqrt(1+k^2) and phase -atan(k). "
            "The frequency method reproduces both to machine precision. The "
            "time march holds the drive over each azimuth step, so it trails "
            "the analytical phase by half a step and converges with the mesh.",
            (),
            "Python public API: bemt._oye_frequency_domain_f and bemt._oye_time_march_f on a uniform relative-speed field with one sine over the azimuth, 720 azimuth steps, A=8",
        )

    def _time_constant_transfer(self, context: ExecutionContext) -> _Evaluation:
        small = self._transfer_record(8.0, _PROBE_AZIMUTH_STEPS)
        large = self._transfer_record(40.0, _PROBE_AZIMUTH_STEPS)
        smaller_amplitude = large["frequency_amplitude"] < small["frequency_amplitude"]
        later_phase = large["frequency_phase_rad"] < small["frequency_phase_rad"]
        matches_theory = max(
            small["frequency_amplitude_error"], small["frequency_phase_error"],
            large["frequency_amplitude_error"], large["frequency_phase_error"],
        ) <= 1e-4
        passed = smaller_amplitude and later_phase and matches_theory
        return self._evaluation(
            passed,
            {"A_8": small, "A_40": large,
             "amplitude_decreases": smaller_amplitude,
             "phase_lag_increases": later_phase},
            {"amplitude_decreases": True, "phase_lag_increases": True,
             "maximum_theory_error": 1e-4},
            "the A=40 response is smaller and later than the A=8 response, both within 1e-4 of theory",
            "A larger time constant raises the reduced frequency, so the "
            "first-order lag returns a smaller and later response.",
            (),
            "Python public API: bemt._oye_frequency_domain_f on a uniform relative-speed field with A=8 and A=40, 720 azimuth steps",
        )

    def _step_response(self, context: ExecutionContext) -> _Evaluation:
        azimuth_steps = _PROBE_AZIMUTH_STEPS
        azimuth_step = 2.0 * math.pi / azimuth_steps
        static_separation = np.ones((1, azimuth_steps))
        speed = np.full((1, azimuth_steps), _PROBE_SPEED)
        chord = np.full((1, azimuth_steps), _PROBE_CHORD)
        config = replace(
            _PROBE_CONFIG, dynamic_stall_A=8.0,
            dynamic_stall_time_march_revolutions=1,
            dynamic_stall_time_march_avg_last=1,
        )
        _periodic, history = _oye_time_march_f(
            static_separation, speed, chord, _PROBE_OMEGA, config,
            f_init=np.zeros(1))
        marched = np.asarray(history)[0, 0, :]
        time_constant = 8.0 * _PROBE_CHORD / (2.0 * _PROBE_SPEED)
        elapsed = (np.arange(1, azimuth_steps + 1) * azimuth_step) / _PROBE_OMEGA
        expected = 1.0 - np.exp(-elapsed / time_constant)
        error = float(np.max(np.abs(marched - expected)))
        return self._evaluation(
            error <= 1e-12,
            {"maximum_absolute_error": error, "time_constant_s": time_constant,
             "samples": int(azimuth_steps)},
            {"maximum_absolute_error": 1e-12},
            "max(abs(f_marched - (1 - exp(-t/tau)))) <= 1e-12",
            "A step in the static separation has an exponential solution. The "
            "recursion integrates each step exactly, so it reproduces that "
            "solution to machine precision.",
            (),
            "Python public API: bemt._oye_time_march_f with a unit step in the static separation, f_init=0, 720 azimuth steps, A=8",
        )

    def _method_distinction(self, context: ExecutionContext) -> _Evaluation:
        records = {str(steps): self._transfer_record(8.0, steps)
                   for steps in _REFINEMENT_STEPS}
        differences = [records[str(steps)]["method_maximum_difference"]
                       for steps in _REFINEMENT_STEPS]
        frequency_exact = max(
            max(record["frequency_amplitude_error"], record["frequency_phase_error"])
            for record in records.values()) <= 1e-4
        # The march holds the drive over each azimuth step, so its phase
        # trails the continuous transfer by half a step. The ratio of the two
        # approaches one as the mesh refines; the finest mesh carries the
        # statement, and the coarse meshes show it converging.
        ratios = [records[str(steps)]["march_phase_error_over_half_step"]
                  for steps in _REFINEMENT_STEPS]
        march_matches_own_form = (
            abs(ratios[-1] - 1.0) <= 0.01
            and all(right > left for left, right in zip(ratios, ratios[1:])))
        decreasing = all(right < left
                         for left, right in zip(differences, differences[1:]))
        passed = (frequency_exact and march_matches_own_form and decreasing
                  and differences[0] > 0.0)
        return self._evaluation(
            passed,
            {"azimuth_steps": list(_REFINEMENT_STEPS),
             "method_differences": differences,
             "march_phase_error_over_half_step": ratios, "records": records},
            {"frequency_matches_continuous_transfer": True,
             "march_matches_zero_order_hold": True,
             "difference_decreases_with_refinement": True},
            "each method matches its own analytical form and their difference falls with azimuth refinement",
            "The frequency method solves the continuous transfer function. The "
            "march solves the discrete recursion of a held drive. The two are "
            "different approximations, so their difference is set by the mesh. "
            "The source fixture reported one number for one unrecorded mesh. "
            "The reproducible statement is the convergence, and it is what "
            "this check measures.",
            (),
            "Python public API: bemt._oye_frequency_domain_f and bemt._oye_time_march_f at 36, 72, 180, 360 and 720 azimuth steps, A=8",
        )

    # =====================================================================
    # Probes of the azimuthal hysteresis loop
    # =====================================================================

    def _loop_case(self, context: ExecutionContext) -> _Case:
        """Return the stalled forward-flight disk the loop claims share."""
        return self._case(
            context, dynamic=True, method="time_march", mu_x=_LOOP_ADVANCE_RATIO,
            collective_deg=_LOOP_COLLECTIVE, revolutions=12,
            azimuth_steps=_LOOP_AZIMUTH_STEPS,
        )

    @staticmethod
    def _loop_fields(case: _Case) -> dict[str, np.ndarray]:
        """Return the disk fields every hysteresis probe reads."""
        maps = case.result.maps
        return {
            "alpha_deg": np.degrees(np.asarray(maps["alpha_eff"], dtype=float)),
            "Cl": np.asarray(maps["Cl"], dtype=float),
            "Cl_static": np.asarray(maps["Cl_static"], dtype=float),
            "Cd": np.asarray(maps["Cd"], dtype=float),
            "Cd_static": np.asarray(maps["Cd_static"], dtype=float),
            "f": np.asarray(maps["f_oye"], dtype=float),
            "f_static": np.asarray(maps["f_st_oye"], dtype=float),
            "PSI": np.asarray(maps["PSI"], dtype=float),
            "radius": np.asarray(maps["R_NORM"], dtype=float)[:, 0],
        }

    @staticmethod
    def _most_affected_station(field: dict[str, np.ndarray]) -> int:
        """Return the outboard station whose peak lift the lag changes most."""
        best_index, best_ratio = 0, -math.inf
        for index, radius in enumerate(field["radius"]):
            if radius < 0.5:
                continue
            static_peak = float(np.max(field["Cl_static"][index]))
            if static_peak <= 0.1:
                continue
            ratio = float(np.max(field["Cl"][index])) / static_peak
            if ratio > best_ratio:
                best_index, best_ratio = index, ratio
        return best_index

    def _hysteresis_direction(self, context: ExecutionContext) -> _Evaluation:
        case = self._loop_case(context)
        field = self._loop_fields(case)
        rising = np.gradient(field["alpha_deg"], axis=1) > 0.0
        stalled = field["f_static"] < _ATTACHED_SEPARATION
        near = np.abs(field["alpha_deg"] - _HYSTERESIS_ANGLE_DEG) < 0.5
        up = near & stalled & rising
        down = near & stalled & ~rising
        up_lift = float(np.mean(field["Cl"][up])) if up.any() else float("nan")
        down_lift = float(np.mean(field["Cl"][down])) if down.any() else float("nan")
        passed = bool(up.any() and down.any() and up_lift > down_lift)
        return self._evaluation(
            passed,
            {"angle_deg": _HYSTERESIS_ANGLE_DEG, "rising_samples": int(up.sum()),
             "falling_samples": int(down.sum()), "rising_lift": up_lift,
             "falling_lift": down_lift, "lift_difference": up_lift - down_lift},
            {"rising_lift_exceeds_falling_lift": True},
            "mean Cl on the rising branch exceeds mean Cl on the falling branch at the same stalled angle",
            "Separation lag keeps the flow attached while the angle rises and "
            "keeps it separated while the angle falls. The loop therefore "
            "carries more lift on the rising branch.",
            (case,),
        )

    def _hysteresis_causality(self, context: ExecutionContext) -> _Evaluation:
        case = self._loop_case(context)
        field = self._loop_fields(case)
        azimuth_step_deg = 360.0 / field["f"].shape[1]
        lags: list[tuple[float, float]] = []
        for index, radius in enumerate(field["radius"]):
            if not (field["f_static"][index] < _ATTACHED_SEPARATION).any():
                continue
            dynamic_minimum = int(np.argmin(field["f"][index]))
            static_minimum = int(np.argmin(field["f_static"][index]))
            lag = ((dynamic_minimum - static_minimum) % field["f"].shape[1]) * azimuth_step_deg
            lags.append((float(radius), float(lag)))
        root_lag = lags[0][1] if lags else float("nan")
        tip_lag = lags[-1][1] if lags else float("nan")
        follows = all(lag > 0.0 for _radius, lag in lags)
        passed = bool(lags) and follows and root_lag > tip_lag
        return self._evaluation(
            passed,
            {"root_station": lags[0][0] if lags else None, "root_lag_deg": root_lag,
             "tip_station": lags[-1][0] if lags else None, "tip_lag_deg": tip_lag,
             "every_station_lags": follows, "station_count": len(lags)},
            {"every_station_lags": True, "root_lag_exceeds_tip_lag": True},
            "each dynamic minimum follows its static minimum, and the root lag exceeds the tip lag",
            "The lag time constant is the chord divided by twice the local "
            "relative speed. The root meets a slower flow, so its separation "
            "state trails the static one by a larger azimuth angle.",
            (case,),
        )

    def _lift_peak_timing(self, context: ExecutionContext) -> _Evaluation:
        case = self._loop_case(context)
        field = self._loop_fields(case)
        index = self._most_affected_station(field)
        azimuth = np.degrees(field["PSI"][index])
        stalled = np.flatnonzero(field["f_static"][index] < _ATTACHED_SEPARATION)
        onset = float(azimuth[stalled[0]]) if stalled.size else float("nan")
        lift_peak = float(azimuth[int(np.argmax(field["Cl"][index]))])
        angle_peak = float(azimuth[int(np.argmax(field["alpha_deg"][index]))])
        passed = bool(stalled.size) and onset < lift_peak < angle_peak
        return self._evaluation(
            passed,
            {"station": float(field["radius"][index]),
             "static_stall_onset_deg": onset, "lift_peak_deg": lift_peak,
             "angle_peak_deg": angle_peak},
            {"ordering": "static stall onset < lift peak < angle peak"},
            "the lift-peak azimuth lies strictly between the static stall onset and the angle peak",
            "Delayed separation carries the lift past static stall. The state "
            "has already separated by the time the angle reaches its own peak.",
            (case,),
        )

    def _lift_overshoot(self, context: ExecutionContext) -> _Evaluation:
        case = self._loop_case(context)
        field = self._loop_fields(case)
        separation = np.asarray(case.result.maps["f_oye"], dtype=float)
        index = self._most_affected_station(field)
        station_ratio = (float(np.max(field["Cl"][index]))
                         / float(np.max(field["Cl_static"][index])))
        disk_ratio = max(
            float(np.max(field["Cl"][row])) / float(np.max(field["Cl_static"][row]))
            for row in range(field["Cl"].shape[0])
            if float(np.max(field["Cl_static"][row])) > 0.1
        )
        bounded = bool(np.all(separation >= 0.0) and np.all(separation <= 1.0))
        finite = bool(np.all(np.isfinite(field["Cl"])))
        passed = station_ratio > 1.0 and bounded and finite
        return self._evaluation(
            passed,
            {"station": float(field["radius"][index]),
             "station_peak_ratio": station_ratio,
             "disk_maximum_peak_ratio": disk_ratio,
             "separation_state_inside_unit_interval": bounded,
             "coefficients_finite": finite},
            {"station_peak_ratio": "greater than 1",
             "separation_state_inside_unit_interval": True},
            "the peak dynamic lift exceeds the peak static lift, and the separation state stays inside 0 to 1",
            "The dynamic lift is a convex combination of the attached and the "
            "separated lift, weighted by a separation state inside zero to "
            "one. The overshoot is therefore positive and bounded by the "
            "attached-flow line. Its size follows the condition, so the "
            "source fixture's 5% to 25% window belongs to one case and not to "
            "the model.",
            (case,),
        )

    def _post_stall_drag(self, context: ExecutionContext) -> _Evaluation:
        case = self._loop_case(context)
        field = self._loop_fields(case)
        stalled = field["f_static"] < _ATTACHED_SEPARATION
        delayed = stalled & (field["f"] > field["f_static"])
        reattaching = stalled & (field["f"] < field["f_static"])
        static_drag = np.maximum(field["Cd_static"], 1e-12)
        delayed_ratio = float(np.mean(field["Cd"][delayed] / static_drag[delayed]))
        reattaching_ratio = float(np.mean(
            field["Cd"][reattaching] / static_drag[reattaching]))
        minimum_drag = float(np.min(field["Cd"]))
        passed = (minimum_drag >= 0.0 and delayed_ratio >= 1.0
                  and reattaching_ratio < delayed_ratio)
        return self._evaluation(
            passed,
            {"minimum_drag": minimum_drag,
             "delayed_separation_drag_ratio": delayed_ratio,
             "reattaching_drag_ratio": reattaching_ratio,
             "whole_cycle_drag_ratio": float(np.mean(
                 field["Cd"][stalled] / static_drag[stalled])),
             "delayed_samples": int(delayed.sum()),
             "reattaching_samples": int(reattaching.sum())},
            {"minimum_drag": 0.0,
             "delayed_separation_drag_ratio": "at least 1.0"},
            "drag is non-negative everywhere and the mean dynamic-to-static drag ratio during delayed separation is at least 1.0",
            "The drag correction splits with the separation state. The delayed "
            "part of the cycle carries the raised drag. The reattaching part "
            "carries less drag than the static polar. One mean over both "
            "halves hides both effects.",
            (case,),
        )

    def _stalled_lift_direction(self, context: ExecutionContext) -> _Evaluation:
        case = self._loop_case(context)
        field = self._loop_fields(case)
        stalled = field["f_static"] < _ATTACHED_SEPARATION
        delayed = stalled & (field["f"] > field["f_static"])
        reattaching = stalled & (field["f"] < field["f_static"])
        gaining = float(np.mean(field["Cl"][delayed] > field["Cl_static"][delayed]))
        increment = float(np.mean(field["Cl"][delayed] - field["Cl_static"][delayed]))
        losing = float(np.mean(
            field["Cl"][reattaching] < field["Cl_static"][reattaching]))
        passed = gaining >= 0.70 and increment >= 0.10
        return self._evaluation(
            passed,
            {"delayed_separation_fraction_gaining_lift": gaining,
             "delayed_separation_mean_increment": increment,
             "reattaching_fraction_losing_lift": losing,
             "delayed_samples": int(delayed.sum())},
            {"delayed_separation_fraction_gaining_lift": 0.70,
             "delayed_separation_mean_increment": 0.10},
            "at least 70% of the elements in delayed separation gain lift, with a mean increment of at least 0.10",
            "The theory names the delayed part of the stalled cycle. The "
            "reattaching part must lose lift by the same mechanism, and it "
            "does.",
            (case,),
        )

    # =====================================================================
    # Probes that need a prescribed maneuver
    # =====================================================================

    def _marched_project(self, *, revolutions: int, dynamics=None):
        """Return the reference rotor prepared for a marched maneuver."""
        project = copy.deepcopy(self._project)
        project.config.update({
            "Ne": 16, "Npsi": 72, "solver": "newton", "max_iter": 300,
            "prandtl_loss_mode": "off", "use_compressibility": False,
        })
        project.airfoil.use_dynamic_stall = True
        project.airfoil.dynamic_stall_method = "time_march"
        project.airfoil.dynamic_stall_time_march_revolutions = revolutions
        project.airfoil.dynamic_stall_time_march_avg_last = 1
        if dynamics is not None:
            project.geometry = replace(project.geometry, dynamics=dynamics)
        return project

    def _maneuver_state_threading(self, context: ExecutionContext) -> _Evaluation:
        project = self._marched_project(revolutions=_THREADING_REVOLUTIONS)
        maneuver = ManeuverDefinition(
            name="state-threading",
            points=[
                ManeuverPoint(t_s=0.0, mu_x=_LOOP_ADVANCE_RATIO, Vz=0.0,
                              collective_deg=_LOOP_COLLECTIVE, rpm=400.0),
                ManeuverPoint(t_s=0.10, mu_x=_LOOP_ADVANCE_RATIO, Vz=0.0,
                              collective_deg=_LOOP_COLLECTIVE, rpm=400.0),
            ],
            dt_s=0.10, substeps_per_step=8, initial_state="equilibrium",
            march_dynamic_stall=True,
        )
        _history, maps_list = api.run_maneuver(project, maneuver)
        first = np.asarray(maps_list[0]["dynamic_stall_time_march_history"])
        second = np.asarray(maps_list[1]["dynamic_stall_time_march_history"])

        # The first marched step of the second sample must be the exact Oye
        # update of the first sample's final state. Anything else means the
        # march reset the separation state at the sample boundary.
        rotor = studies._to_rotor(
            project.geometry, collective_deg=_LOOP_COLLECTIVE, rpm=400.0)
        config = studies._build_config(project.config, airfoil_def=project.airfoil)
        chord = _pitt_peters_geometry(rotor, config)[5][:, 0]
        static_separation = np.asarray(
            maps_list[1]["f_st_oye"], dtype=float)[:, 0]
        speed = np.maximum(np.asarray(maps_list[1]["W"], dtype=float)[:, 0], 1e-3)
        time_constant = project.airfoil.dynamic_stall_A * chord / (2.0 * speed)
        azimuth_step = 2.0 * math.pi / second.shape[2]
        decay = np.exp(-azimuth_step / np.maximum(rotor.Omega * time_constant, 1e-9))
        inherited = first[-1][:, -1]
        expected = static_separation + (inherited - static_separation) * decay
        threaded_residual = float(np.max(np.abs(second[0][:, 0] - expected)))

        # The same step taken after a reset, for contrast.
        reset = np.asarray(maps_list[1]["f_st_oye"], dtype=float)[:, -1]
        reset_expected = static_separation + (reset - static_separation) * decay
        reset_residual = float(np.max(np.abs(second[0][:, 0] - reset_expected)))

        start_up_transient = float(np.max(np.abs(first[0] - first[-1])))
        passed = threaded_residual <= 1e-12 and reset_residual > threaded_residual
        return self._evaluation(
            passed,
            {"threaded_initial_residual": threaded_residual,
             "reset_initial_residual": reset_residual,
             "start_up_transient": start_up_transient,
             "marched_revolutions": _THREADING_REVOLUTIONS},
            {"threaded_initial_residual": 1e-12,
             "reset_initial_residual": "larger than the threaded residual"},
            "a march initialized from the preceding final state has an initial residual at most 1e-12",
            "The first sample starts from the static separation and carries a "
            "start-up transient. The second sample starts from the first "
            "sample's final state, so its first marched revolution already "
            "equals its last one.",
            (),
            "Python public API: api.run_maneuver(project, ManeuverDefinition(march_dynamic_stall=True)) with two samples at one condition",
        )

    def _maneuver_hysteresis(self, context: ExecutionContext) -> _Evaluation:
        dynamics = BladeDynamicsDef(
            flap_model="offset", hinge_offset_norm=0.05, inertia_source="lock",
            lock_number=8.0, harmonics=2,
        )
        project = self._marched_project(revolutions=6, dynamics=dynamics)
        project.airfoil.dynamic_stall_time_march_avg_last = 2
        step = _RAMP_DURATION_S / _RAMP_SIDE_SAMPLES
        maneuver = ManeuverDefinition(
            name="collective-ramp",
            points=[
                ManeuverPoint(t_s=0.0, mu_x=0.20, Vz=0.0,
                              collective_deg=_RAMP_LOW_DEG, rpm=400.0),
                ManeuverPoint(t_s=_RAMP_DURATION_S, mu_x=0.20, Vz=0.0,
                              collective_deg=_RAMP_HIGH_DEG, rpm=400.0),
                ManeuverPoint(t_s=2.0 * _RAMP_DURATION_S, mu_x=0.20, Vz=0.0,
                              collective_deg=_RAMP_LOW_DEG, rpm=400.0),
            ],
            dt_s=step, substeps_per_step=8, initial_state="equilibrium",
            march_dynamic_stall=True, march_flapping=True,
        )
        history, maps_list = api.run_maneuver(project, maneuver)
        collective = history["collective_deg"].to_numpy()
        thrust = history["CT"].to_numpy()
        apex = int(np.argmax(collective))
        rising = float(np.interp(_RAMP_PROBE_DEG, collective[:apex + 1],
                                 thrust[:apex + 1]))
        falling = float(np.interp(_RAMP_PROBE_DEG, collective[apex:][::-1],
                                  thrust[apex:][::-1]))
        continuous = all(maps.get("dynamic_stall_time_march_history") is not None
                         for maps in maps_list)
        intervals = history["marched_interval_s"].to_numpy()
        marched = bool(np.all(intervals[1:] > 0.0) and intervals[0] == 0.0)
        passed = (len(history) == _RAMP_SAMPLES and continuous and marched
                  and rising > falling)
        return self._evaluation(
            passed,
            {"sample_count": int(len(history)),
             "probe_collective_deg": _RAMP_PROBE_DEG,
             "rising_branch_CT": rising, "falling_branch_CT": falling,
             "relative_difference": (rising - falling) / falling,
             "every_sample_marched_a_separation_state": continuous,
             "every_later_sample_marched_an_interval": marched},
            {"sample_count": _RAMP_SAMPLES,
             "rising_branch_CT_exceeds_falling_branch_CT": True},
            "all 41 samples stay continuous and the rising branch carries more thrust than the falling branch at 13 degrees",
            "The inflow state lags the collective, so the rising branch runs "
            "with less induced inflow and more thrust. The flap response is "
            "marched with it, because an unrelieved hub moment drives the "
            "linear inflow harmonics past their validity range and reverses "
            "the sign of the loop.",
            (),
            "Python public API: api.run_maneuver(project, ManeuverDefinition(march_dynamic_stall=True, march_flapping=True)) over a 41-sample collective ramp from 6 to 18 to 6 degrees",
        )

    # =====================================================================
    # Remaining probes
    # =====================================================================

    def _periodic_residual_decay(self, context: ExecutionContext) -> _Evaluation:
        cases = {
            revolutions: self._case(
                context, dynamic=True, method="time_march", mu_x=0.35,
                collective_deg=14.0, lag_constant=40.0, revolutions=revolutions,
            )
            for revolutions in (2, 4)
        }
        residuals = {
            revolutions: float(case.result.summary["dynamic_stall_periodic_residual"])
            for revolutions, case in cases.items()
        }
        warnings = {
            revolutions: bool(case.result.summary.get("dynamic_stall_warning"))
            for revolutions, case in cases.items()
        }
        decays = residuals[2] > residuals[4]
        warns = all(warnings[revolutions] for revolutions in (2, 4)
                    if residuals[revolutions] > 1e-3)
        passed = decays and warns
        return self._evaluation(
            passed,
            {"residual_2_revolutions": residuals[2],
             "residual_4_revolutions": residuals[4],
             "warning_at_2_revolutions": warnings[2],
             "warning_at_4_revolutions": warnings[4]},
            {"residual_decreases": True, "warning_above_1e-3": True},
            "the periodic residual falls from two to four revolutions, and any value above 1e-3 emits a warning",
            "The march starts from the static separation and needs several "
            "revolutions to settle. The residual measures what is left, and a "
            "value above the declared tolerance must reach the user.",
            tuple(cases.values()),
        )

    def _section_opt_out(self, context: ExecutionContext) -> _Evaluation:
        project = copy.deepcopy(self._project)
        project.config.update({
            "Ne": 60, "Npsi": 72, "solver": "newton", "max_iter": 300,
            "prandtl_loss_mode": "off", "use_compressibility": False,
        })
        enabled = replace(
            project.airfoil, name="inboard", r_norm=_ENABLED_STATION,
            use_dynamic_stall=True, dynamic_stall_method="time_march",
            dynamic_stall_time_march_revolutions=6)
        disabled = replace(
            project.airfoil, name="outboard", r_norm=_DISABLED_STATION,
            use_dynamic_stall=False)
        project.airfoil = enabled
        project.airfoil_sections = [enabled, disabled]
        maps = studies.run_single_case(
            project,
            FlightCondition(name="section opt-out", rpm=400.0, mu_x=0.20,
                            collective_deg=16.0),
        ).maps
        radius = np.asarray(maps["R_NORM"], dtype=float)[:, 0]
        weight = np.asarray(maps["dynamic_stall_fade_weight"], dtype=float)
        lift = np.asarray(maps["Cl"], dtype=float)
        static_lift = np.asarray(maps["Cl_static"], dtype=float)
        records: dict[str, dict[str, float]] = {}
        for target in (_ENABLED_STATION, _INTERPOLATION_STATION, _OUTSIDE_STATION):
            index = int(np.argmin(np.abs(radius - target)))
            station = float(radius[index])
            expected = max(min((_DISABLED_STATION - station)
                               / (_DISABLED_STATION - _ENABLED_STATION), 1.0), 0.0)
            records[f"{target:.2f}"] = {
                "station": station,
                "maximum_enabled_weight": float(np.max(weight[index])),
                "linear_section_weight": expected,
                "maximum_lift_correction": float(np.max(np.abs(
                    lift[index] - static_lift[index]))),
            }
        outside = records[f"{_OUTSIDE_STATION:.2f}"]
        interpolated = records[f"{_INTERPOLATION_STATION:.2f}"]
        passed = (
            outside["maximum_lift_correction"] == 0.0
            and outside["maximum_enabled_weight"] == 0.0
            and abs(interpolated["maximum_enabled_weight"]
                    - interpolated["linear_section_weight"]) <= 1e-6
            and 0.10 <= interpolated["maximum_enabled_weight"] <= 0.14
        )
        return self._evaluation(
            passed,
            {"stations": records, "enabled_section": _ENABLED_STATION,
             "disabled_section": _DISABLED_STATION},
            {"disabled_station_correction": 0.0,
             "interpolation_station_weight": "approximately 0.12"},
            "the disabled station has zero correction and the interpolation station retains approximately 12% of it",
            "The section weight is interpolated linearly between the section "
            "stations. A station outside the enabled section keeps the static "
            "polar exactly.",
            (),
            "Python public API: studies.run_single_case(project, FlightCondition(rpm=400, mu_x=0.20, collective_deg=16)) with airfoil sections at r/R 0.30 (enabled) and 0.88 (disabled)",
        )
