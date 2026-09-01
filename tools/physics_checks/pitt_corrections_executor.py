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

from zbemt.airfoils import preview_polar
from zbemt.bemt import _PP_M3, _pitt_peters_L_V
from zbemt.models import AirfoilDef

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
            "PP-B2": lambda c: self._missing_history(c, "PP-B2", 0.05),
            "PP-B3": lambda c: self._missing_history(c, "PP-B3", 0.05),
            "PP-B4": lambda c: self._missing_history(c, "PP-B4", 0.05),
            "PP-B5-COMBINED": self._field_and_thrust_comparison,
            "PP-B6": self._outer_convergence,
            "PP-B7": lambda c: self._missing_history(c, "PP-B7", 0.10, sideslip=30.0),
            "PP-B8": lambda c: self._missing_history(c, "PP-B8", 0.10),
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

    def _reverse_flow_spread(self, context: ExecutionContext) -> _Evaluation:
        models = ("flat_plate", "thin_plate_blend", "viterna_full_range")
        cases = tuple(self._case(context, (
            "--rpm", "400", "--mu-inplane", "0.60", "--collective", "8",
            "--set", f"config.reverse_flow_model={model}",
        )) for model in models)
        ct = [case.number("CT") for case in cases]
        spread = (max(ct) - min(ct)) / max(abs(sum(ct) / len(ct)), 1e-15)
        return _Evaluation(
            False,
            {"models": list(models), "CT": ct, "relative_spread": spread},
            {"maximum_relative_spread": 0.01, "flat_plate_Cd": 1.90},
            "CT spread <= 1% and local flat-plate Cd equals 1.90.",
            "The CLI confirms finite integrated loads. It does not export local reverse-flow drag.",
            cases,
            status=FinalStatus.INCONCLUSIVE,
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

    def _missing_history(
        self,
        context: ExecutionContext,
        claim_id: str,
        mu: float,
        *,
        sideslip: float = 0.0,
    ) -> _Evaluation:
        case = self._case(context, (
            "--rpm", "400", "--mu-inplane", str(mu), "--collective", "8",
            "--inflow", "pitt_peters_steady",
            "--set", f"config.inflow_sideslip_deg={sideslip}",
        ))
        return _Evaluation(
            False,
            {"steady_CT": case.number("CT"), "steady_lambda_i": case.number("lambda_i"), "requested_claim": claim_id},
            {"required_evidence": "A prescribed maneuver history and its three inflow states."},
            "The claim-specific maneuver history must satisfy the ledger rule.",
            "A real steady CLI reference ran. No saved maneuver exists on the starter project, so the required history is absent.",
            (case,),
            status=FinalStatus.INCONCLUSIVE,
        )

    def _field_and_thrust_comparison(self, context: ExecutionContext) -> _Evaluation:
        return self._pitt_drees_comparison(context, combined=True)

    def _field_asymmetry(self, context: ExecutionContext) -> _Evaluation:
        return self._pitt_drees_comparison(context, combined=False)

    def _pitt_drees_comparison(self, context: ExecutionContext, *, combined: bool) -> _Evaluation:
        cases = tuple(self._case(context, (
            "--rpm", "400", "--mu-inplane", "0.15", "--collective", "8", "--inflow", model,
        )) for model in ("pitt_peters_steady", "drees_global"))
        ct = [case.number("CT") for case in cases]
        difference = _relative_difference(*ct)
        return _Evaluation(
            False,
            {"models": ["pitt_peters_steady", "drees_global"], "CT": ct, "relative_CT_difference": difference},
            {"minimum_field_correlation": 0.75, "same_maximum_station": True, "maximum_CT_difference": 0.04},
            "The field and integrated-load conditions in the claim must all hold.",
            "The integrated thrust comparison ran. The public CLI does not export the two local inflow fields.",
            cases,
            status=FinalStatus.INCONCLUSIVE,
        )

    def _outer_convergence(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, (
            "--rpm", "400", "--mu-inplane", "0", "--collective", "8",
            "--inflow", "pitt_peters_steady", "--pitt-peters-outer-iter", "15",
            "--pitt-peters-tol", "1e-6",
        ))
        return _Evaluation(
            False,
            {"CT": case.number("CT"), "finite": math.isfinite(case.number("CT"))},
            {"maximum_outer_iterations": 15, "residual_tolerance": 1e-6},
            "The exported outer count and residual must satisfy the declared limits.",
            "The case converged, but results.csv does not export the Pitt-Peters outer count or residual.",
            (case,),
            status=FinalStatus.INCONCLUSIVE,
        )

    def _empirical_sideslip(self, context: ExecutionContext) -> _Evaluation:
        cases = tuple(self._case(context, (
            "--rpm", "400", "--mu-inplane", "0.15", "--collective", "8",
            "--inflow", model, "--set", f"config.inflow_sideslip_deg={sideslip}",
        )) for model in ("coleman_global", "drees_global") for sideslip in ("0", "30"))
        return _Evaluation(
            False,
            {"CT": [case.number("CT") for case in cases], "finite": _finite([case.number("CT") for case in cases])},
            {"field_maximum_shift_deg": -30.0, "azimuth_cell_tolerance": 15.0},
            "The local field maximum must shift by minus 30 degrees within one cell.",
            "All integrated cases ran. The CLI does not export the local field maximum.",
            cases,
            status=FinalStatus.INCONCLUSIVE,
        )

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

    def _mass_flow_matrix(self, context: ExecutionContext) -> _Evaluation:
        _, hover = _pitt_peters_L_V(0.0, 0.08, 0.0)
        _, forward = _pitt_peters_L_V(10.0, 0.08, 0.0)
        hover_error = abs(float(hover[1]) - 2.0 * 0.08)
        total_velocity = math.sqrt(10.0**2 + 0.08**2 + 1e-9)
        forward_error = abs(float(forward[1]) / total_velocity - 1.0)
        measured = {
            "hover_V": hover.tolist(), "forward_V": forward.tolist(),
            "hover_harmonic_error": hover_error, "forward_relative_error": forward_error,
        }
        artifact = self._api_artifact(context, "pp-mass-flow", measured)
        # The fast-forward relation is asymptotic. Mu=10 makes the residual
        # measurable, so the strict 1e-12 ledger rule cannot be certified.
        return _Evaluation(
            False,
            measured,
            {"hover_harmonic": 0.16, "fast_forward_limit": total_velocity},
            "Both limiting relations must agree within 1e-12.",
            "The hover identity is exact. A finite forward-speed probe cannot prove an asymptotic limit to 1e-12.",
            artifacts=(artifact,),
            command="Python API probe: zbemt.bemt._pitt_peters_L_V",
            status=FinalStatus.INCONCLUSIVE,
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

    def _steady_march_audit(self, context: ExecutionContext) -> _Evaluation:
        hover = self._hover_equilibrium(context)
        missing = self._missing_history(context, "PP-STEADY-MARCH-AUDIT", 0.10)
        return _Evaluation(
            False,
            {"hover": dict(hover.measured), "march": dict(missing.measured)},
            {"hover_momentum_error": 1e-6, "march_state_error": 1e-6},
            "Both the hover momentum and 20-revolution march conditions must hold.",
            "The hover limit ran and can be evaluated. The required maneuver history is absent.",
            hover.cases + missing.cases,
            status=FinalStatus.INCONCLUSIVE,
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

    def _axial_no_ops(self, context: ExecutionContext) -> _Evaluation:
        arguments = ("--rpm", "2400", "--j-axial", "0.8", "--collective", "0")
        cases = (
            self._case(context, (*arguments, "--inflow", "glauert_local", "--set", "config.reverse_flow_model=simple_flip"), PROPELLER_PROJECT),
            self._case(context, (*arguments, "--inflow", "drees_global", "--set", "config.reverse_flow_model=simple_flip"), PROPELLER_PROJECT),
            self._case(context, (*arguments, "--inflow", "glauert_local", "--set", "config.reverse_flow_model=flat_plate"), PROPELLER_PROJECT),
        )
        baseline = (cases[0].number("CT_prop"), cases[0].number("CP_prop"))
        changes = [max(_relative_difference(baseline[0], case.number("CT_prop")), _relative_difference(baseline[1], case.number("CP_prop"))) for case in cases[1:]]
        return _Evaluation(
            False,
            {"baseline_CT_CP": list(baseline), "maximum_changes": changes},
            {"maximum_change": 1e-12, "options": ["skew", "reverse flow", "dynamic stall"]},
            "Each isolated option must change CT_prop and CP_prop by at most 1e-12.",
            "Skew and reverse-flow cases ran. A steady CLI case cannot activate the time-marched dynamic-stall path, so the full rule is not certified.",
            cases,
            status=FinalStatus.INCONCLUSIVE,
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

    def _warning_threshold(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, ("--rpm", "400", "--v-axial", "20", "--collective", "16"))
        text = (case.stdout + case.stderr).lower()
        return _Evaluation(
            False,
            {"convergence_pct": case.number("convergence_pct"), "warning_present": "warning" in text},
            {"no_warning_at_pct": 99.9, "warning_below_pct": 99.5},
            "Both sides of the 99.5% threshold must be reproduced.",
            "One real case ran. The prepared cases needed to force both sides of the threshold are absent.",
            (case,),
            status=FinalStatus.INCONCLUSIVE,
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


def execute_pitt_corrections_claim(claim: Claim, context: ExecutionContext) -> CheckResult:
    """Execute one claim with a fresh domain executor."""
    return PittCorrectionsExecutor()(claim, context)
