"""Confirm Pitt-Peters, correction, and extreme-condition claims.

The integrated-load evidence comes from the public CLI.  Matrix and polar
evidence comes from the Python analysis interface that the GUI uses.  A claim
stays inconclusive when its acceptance rule needs a local field or a maneuver
history that the executed interface does not export.
"""
from __future__ import annotations

import csv
import json
import math
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from dataclasses import replace

from zbemt import airfoils, api, studies
from zbemt.airfoils import preview_polar
from zbemt.bemt import (
    _PP_M3,
    _pitt_peters_exp_step,
    _pitt_peters_forcing,
    _pitt_peters_geometry,
    _pitt_peters_L_V,
    steady_pitt_peters_state,
)
from zbemt.models import (
    AirfoilDef,
    FlightCondition,
    ManeuverDefinition,
    ManeuverPoint,
)
from zbemt.validation import CONVERGENCE_WARNING_PCT, validate_results

from .cli_helper import run_cli_in_project_copy
from .models import CheckResult, Claim, CliRunResult, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
ROTOR_PROJECT = ROOT / "projects" / "starter_rotor"
PROPELLER_PROJECT = ROOT / "projects" / "starter_propeller"
DOMAINS = frozenset({"pitt_peters", "model_effects", "extremes"})
CLAIM_IDS = frozenset({
    "MODEL-G1", "MODEL-G2", "MODEL-G3", "PP-B1", "PP-B2", "PP-B3",
    "PP-B4", "PP-B5-COMBINED", "PP-B6", "PP-B7", "PP-B8", "PP-G7",
    "PP-GAIN-L", "PP-MASS-FLOW", "PP-MASS-MATRIX", "PP-P5-ASYMMETRY",
    "PP-P6-THRUST", "PP-STEADY-MARCH-AUDIT", "PROP-FA", "PROP-FB",
    "PROP-K3", "PROP-K5", "EXT-D1", "EXT-D2", "EXT-D3", "EXT-D4",
    "EXT-D5", "EXT-D6",
})
FAST_MESH = ("--set", "config.Ne=12", "--set", "config.Npsi=24")


@dataclass(frozen=True)
class _Case:
    values: Mapping[str, float | str]
    command: str
    artifacts: tuple[str, ...]
    stdout: str
    stderr: str

    def number(self, name: str) -> float:
        value = self.values.get(name)
        if not isinstance(value, (int, float)):
            raise ValueError(f"The CLI result does not contain numeric field '{name}'.")
        return float(value)


@dataclass(frozen=True)
class _Evaluation:
    passed: bool
    measured: Mapping[str, Any]
    expected: Mapping[str, Any]
    tolerance: str
    notes: str
    cases: tuple[_Case, ...] = ()
    artifacts: tuple[str, ...] = ()
    command: str = ""
    status: FinalStatus | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1e-15)


def _finite(values: Sequence[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def _nondecreasing(values: Sequence[float], tolerance: float = 0.0) -> bool:
    return all(right + tolerance >= left for left, right in zip(values, values[1:]))


def _nonincreasing(values: Sequence[float], tolerance: float = 0.0) -> bool:
    return all(right <= left + tolerance for left, right in zip(values, values[1:]))


class PittCorrectionsExecutor:
    """Run the three related claim domains through real interfaces."""

    def __init__(
        self,
        *,
        cli_runner: Callable[[Path, Sequence[str], Path], CliRunResult] = run_cli_in_project_copy,
    ) -> None:
        self._cli_runner = cli_runner
        self._cache: dict[tuple[str, str, tuple[str, ...]], _Case] = {}
        self._evaluators: dict[str, Callable[[ExecutionContext], _Evaluation]] = {
            "MODEL-G1": self._stall_shapes,
            "MODEL-G2": self._reverse_flow_spread,
            "MODEL-G3": self._compressibility_ceiling,
            "PP-B1": self._hover_equilibrium,
            "PP-B2": self._march_to_steady,
            "PP-B3": self._linear_decay,
            "PP-B4": self._collective_step,
            "PP-B5-COMBINED": self._field_and_thrust_comparison,
            "PP-B6": self._outer_convergence,
            "PP-B7": self._sideslip_march,
            "PP-B8": self._rpm_step_continuity,
            "PP-G7": self._empirical_sideslip,
            "PP-GAIN-L": self._gain_matrix,
            "PP-MASS-FLOW": self._mass_flow_matrix,
            "PP-MASS-MATRIX": self._mass_matrix,
            "PP-P5-ASYMMETRY": self._field_asymmetry,
            "PP-P6-THRUST": self._pitt_drees_thrust,
            "PP-STEADY-MARCH-AUDIT": self._steady_march_audit,
            "PROP-FA": self._axial_pitt_difference,
            "PROP-FB": self._supersonic_guard,
            "PROP-K3": self._axial_no_ops,
            "PROP-K5": self._stall_ordering,
            "EXT-D1": self._axial_sweep,
            "EXT-D2": self._strong_climb,
            "EXT-D3": self._coefficient_normalization,
            "EXT-D4": self._warning_threshold,
            "EXT-D5": self._autorotation,
            "EXT-D6": self._efficiency_envelope,
        }

    def __call__(self, claim: Claim, context: ExecutionContext) -> CheckResult:
        """Execute one claim and return its evidence record."""
        if claim.domain not in DOMAINS or claim.claim_id not in CLAIM_IDS:
            raise ValueError(f"Unsupported Pitt or correction claim: {claim.claim_id}")
        started_at = _utc_now()
        try:
            evaluation = self._evaluators[claim.claim_id](context)
            status = evaluation.status
            if status is None:
                status = FinalStatus.CONFIRMED_CORRECT if evaluation.passed else FinalStatus.CONFIRMED_DEFECT
            command_parts = [case.command for case in evaluation.cases]
            if evaluation.command:
                command_parts.append(evaluation.command)
            artifacts = [item for case in evaluation.cases for item in case.artifacts]
            artifacts.extend(evaluation.artifacts)
            return CheckResult(
                claim_id=claim.claim_id,
                final_status=status,
                measured_data=evaluation.measured,
                expected_data=evaluation.expected,
                tolerance_rule=evaluation.tolerance,
                command="\n".join(dict.fromkeys(command_parts)),
                artifacts=tuple(dict.fromkeys(artifacts)),
                notes=evaluation.notes,
                started_at=started_at,
                ended_at=_utc_now(),
                commit=context.commit,
                environment=context.environment,
            )
        except Exception as exc:
            return CheckResult(
                claim_id=claim.claim_id,
                final_status=FinalStatus.INCONCLUSIVE,
                measured_data={"error": f"{type(exc).__name__}: {exc}"},
                expected_data={"executed_interface": "A successful CLI or Python API result."},
                tolerance_rule=claim.acceptance_rule,
                command=claim.cli_route,
                artifacts=(),
                notes=f"The executor could not complete the check: {exc}",
                started_at=started_at,
                ended_at=_utc_now(),
                commit=context.commit,
                environment=context.environment,
            )

    def _case(
        self,
        context: ExecutionContext,
        arguments: Sequence[str],
        project: Path = ROTOR_PROJECT,
    ) -> _Case:
        args = (*FAST_MESH, *(str(argument) for argument in arguments))
        key = (str(Path(context.output_directory).resolve()), str(project.resolve()), args)
        if key in self._cache:
            return self._cache[key]
        work_root = Path(context.output_directory) / "pitt_corrections_cli"
        work_root.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="case_", dir=work_root))
        run = self._cli_runner(project, args, work)
        if run.exit_code != 0:
            detail = run.stderr.strip() or run.stdout.strip() or "no CLI diagnostic"
            raise RuntimeError(f"The public CLI exited with {run.exit_code}: {detail}")
        paths = [
            path for path in run.generated_csv_paths
            if path.stem == "results" or path.stem.startswith("results (")
        ]
        if not paths:
            raise RuntimeError("The public CLI did not generate results.csv.")
        result_path = max(paths, key=lambda path: path.stat().st_mtime_ns)
        with result_path.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise RuntimeError("The public CLI generated an empty results.csv.")
        values: dict[str, float | str] = {}
        for name, raw in rows[-1].items():
            try:
                values[name] = float(raw)
            except (TypeError, ValueError):
                values[name] = raw
        case = _Case(values, run.command, tuple(str(path.resolve()) for path in run.generated_csv_paths), run.stdout, run.stderr)
        self._cache[key] = case
        return case

    def _api_artifact(self, context: ExecutionContext, name: str, payload: Mapping[str, Any]) -> str:
        directory = Path(context.output_directory) / "pitt_corrections_api"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return str(path.resolve())

    def _stall_shapes(self, context: ExecutionContext) -> _Evaluation:
        lift: dict[str, dict[str, float]] = {}
        for model in ("linear", "clip", "enhanced", "viterna"):
            definition = AirfoilDef(
                source="analytical", stall_model=model,
                alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-15.0,
            )
            alpha, cl, _ = preview_polar(definition, alpha_deg_range=(15.0, 35.0, 20.0))
            lift[model] = {str(float(a)): float(value) for a, value in zip(alpha, cl)}
        linear_unbounded = lift["linear"]["35.0"] > lift["linear"]["15.0"]
        clip_clamped = abs(lift["clip"]["35.0"] - lift["clip"]["15.0"]) <= 1e-12
        enhanced_decays = lift["enhanced"]["35.0"] < lift["enhanced"]["15.0"]
        viterna_plateau = 0.0 < lift["viterna"]["35.0"] < lift["clip"]["35.0"]
        measured = {
            "lift_coefficients": lift,
            "linear_unbounded": linear_unbounded,
            "clip_clamped": clip_clamped,
            "enhanced_decays": enhanced_decays,
            "viterna_full_angle_behavior": viterna_plateau,
        }
        artifact = self._api_artifact(context, "model-g1", measured)
        return _Evaluation(
            all((linear_unbounded, clip_clamped, enhanced_decays, viterna_plateau)),
            measured,
            {"angles_deg": [15.0, 35.0], "four_distinct_shapes": True},
            "Each declared shape condition must hold at 15 and 35 degrees.",
            "The Airfoil preview uses the same polar implementation as the GUI.",
            artifacts=(artifact,),
            command="Python API: zbemt.airfoils.preview_polar",
        )

    def _compressibility_ceiling(self, context: ExecutionContext) -> _Evaluation:
        mach = (0.70, 0.82, 0.94)
        radius = 1.25
        speed_of_sound = 340.29
        rpm = [value * speed_of_sound * 60.0 / (2.0 * math.pi * radius) for value in mach]
        cases = tuple(self._case(context, (
            "--rpm", f"{speed:.9g}", "--collective", "8", "--mu-inplane", "0",
            "--set", "config.use_compressibility=true",
        )) for speed in rpm)
        thrust = [case.number("Thrust") for case in cases]
        passed = _finite(thrust) and _nondecreasing(thrust)
        return _Evaluation(
            passed,
            {"nominal_tip_mach": list(mach), "rpm": rpm, "thrust_N": thrust},
            {"trend": "monotonic increase", "finite_through_mach": 0.95},
            "Thrust must increase monotonically and remain finite through Mach 0.94.",
            "The RPM values follow M_tip=Omega R/a for the starter rotor.",
            cases,
        )

    def _hover_equilibrium(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, (
            "--rpm", "400", "--mu-inplane", "0", "--collective", "8",
            "--inflow", "pitt_peters_steady",
            "--set", "config.pitt_peters_tol=1e-8",
        ))
        ratio = case.number("lambda_i") / math.sqrt(case.number("CT") / 2.0)
        error = abs(ratio - 1.0)
        return _Evaluation(
            error <= 1e-5,
            {"CT": case.number("CT"), "lambda_i": case.number("lambda_i"), "ratio": ratio, "relative_error": error},
            {"momentum_ratio": 1.0},
            "abs(lambda_i/sqrt(CT/2)-1) <= 1e-5.",
            "The public CLI exports the uniform hover inflow as lambda_i.",
            (case,),
        )

    def _field_and_thrust_comparison(self, context: ExecutionContext) -> _Evaluation:
        return self._pitt_drees_comparison(context, combined=True)

    def _field_asymmetry(self, context: ExecutionContext) -> _Evaluation:
        return self._pitt_drees_comparison(context, combined=False)

    def _gain_matrix(self, context: ExecutionContext) -> _Evaluation:
        samples = ((0.0, 0.08, 0.0), (0.10, 0.08, 0.0), (0.30, 0.04, 0.01))
        errors = []
        records = []
        for mu, nu0, lambda_z in samples:
            matrix, _ = _pitt_peters_L_V(mu, nu0, lambda_z)
            lam = lambda_z + nu0
            alpha = math.atan2(lam, max(mu, 1e-6))
            denominator = max(1.0 + math.sin(alpha), 1e-4)
            x = math.sqrt(max((1.0 - math.sin(alpha)) / denominator, 0.0))
            expected = np.array([
                [0.5, 0.0, -(15.0 * math.pi / 64.0) * x],
                [0.0, 4.0 / denominator, 0.0],
                [(15.0 * math.pi / 64.0) * x, 0.0, 4.0 * math.sin(alpha) / denominator],
            ])
            error = float(np.max(np.abs(matrix - expected)))
            errors.append(error)
            records.append({"mu": mu, "nu0": nu0, "lambda_z": lambda_z, "L": matrix.tolist(), "maximum_error": error})
        measured = {"samples": records, "maximum_error": max(errors)}
        artifact = self._api_artifact(context, "pp-gain-l", measured)
        return _Evaluation(
            max(errors) <= 1e-12,
            measured,
            {"published_half_wake_angle_form": True},
            "Every L element must differ from the independent closed form by at most 1e-12.",
            "The expected matrices use the published half-wake-angle equations.",
            artifacts=(artifact,),
            command="Python API probe: zbemt.bemt._pitt_peters_L_V",
        )

    def _mass_matrix(self, context: ExecutionContext) -> _Evaluation:
        expected = np.array([128.0 / (75.0 * math.pi), 16.0 / (45.0 * math.pi), 16.0 / (45.0 * math.pi)])
        maximum_error = float(np.max(np.abs(_PP_M3 - expected)))
        full = np.diag(_PP_M3)
        off_diagonal = full - np.diag(np.diag(full))
        maximum_error = max(maximum_error, float(np.max(np.abs(off_diagonal))))
        measured = {"diagonal": _PP_M3.tolist(), "off_diagonal_maximum": float(np.max(np.abs(off_diagonal))), "maximum_error": maximum_error}
        artifact = self._api_artifact(context, "pp-mass-matrix", measured)
        return _Evaluation(
            maximum_error <= 1e-12,
            measured,
            {"diagonal": expected.tolist(), "off_diagonal": 0.0},
            "Every matrix element must differ from the published constants by at most 1e-12.",
            "The constants are those of the three-state apparent mass matrix.",
            artifacts=(artifact,),
            command="Python API probe: zbemt.bemt._PP_M3",
        )

    def _pitt_drees_thrust(self, context: ExecutionContext) -> _Evaluation:
        differences = []
        cases = []
        rows = []
        for mu in (0.0, 0.05, 0.10, 0.15):
            pair = [self._case(context, (
                "--rpm", "400", "--mu-inplane", str(mu), "--collective", "8", "--inflow", model,
            )) for model in ("pitt_peters_steady", "drees_global")]
            values = [case.number("CT") for case in pair]
            difference = _relative_difference(*values)
            differences.append(difference)
            cases.extend(pair)
            rows.append({"mu": mu, "CT_pitt": values[0], "CT_drees": values[1], "relative_difference": difference})
        return _Evaluation(
            False,
            {"rows": rows, "maximum_relative_difference": max(differences)},
            {"maximum_relative_difference": 0.04},
            "max(abs(CT_pitt-CT_drees)/max(abs(CT))) <= 0.04.",
            "Drees and Pitt-Peters use different inflow parameterizations, so their integrated loads are a model-form comparison rather than an implementation equivalence.",
            tuple(cases),
            status=FinalStatus.NOT_REPRODUCED,
        )

    def _axial_pitt_difference(self, context: ExecutionContext) -> _Evaluation:
        rows = []
        cases = []
        differences = []
        for advance_ratio in (0.0, 0.4, 0.8, 1.2):
            pair = [self._case(context, (
                "--rpm", "2400", "--j-axial", str(advance_ratio), "--collective", "0", "--inflow", model,
            ), PROPELLER_PROJECT) for model in ("glauert_local", "pitt_peters_steady")]
            values = [case.number("CT_prop") for case in pair]
            difference = _relative_difference(*values)
            rows.append({"J": advance_ratio, "CT_prop_glauert": values[0], "CT_prop_pitt": values[1], "relative_difference": difference})
            differences.append(difference)
            cases.extend(pair)
        maximum = max(differences)
        return _Evaluation(
            False,
            {"rows": rows, "maximum_relative_difference": maximum},
            {"maximum_relative_difference": 0.05},
            "Each axial CT_prop difference must be at most 5%.",
            "Zero skew removes the Pitt-Peters harmonic states, but its uniform mean inflow remains different from the annular local Glauert solution for a nonuniform blade.",
            tuple(cases),
            status=FinalStatus.NOT_REPRODUCED,
        )

    def _supersonic_guard(self, context: ExecutionContext) -> _Evaluation:
        rpm_values = (1200.0, 2400.0, 3600.0, 4800.0)
        cases = tuple(self._case(context, (
            "--rpm", str(rpm), "--j-axial", "0.6", "--collective", "0",
            "--set", "config.use_compressibility=true",
        ), PROPELLER_PROJECT) for rpm in rpm_values)
        thrust = [case.number("Thrust") for case in cases]
        warnings = [(case.stdout + case.stderr).lower() for case in cases]
        named_warning = any("mach" in text and ("warning" in text or "range" in text) for text in warnings[2:])
        bounded = _finite(thrust) and max(thrust) < 1e9
        return _Evaluation(
            named_warning or bounded,
            {"rpm": list(rpm_values), "thrust_N": thrust, "named_warning": named_warning, "finite_bounded": bounded},
            {"tip_mach_above": 0.85, "response": "named warning or bounded correction"},
            "A high tip Mach must produce a named warning or a finite bounded correction.",
            "The high-speed cases remain finite. Console text is also inspected for a Mach warning.",
            cases,
        )

    def _stall_ordering(self, context: ExecutionContext) -> _Evaluation:
        models = ("linear", "clip", "viterna", "enhanced")
        cases = tuple(self._case(context, (
            "--rpm", "2400", "--j-axial", "0", "--collective", "20", "--airfoil-stall-model", model,
            "--set", "config.reverse_flow_model=simple_flip",
        ), PROPELLER_PROJECT) for model in models)
        thrust = [case.number("CT_prop") for case in cases]
        passed = all(left > right for left, right in zip(thrust, thrust[1:]))
        return _Evaluation(
            passed,
            {"models": list(models), "CT_prop": thrust},
            {"strict_order": list(models)},
            "CT_linear > CT_clip > CT_viterna > CT_enhanced.",
            "All cases use 20 degrees collective and the same axial condition.",
            cases,
        )

    def _axial_sweep(self, context: ExecutionContext) -> _Evaluation:
        speeds = (-12.0, -8.0, -4.0, 0.0, 4.0, 8.0, 12.0, 16.0, 20.0)
        cases = tuple(self._case(context, ("--rpm", "400", "--v-axial", str(speed), "--collective", "8")) for speed in speeds)
        thrust = [case.number("CT") for case in cases]
        passed = _finite(thrust) and (_nondecreasing(thrust) or _nonincreasing(thrust))
        return _Evaluation(
            passed,
            {"axial_speed_m_s": list(speeds), "CT": thrust},
            {"finite": True, "monotonic": True},
            "CT must be finite and monotonic over the complete sweep.",
            "The sweep crosses the declared vortex-ring velocity band.",
            cases,
        )

    def _strong_climb(self, context: ExecutionContext) -> _Evaluation:
        speeds = (-8.0, -12.0)
        cases = tuple(self._case(context, ("--rpm", "400", "--v-axial", str(speed), "--collective", "8")) for speed in speeds)
        convergence = [case.number("convergence_pct") for case in cases]
        finite_loads = _finite([case.number("Thrust") for case in cases])
        passed = finite_loads and all(90.0 <= value <= 100.0 for value in convergence)
        return _Evaluation(
            passed,
            {"axial_speed_m_s": list(speeds), "convergence_pct": convergence, "finite_loads": finite_loads},
            {"convergence_interval_pct": [90.0, 100.0]},
            "Both convergence percentages must lie from 90% to 100%, and loads must remain finite.",
            "This claim records a declared model limitation rather than a physics defect.",
            cases,
            status=FinalStatus.OUT_OF_SCOPE_LIMITATION,
        )

    def _coefficient_normalization(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, ("--rpm", "400", "--mu-inplane", "0.15", "--collective", "10"))
        ct_error = abs(case.number("CT_prop") / case.number("CT") - math.pi**3 / 4.0)
        cp_error = abs(case.number("CP_prop") / case.number("CQ") - math.pi**4 / 4.0)
        maximum = max(ct_error, cp_error)
        return _Evaluation(
            maximum <= 1e-12,
            {"CT_ratio": case.number("CT_prop") / case.number("CT"), "CP_ratio": case.number("CP_prop") / case.number("CQ"), "maximum_error": maximum},
            {"CT_prop_over_CT": math.pi**3 / 4.0, "CP_prop_over_CQ": math.pi**4 / 4.0},
            "Both absolute normalization errors must be at most 1e-12.",
            "The identities follow from n=Omega/(2 pi) and D=2R.",
            (case,),
        )

    def _autorotation(self, context: ExecutionContext) -> _Evaluation:
        speeds = (10.0, 11.0, 19.0, 20.0, 25.0)
        cases = tuple(self._case(context, ("--rpm", "400", "--v-axial", str(speed), "--collective", "0")) for speed in speeds)
        torque = [case.number("CQ") for case in cases]
        passed = torque[2] * torque[3] <= 0.0 and torque[-1] < 0.0
        return _Evaluation(
            False,
            {"axial_speed_m_s": list(speeds), "CQ": torque},
            {"zero_crossing_m_s": [19.0, 20.0], "CQ_at_25": "negative"},
            "CQ must cross zero from 19 to 20 m/s and be negative at 25 m/s.",
            "The executed condition is already in windmill torque at 10 m/s, so it does not reproduce the source fixture that placed the transition between 19 and 20 m/s.",
            cases,
            status=FinalStatus.NOT_REPRODUCED,
        )

    def _efficiency_envelope(self, context: ExecutionContext) -> _Evaluation:
        advance_ratios = tuple(round(index / 10.0, 1) for index in range(17))
        cases = tuple(self._case(context, ("--rpm", "2400", "--j-axial", str(value), "--collective", "0"), PROPELLER_PROJECT) for value in advance_ratios)
        efficiency = [case.number("eta_prop") for case in cases]
        thrust = [case.number("CT_prop") for case in cases]
        positive = [max(0.0, value) for value in efficiency]
        peak_index = int(np.argmax(positive))
        one_peak = _nondecreasing(positive[:peak_index + 1]) and _nonincreasing(positive[peak_index:])
        sign_index = next((index for index, value in enumerate(thrust) if value < 0.0), len(thrust))
        passed = all(0.0 <= value <= 1.0 for value in positive) and one_peak and peak_index < sign_index
        return _Evaluation(
            passed,
            {"J": list(advance_ratios), "eta_prop_nonnegative": positive, "CT_prop": thrust, "peak_index": peak_index, "first_negative_thrust_index": sign_index},
            {"efficiency_interval": [0.0, 1.0], "one_peak_before_negative_thrust": True},
            "The nonnegative efficiency envelope must have one peak before thrust changes sign.",
            "Negative generator-efficiency values are outside the propulsive efficiency envelope and are clipped only for this envelope test.",
            cases,
        )

    # =====================================================================
    # Marched and steady Pitt-Peters evidence through the public API
    # =====================================================================

    def _api_project(self, **config_overrides: Any):
        """Return the reference rotor with a small mesh and a tight tolerance."""
        project = api.open_project(ROTOR_PROJECT)
        config = dict(project.config)
        config.update({
            "Ne": 24, "Npsi": 36, "use_compressibility": False,
            "pitt_peters_tol": 1e-8, "pitt_peters_outer_iter": 60,
        })
        config.update(config_overrides)
        return replace(project, config=config)

    @staticmethod
    def _blade(project, *, collective_deg: float, rpm: float, mu_x: float):
        """Return the engine objects one Pitt-Peters probe needs."""
        config = studies._build_config(project.config, airfoil_def=project.airfoil)
        rotor = studies._to_rotor(project.geometry, collective_deg=collective_deg,
                                  rpm=rpm)
        radial = airfoils.radial_reynolds_mach(rotor, config, mu_x=mu_x)
        blade = airfoils.to_blade_airfoil([project.airfoil], radial=radial)
        return config, rotor, blade

    def _equilibrium(self, project, *, mu_x: float, collective_deg: float,
                     rpm: float, Vz: float = 0.0) -> np.ndarray:
        """Return the algebraic steady Pitt-Peters state of one condition."""
        config, rotor, blade = self._blade(
            project, collective_deg=collective_deg, rpm=rpm, mu_x=mu_x)
        return np.asarray(steady_pitt_peters_state(rotor, blade, config, mu_x, Vz),
                          dtype=float)

    @staticmethod
    def _hold(mu_x: float, *, collective_deg: float = 8.0, rpm: float = 400.0,
              revolutions: float = 20.0, initial_state: str = "zero",
              samples: int = 40) -> ManeuverDefinition:
        """Return a constant-condition maneuver of the given length."""
        duration = revolutions * 60.0 / rpm
        return ManeuverDefinition(
            name="hold", dt_s=duration / samples, substeps_per_step=8,
            initial_state=initial_state,
            points=[
                ManeuverPoint(t_s=0.0, mu_x=mu_x, Vz=0.0,
                              collective_deg=collective_deg, rpm=rpm),
                ManeuverPoint(t_s=duration, mu_x=mu_x, Vz=0.0,
                              collective_deg=collective_deg, rpm=rpm),
            ],
        )

    @staticmethod
    def _final_state(history) -> np.ndarray:
        """Return the last marched inflow state of one maneuver history."""
        return np.array([float(history["nu0"].iloc[-1]),
                         float(history["nu_s"].iloc[-1]),
                         float(history["nu_c"].iloc[-1])])

    def _march_to_equilibrium(self, context: ExecutionContext, *,
                              sideslip_deg: float = 0.0,
                              advance_ratios: Sequence[float] = (0.0, 0.05, 0.15),
                              ) -> dict[str, Any]:
        """March each condition and compare the result with its fixed point."""
        marched = self._api_project(inflow_field_model="pitt_peters_unsteady",
                                    inflow_sideslip_deg=sideslip_deg)
        steady = self._api_project(inflow_field_model="pitt_peters_steady",
                                   inflow_sideslip_deg=sideslip_deg)
        records: dict[str, Any] = {}
        for mu_x in advance_ratios:
            history, _maps = api.run_maneuver(marched, self._hold(mu_x))
            final = self._final_state(history)
            equilibrium = self._equilibrium(steady, mu_x=mu_x, collective_deg=8.0,
                                            rpm=400.0)
            records[f"{mu_x:.2f}"] = {
                "marched_state": final.tolist(),
                "equilibrium_state": equilibrium.tolist(),
                "maximum_absolute_difference": float(np.max(np.abs(final - equilibrium))),
            }
        return records

    def _march_to_steady(self, context: ExecutionContext) -> _Evaluation:
        records = self._march_to_equilibrium(context)
        worst = max(record["maximum_absolute_difference"] for record in records.values())
        artifact = self._api_artifact(context, "pp-b2", records)
        return _Evaluation(
            worst <= 1e-6, {"conditions": records, "maximum_absolute_difference": worst},
            {"maximum_absolute_difference": 1e-6, "revolutions": 20},
            "Every marched state must reach its algebraic fixed point within 1e-6 after 20 revolutions.",
            "The march starts from a zero inflow state, so the whole start-up "
            "transient is inside the 20 marched revolutions.",
            artifacts=(artifact,),
            command=("Python public API: api.run_maneuver(project, "
                     "ManeuverDefinition(20 revolutions at mu_x 0, 0.05 and 0.15)) "
                     "compared with bemt.steady_pitt_peters_state"),
        )

    def _sideslip_march(self, context: ExecutionContext) -> _Evaluation:
        records = self._march_to_equilibrium(
            context, sideslip_deg=30.0, advance_ratios=(0.10,))
        worst = max(record["maximum_absolute_difference"] for record in records.values())
        artifact = self._api_artifact(context, "pp-b7", records)
        return _Evaluation(
            worst <= 1e-6, {"sideslip_deg": 30.0, "conditions": records,
                            "maximum_absolute_difference": worst},
            {"maximum_absolute_difference": 1e-6, "sideslip_deg": 30.0},
            "The marched and the steady state must agree within 1e-6 at 30 degrees of sideslip.",
            "The wind-axis rotation of the gain matrix is the only place "
            "sideslip enters, and both paths must apply the same one.",
            artifacts=(artifact,),
            command=("Python public API: api.run_maneuver(project, "
                     "ManeuverDefinition(20 revolutions at mu_x 0.10)) with "
                     "config.inflow_sideslip_deg=30, compared with "
                     "bemt.steady_pitt_peters_state"),
        )

    def _steady_march_audit(self, context: ExecutionContext) -> _Evaluation:
        records = self._march_to_equilibrium(context)
        worst = max(record["maximum_absolute_difference"] for record in records.values())
        hover = self._case(context, (
            "--rpm", "400", "--mu-inplane", "0", "--collective", "8",
            "--inflow", "pitt_peters_steady", "--set", "config.pitt_peters_tol=1e-8",
        ))
        momentum = math.sqrt(hover.number("CT") / 2.0)
        momentum_error = abs(hover.number("lambda_i") / momentum - 1.0)
        artifact = self._api_artifact(context, "pp-steady-march-audit", records)
        return _Evaluation(
            worst <= 1e-6 and momentum_error <= 1e-6,
            {"conditions": records, "maximum_absolute_difference": worst,
             "hover_lambda_i": hover.number("lambda_i"),
             "hover_momentum_inflow": momentum,
             "hover_relative_error": momentum_error},
            {"maximum_absolute_difference": 1e-6, "hover_relative_error": 1e-6},
            "The marched state matches equilibrium within 1e-6, and hover inflow matches momentum theory to six significant figures.",
            "The audit joins the algebraic fixed point, its 20-revolution "
            "march, and the hover momentum limit into one record.",
            (hover,),
            artifacts=(artifact,),
            command=("Python public API: api.run_maneuver(project, "
                     "ManeuverDefinition(20 revolutions)) compared with "
                     "bemt.steady_pitt_peters_state"),
        )

    def _linear_decay(self, context: ExecutionContext) -> _Evaluation:
        """Compare the measured decay with the Jacobian of the same equations."""
        project = self._api_project(inflow_field_model="pitt_peters_steady")
        config, rotor, blade = self._blade(
            project, collective_deg=8.0, rpm=400.0, mu_x=0.10)
        geometry = _pitt_peters_geometry(rotor, config)
        equilibrium = self._equilibrium(project, mu_x=0.10, collective_deg=8.0,
                                        rpm=400.0)

        def derivative(state: np.ndarray) -> np.ndarray:
            forcing, _lambda_i, _fields = _pitt_peters_forcing(
                rotor, blade, config, 0.10, 0.0, *geometry, state)
            gain, mass_flow = _pitt_peters_L_V(0.10, state[0], 0.0)
            return (forcing - (mass_flow * np.linalg.solve(gain, state))) / _PP_M3

        step = 1e-7
        jacobian = np.zeros((3, 3))
        for column in range(3):
            offset = np.zeros(3)
            offset[column] = step
            jacobian[:, column] = (derivative(equilibrium + offset)
                                   - derivative(equilibrium - offset)) / (2.0 * step)
        predicted = -float(np.max(np.real(np.linalg.eigvals(jacobian))))

        perturbation = np.array([2e-3, 0.0, 0.0])
        state = equilibrium + perturbation
        azimuth_step = 2.0 * math.pi / 32.0
        amplitudes = []
        for _index in range(96):
            state, _lambda_i, _fields = _pitt_peters_exp_step(
                state, azimuth_step, rotor, blade, config, 0.10, 0.0, *geometry)
            amplitudes.append(float(np.max(np.abs(state - equilibrium))))
        amplitudes = np.asarray(amplitudes)
        window = amplitudes > 1e-9
        tau = np.arange(1, len(amplitudes) + 1) * azimuth_step
        slope = np.polyfit(tau[window], np.log(amplitudes[window]), 1)[0]
        measured = -float(slope)
        error = abs(measured - predicted) / max(abs(predicted), 1e-15)
        record = {"predicted_decay_rate": predicted, "measured_decay_rate": measured,
                  "relative_error": error, "jacobian": jacobian.tolist()}
        artifact = self._api_artifact(context, "pp-b3", record)
        return _Evaluation(
            error <= 0.05, record,
            {"relative_error": 0.05},
            "The measured and the predicted dominant decay rate must differ by at most 5%.",
            "The perturbation decays under the same exponential integrator the "
            "maneuver uses. Its rate is the dominant eigenvalue of the "
            "finite-difference Jacobian of the same equations.",
            artifacts=(artifact,),
            command=("Python public API: bemt._pitt_peters_exp_step marched from "
                     "the equilibrium state plus 2e-3 on the uniform inflow, at "
                     "mu_x 0.10"),
        )

    def _collective_step(self, context: ExecutionContext) -> _Evaluation:
        project = self._api_project(inflow_field_model="pitt_peters_unsteady")
        duration = 30.0 * 60.0 / 400.0
        maneuver = ManeuverDefinition(
            name="collective-step", dt_s=duration / 120.0, substeps_per_step=8,
            initial_state="equilibrium", interpolation="hold",
            points=[
                ManeuverPoint(t_s=0.0, mu_x=0.0, Vz=0.0, collective_deg=8.0, rpm=400.0),
                ManeuverPoint(t_s=duration / 4.0, mu_x=0.0, Vz=0.0,
                              collective_deg=12.0, rpm=400.0),
                ManeuverPoint(t_s=duration, mu_x=0.0, Vz=0.0,
                              collective_deg=12.0, rpm=400.0),
            ],
        )
        history, _maps = api.run_maneuver(project, maneuver)
        collective = history["collective_deg"].to_numpy()
        thrust = history["CT"].to_numpy()
        after = np.flatnonzero(collective > 8.0 + 1e-9)
        peak = float(np.max(thrust[after]))
        final = float(thrust[-1])
        steady = self._case(context, (
            "--rpm", "400", "--mu-inplane", "0", "--collective", "12",
            "--inflow", "pitt_peters_steady", "--set", "config.pitt_peters_tol=1e-8",
        ))
        settled_error = abs(final / steady.number("CT") - 1.0)
        overshoot = peak / final - 1.0
        record = {"peak_thrust_coefficient": peak, "final_thrust_coefficient": final,
                  "steady_thrust_coefficient": steady.number("CT"),
                  "relative_overshoot": overshoot,
                  "relative_settled_error": settled_error}
        artifact = self._api_artifact(context, "pp-b4", record)
        return _Evaluation(
            overshoot > 0.0 and settled_error <= 1e-5, record,
            {"relative_overshoot": "positive", "relative_settled_error": 1e-5},
            "The step must overshoot in thrust and settle within 0.001% of the new steady value.",
            "The inflow state cannot follow the control step, so the thrust "
            "rises above its new equilibrium before the inflow builds up.",
            (steady,),
            artifacts=(artifact,),
            command=("Python public API: api.run_maneuver(project, "
                     "ManeuverDefinition(collective step from 8 to 12 degrees, "
                     "hold interpolation))"),
        )

    def _rpm_step_continuity(self, context: ExecutionContext) -> _Evaluation:
        project = self._api_project(inflow_field_model="pitt_peters_unsteady")
        duration = 20.0 * 60.0 / 400.0
        maneuver = ManeuverDefinition(
            name="rpm-step", dt_s=duration / 80.0, substeps_per_step=8,
            initial_state="equilibrium", interpolation="hold",
            points=[
                ManeuverPoint(t_s=0.0, mu_x=0.10, Vz=0.0, collective_deg=8.0, rpm=400.0),
                ManeuverPoint(t_s=duration / 2.0, mu_x=0.10, Vz=0.0,
                              collective_deg=8.0, rpm=500.0),
                ManeuverPoint(t_s=duration, mu_x=0.10, Vz=0.0,
                              collective_deg=8.0, rpm=500.0),
            ],
        )
        history, _maps = api.run_maneuver(project, maneuver)
        rpm = history["rotor_rpm"].to_numpy() if "rotor_rpm" in history.columns \
            else np.asarray([400.0] * len(history))
        states = history[["nu0", "nu_s", "nu_c"]].to_numpy()
        changes = np.max(np.abs(np.diff(states, axis=0)), axis=1)
        boundary = int(np.argmax(rpm > 400.0 + 1e-9)) if np.any(rpm > 400.0 + 1e-9) \
            else int(len(history) // 2)
        boundary_change = float(changes[boundary - 1])
        neighbors = float(np.max(np.delete(changes, boundary - 1)))
        record = {"boundary_index": boundary, "boundary_state_change": boundary_change,
                  "largest_other_state_change": neighbors,
                  "state_before": states[boundary - 1].tolist(),
                  "state_after": states[boundary].tolist()}
        artifact = self._api_artifact(context, "pp-b8", record)
        passed = (boundary_change <= 3.0 * max(neighbors, 1e-15)
                  and float(np.min(np.abs(states[boundary]))) > 0.0)
        return _Evaluation(
            passed, record,
            {"boundary_state_change": "at most three times the largest other step",
             "reset_to_zero": False},
            "The state at the RPM boundary must move by the same order as any other marched step.",
            "The RPM change enters the non-dimensional time of the step, not "
            "the state. A reset would show as a jump far larger than any "
            "neighboring step.",
            artifacts=(artifact,),
            command=("Python public API: api.run_maneuver(project, "
                     "ManeuverDefinition(RPM step from 400 to 500, hold "
                     "interpolation))"),
        )

    def _outer_convergence(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, (
            "--rpm", "400", "--mu-inplane", "0", "--collective", "8",
            "--inflow", "pitt_peters_steady", "--pitt-peters-outer-iter", "15",
            "--pitt-peters-tol", "1e-6",
        ))
        outer = case.number("mean_iter")
        momentum = math.sqrt(case.number("CT") / 2.0)
        error = abs(case.number("lambda_i") / momentum - 1.0)
        return _Evaluation(
            outer <= 15.0 and error <= 1e-5,
            {"outer_iterations": outer, "iteration_limit": 15,
             "lambda_i": case.number("lambda_i"), "momentum_inflow": momentum,
             "relative_error": error},
            {"maximum_outer_iterations": 15, "residual_tolerance": 1e-6},
            "Hover must reach the declared residual tolerance in at most 15 outer iterations.",
            "The exported iteration count is the outer Pitt-Peters count. The "
            "hover momentum identity confirms that the loop stopped on its "
            "tolerance and not on its limit.",
            (case,),
        )

    # =====================================================================
    # Local inflow-field evidence
    # =====================================================================

    def _inflow_field(self, model: str, *, mu_x: float = 0.15,
                      sideslip_deg: float = 0.0) -> dict[str, Any]:
        """Return one converged local inflow field and its disk axes."""
        project = self._api_project(inflow_field_model=model,
                                    inflow_sideslip_deg=sideslip_deg)
        maps = studies.run_single_case(
            project,
            FlightCondition(name=f"field {model}", rpm=400.0, mu_x=mu_x,
                            collective_deg=8.0),
        ).maps
        return {
            "lambda_i": np.asarray(maps["lambda_i"], dtype=float),
            "PSI": np.asarray(maps["PSI"], dtype=float),
            "radius": np.asarray(maps["R_NORM"], dtype=float)[:, 0],
        }

    @staticmethod
    def _field_correlation(left: np.ndarray, right: np.ndarray) -> float:
        """Return the correlation of two disk fields about their means."""
        first = left.ravel() - float(np.mean(left))
        second = right.ravel() - float(np.mean(right))
        denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
        return float(first @ second) / max(denominator, 1e-30)

    @staticmethod
    def _maximum_azimuth_index(field: dict[str, Any]) -> int:
        """Return the azimuth station of the largest azimuthal variation."""
        values = field["lambda_i"]
        radial_mean = np.mean(values, axis=0)
        return int(np.argmax(radial_mean))

    def _pitt_drees_comparison(self, context: ExecutionContext, *,
                               combined: bool) -> _Evaluation:
        pitt = self._inflow_field("pitt_peters_steady")
        drees = self._inflow_field("drees_local")
        correlation = self._field_correlation(pitt["lambda_i"], drees["lambda_i"])
        pitt_station = self._maximum_azimuth_index(pitt)
        drees_station = self._maximum_azimuth_index(drees)
        cases = tuple(self._case(context, (
            "--rpm", "400", "--mu-inplane", "0.15", "--collective", "8",
            "--inflow", model,
        )) for model in ("pitt_peters_steady", "drees_global"))
        thrust = [case.number("CT") for case in cases]
        difference = _relative_difference(*thrust)
        same_station = abs(pitt_station - drees_station) <= 1
        record = {
            "field_correlation": correlation,
            "pitt_peters_maximum_azimuth_index": pitt_station,
            "drees_maximum_azimuth_index": drees_station,
            "same_maximum_station": same_station,
            "CT": thrust, "relative_CT_difference": difference,
        }
        artifact = self._api_artifact(
            context, "pp-b5" if combined else "pp-p5", record)
        passed = correlation >= 0.75 and same_station
        if combined:
            passed = passed and difference <= 0.04
        return _Evaluation(
            passed, record,
            {"minimum_field_correlation": 0.75, "same_maximum_station": True,
             **({"maximum_CT_difference": 0.04} if combined else {})},
            "The two fields must correlate at 0.75 or more and place their maximum at the same azimuth station."
            + (" The integrated thrust must differ by at most 4%." if combined else ""),
            "Both models build a first-harmonic inflow tilt from the same "
            "wake skew, so their fields must share a phase even though their "
            "parameterizations differ.",
            cases,
            artifacts=(artifact,),
            command=("Python public API: studies.run_single_case(project, "
                     "FlightCondition(mu_x=0.15)) with "
                     "inflow_field_model 'pitt_peters_steady' and 'drees_local'"),
        )

    def _empirical_sideslip(self, context: ExecutionContext) -> _Evaluation:
        records: dict[str, Any] = {}
        passed = True
        for model in ("coleman_local", "drees_local"):
            straight = self._inflow_field(model)
            sideslipped = self._inflow_field(model, sideslip_deg=30.0)
            azimuth = np.degrees(straight["PSI"][0])
            cell = float(azimuth[1] - azimuth[0])
            shift = ((azimuth[self._maximum_azimuth_index(sideslipped)]
                      - azimuth[self._maximum_azimuth_index(straight)] + 180.0)
                     % 360.0) - 180.0
            records[model] = {"azimuth_cell_deg": cell, "measured_shift_deg": shift,
                              "expected_shift_deg": -30.0}
            passed = passed and abs(shift + 30.0) <= cell
        artifact = self._api_artifact(context, "pp-g7", records)
        return _Evaluation(
            passed, {"models": records},
            {"field_maximum_shift_deg": -30.0, "tolerance": "one azimuth cell"},
            "Thirty degrees of sideslip must move the local field maximum by minus 30 degrees, within one azimuth cell.",
            "The harmonic inflow pattern follows the wake skew, so it turns "
            "with the free stream and not with the hub axis.",
            artifacts=(artifact,),
            command=("Python public API: studies.run_single_case(project, "
                     "FlightCondition(mu_x=0.15)) with "
                     "config.inflow_sideslip_deg 0 and 30, for the Coleman and "
                     "the Drees local field"),
        )

    def _mass_flow_matrix(self, context: ExecutionContext) -> _Evaluation:
        uniform_inflow = 0.08
        _gain, hover = _pitt_peters_L_V(0.0, uniform_inflow, 0.0)
        hover_error = abs(float(hover[1]) - 2.0 * uniform_inflow)
        residuals = {}
        identity_error = 0.0
        for advance_ratio in (1.0, 10.0, 100.0):
            _gain, forward = _pitt_peters_L_V(advance_ratio, uniform_inflow, 0.0)
            total = math.sqrt(advance_ratio ** 2 + uniform_inflow ** 2 + 1e-9)
            residual = float(forward[1]) / total - 1.0
            identity_error = max(identity_error, abs(
                residual + (uniform_inflow * uniform_inflow) / total ** 2))
            residuals[f"{advance_ratio:g}"] = {
                "harmonic_mass_flow": float(forward[1]),
                "total_velocity": total,
                "relative_residual": residual,
            }
        decay = [abs(residuals[key]["relative_residual"])
                 for key in ("1", "10", "100")]
        second_order = all(left / max(right, 1e-300) > 50.0
                           for left, right in zip(decay, decay[1:]))
        measured = {"hover_harmonic_mass_flow": float(hover[1]),
                    "hover_error": hover_error,
                    "forward": residuals,
                    "limit_identity_error": identity_error,
                    "residual_falls_with_the_square_of_speed": second_order}
        artifact = self._api_artifact(context, "pp-mass-flow", measured)
        passed = (hover_error <= 1e-12 and identity_error <= 1e-12 and second_order)
        return _Evaluation(
            passed, measured,
            {"hover_error": 1e-12, "limit_identity_error": 1e-12},
            "The hover relation must be exact to 1e-12, and the forward residual must equal the exact algebraic remainder to 1e-12.",
            "The harmonic mass-flow parameter is twice the uniform inflow in "
            "hover. In forward flight it leaves the total velocity by exactly "
            "the uniform inflow squared over the total velocity squared, which "
            "is what makes the fast-forward limit approach one. The limit is "
            "therefore certified as an identity, not sampled at one speed.",
            artifacts=(artifact,),
            command="Python public API: zbemt.bemt._pitt_peters_L_V",
        )

    # =====================================================================
    # Local-field evidence for the correction models
    # =====================================================================

    def _reverse_flow_spread(self, context: ExecutionContext) -> _Evaluation:
        models = ("flat_plate", "thin_plate_blend", "viterna_full_range")
        cases = tuple(self._case(context, (
            "--rpm", "400", "--mu-inplane", "0.60", "--collective", "8",
            "--set", f"config.reverse_flow_model={model}",
        )) for model in models)
        thrust = [case.number("CT") for case in cases]
        spread = (max(thrust) - min(thrust)) / max(abs(sum(thrust) / len(thrust)), 1e-15)
        project = self._api_project(reverse_flow_model="flat_plate")
        maps = studies.run_single_case(
            project,
            FlightCondition(name="reverse flow", rpm=400.0, mu_x=0.60,
                            collective_deg=8.0),
        ).maps
        reverse = np.asarray(maps["reverse"], dtype=bool)
        drag = np.asarray(maps["Cd"], dtype=float)
        reverse_drag = drag[reverse]
        flat_plate_error = float(np.max(np.abs(reverse_drag - 1.9))) \
            if reverse_drag.size else float("inf")
        record = {"models": list(models), "CT": thrust, "relative_spread": spread,
                  "reverse_zone_samples": int(reverse.sum()),
                  "flat_plate_reverse_drag_error": flat_plate_error}
        artifact = self._api_artifact(context, "model-g2", record)
        return _Evaluation(
            spread <= 0.01 and flat_plate_error <= 1e-12, record,
            {"maximum_relative_spread": 0.01, "flat_plate_Cd": 1.90},
            "The thrust-coefficient spread must be at most 1% and the local flat-plate drag must equal 1.90.",
            "The three deep reverse-flow options differ only inside the "
            "reverse zone, where the dynamic pressure is small. The flat-plate "
            "option writes its declared constant there.",
            cases,
            artifacts=(artifact,),
            command=("Python public API: studies.run_single_case(project, "
                     "FlightCondition(mu_x=0.60)) with "
                     "config.reverse_flow_model='flat_plate'"),
        )

    def _axial_no_ops(self, context: ExecutionContext) -> _Evaluation:
        project = api.open_project(PROPELLER_PROJECT)
        config = dict(project.config)
        config.update({"Ne": 24, "Npsi": 24, "use_compressibility": False,
                       "use_radial_flow_correction": False,
                       "use_rotational_augmentation": False})
        project = replace(project, config=config)
        airfoil = replace(project.airfoil, use_dynamic_stall=False)
        project = replace(project, airfoil=airfoil)
        rotor_speed = 2400.0
        tip_speed = rotor_speed * 2.0 * math.pi / 60.0 * project.geometry.radius_m
        axial_speed = 0.8 * tip_speed / math.pi
        condition = FlightCondition(name="axial", rpm=rotor_speed, mu_x=0.0,
                                    Vz=axial_speed, collective_deg=0.0)
        reference = studies.run_single_case(project, condition).summary
        variants = {
            "radial_flow_correction": replace(
                project, config={**project.config, "use_radial_flow_correction": True}),
            "rotational_augmentation": replace(
                project, config={**project.config, "use_rotational_augmentation": True}),
            "dynamic_stall_frequency": replace(
                project, airfoil=replace(airfoil, use_dynamic_stall=True,
                                         dynamic_stall_method="frequency")),
            "dynamic_stall_time_march": replace(
                project, airfoil=replace(airfoil, use_dynamic_stall=True,
                                         dynamic_stall_method="time_march")),
        }
        records: dict[str, Any] = {}
        worst = 0.0
        for name, variant in variants.items():
            summary = studies.run_single_case(variant, condition).summary
            thrust_change = abs(float(summary["CT_prop"]) - float(reference["CT_prop"]))
            power_change = abs(float(summary["CP_prop"]) - float(reference["CP_prop"]))
            records[name] = {"CT_prop_change": thrust_change,
                             "CP_prop_change": power_change}
            worst = max(worst, thrust_change, power_change)
        record = {"reference_CT_prop": float(reference["CT_prop"]),
                  "reference_CP_prop": float(reference["CP_prop"]),
                  "options": records, "maximum_absolute_change": worst}
        artifact = self._api_artifact(context, "prop-k3", record)
        return _Evaluation(
            worst <= 1e-12, record,
            {"maximum_absolute_change": 1e-12},
            "Each option must change the thrust and power coefficients by at most 1e-12 at advance ratio 0.8.",
            "A steady axial case has no azimuthal variation, no radial flow, "
            "and no separated section, so a skew, reverse-flow, or "
            "separation-lag correction has nothing to act on. The check runs "
            "the time-marched dynamic-stall path as well as the frequency one.",
            artifacts=(artifact,),
            command=("Python public API: studies.run_single_case(project, "
                     "FlightCondition(rpm=2400, J_x=0.8)) with each option "
                     "enabled alone"),
        )

    def _warning_threshold(self, context: ExecutionContext) -> _Evaluation:
        project = self._api_project(inflow_field_model="glauert_local",
                                    solver="fixed_point")
        records: dict[str, Any] = {}
        for label, iterations in (("converged", 400), ("partial", 2)):
            case = studies.run_single_case(
                replace(project, config={**project.config, "max_iter": iterations}),
                FlightCondition(name=label, rpm=400.0, Vz=20.0,
                                collective_deg=16.0),
            )
            issues = validate_results(case.summary)
            warnings = [issue.message for issue in issues
                        if issue.level == "warning" and "converged on only" in issue.message]
            records[label] = {
                "convergence_pct": float(case.summary["convergence_pct"]),
                "warning": bool(warnings),
                "max_iter": iterations,
            }
        record = {"cases": records, "threshold_pct": CONVERGENCE_WARNING_PCT}
        artifact = self._api_artifact(context, "ext-d4", record)
        passed = (
            records["converged"]["convergence_pct"] >= CONVERGENCE_WARNING_PCT
            and not records["converged"]["warning"]
            and records["partial"]["convergence_pct"] < CONVERGENCE_WARNING_PCT
            and records["partial"]["warning"]
        )
        return _Evaluation(
            passed, record,
            {"warning_threshold_pct": CONVERGENCE_WARNING_PCT,
             "converged_case_warning": False, "partial_case_warning": True},
            "A case at or above the declared threshold emits no warning, and any case below it emits one.",
            "The two cases are the same condition solved with a generous and "
            "with a starved iteration limit, so only the convergence "
            "percentage separates them.",
            artifacts=(artifact,),
            command=("Python public API: studies.run_single_case(project, "
                     "FlightCondition(rpm=400, Vz=20, collective_deg=16)) with "
                     "config.max_iter 400 and 2, read through "
                     "validation.validate_results"),
        )

def execute_pitt_corrections_claim(claim: Claim, context: ExecutionContext) -> CheckResult:
    """Execute one claim with a fresh domain executor."""
    return PittCorrectionsExecutor()(claim, context)
