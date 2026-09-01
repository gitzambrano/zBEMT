"""Confirm propeller claims through the public CLI and independent rules."""
from __future__ import annotations

import csv
import math
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .cli_helper import run_cli_in_project_copy
from .models import CheckResult, Claim, CliRunResult, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = ROOT / "projects" / "starter_propeller"
BASE = ("--rpm", "2400", "--j-axial", "0.6", "--collective", "0")


class _CaseFailure(RuntimeError):
    """Report a public CLI failure to the claim result builder."""


@dataclass(frozen=True)
class _Case:
    values: Mapping[str, float | str]
    command: str
    artifacts: tuple[str, ...]

    def number(self, name: str) -> float:
        """Return one required numeric result value."""
        value = self.values.get(name)
        if not isinstance(value, (int, float)):
            raise _CaseFailure(f"The CLI result does not contain numeric field '{name}'.")
        return float(value)


@dataclass(frozen=True)
class _Evaluation:
    passed: bool
    measured: Mapping[str, Any]
    expected: Mapping[str, Any]
    tolerance: str
    notes: str
    cases: tuple[_Case, ...]
    status: FinalStatus | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_error(actual: float, expected: float) -> float:
    scale = max(abs(expected), 1e-15)
    return abs(actual - expected) / scale


def _relative_spread(values: Sequence[float]) -> float:
    scale = max(max(abs(value) for value in values), 1e-15)
    return (max(values) - min(values)) / scale


def _nondecreasing(values: Sequence[float], tolerance: float = 0.0) -> bool:
    return all(right + tolerance >= left for left, right in zip(values, values[1:]))


def _nonincreasing(values: Sequence[float], tolerance: float = 0.0) -> bool:
    return all(right <= left + tolerance for left, right in zip(values, values[1:]))


class PropellerExecutor:
    """Evaluate every propeller claim and cache identical public CLI runs."""

    def __init__(
        self,
        *,
        cli_runner: Callable[[Path, Sequence[str], Path], CliRunResult] = run_cli_in_project_copy,
        source_project: Path = DEFAULT_PROJECT,
    ) -> None:
        self._cli_runner = cli_runner
        self._source_project = Path(source_project)
        self._cache: dict[tuple[str, tuple[str, ...]], _Case] = {}
        self._evaluators = {
            "PROP-C13": self._induced_power_bookkeeping,
            "PROP-C14": self._shaft_power_identity,
            "PROP-F5": self._gentle_twist_hover,
            "PROP-G8": self._oblique_reference,
            "PROP-GEOMETRY-SUMMARY": self._geometry_summary,
            "PROP-K1": self._induced_power_factor,
            "PROP-K4": self._azimuthal_convergence,
            "PROP-K6": self._profile_drag_scaling,
            "PROP-K7": self._reverse_thrust,
            "PROP-K9": self._extreme_collective,
            "PROP-MOMENTUM-SUMMARY": self._momentum_summary,
            "PROP-N2": self._borderline_convergence,
            "PROP-N3": self._starter_reverse_limit,
            "PROP-POWER-SUMMARY": self._power_summary,
            "PROP-STATIC-SUMMARY": self._static_summary,
            "PROP-T1": self._coefficient_identities,
            "PROP-T10": self._mesh_convergence,
            "PROP-T2A": self._momentum_efficiency_bound,
            "PROP-T2B": self._momentum_induced_velocity,
            "PROP-T3": self._static_figure_of_merit,
            "PROP-T4": self._curve_shapes,
            "PROP-T5A": self._prandtl_ordering,
            "PROP-T5C": self._solver_agreement,
            "PROP-T6A": self._rpm_similarity,
            "PROP-T6C": self._density_similarity,
            "PROP-T7": self._crossflow_symmetry,
            "PROP-T8": self._windmill_regimes,
            "PROP-T9A": self._blade_count_scaling,
            "PROP-T9B": self._radius_scaling,
        }

    def __call__(self, claim: Claim, context: ExecutionContext) -> CheckResult:
        """Run one claim and return a complete result record."""
        started_at = _utc_now()
        try:
            evaluator = self._evaluators[claim.claim_id]
            evaluation = evaluator(context)
            status = evaluation.status
            if status is None:
                status = (
                    FinalStatus.CONFIRMED_CORRECT
                    if evaluation.passed else FinalStatus.CONFIRMED_DEFECT
                )
            commands = tuple(dict.fromkeys(case.command for case in evaluation.cases))
            artifacts = tuple(dict.fromkeys(
                artifact for case in evaluation.cases for artifact in case.artifacts
            ))
            return CheckResult(
                claim_id=claim.claim_id,
                final_status=status,
                measured_data=evaluation.measured,
                expected_data=evaluation.expected,
                tolerance_rule=evaluation.tolerance,
                command="\n".join(commands),
                artifacts=artifacts,
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
                expected_data={"public_cli": "A successful result CSV with required fields."},
                tolerance_rule=claim.acceptance_rule,
                command=claim.cli_route,
                artifacts=(),
                notes=f"The propeller executor could not complete: {exc}",
                started_at=started_at,
                ended_at=_utc_now(),
                commit=context.commit,
                environment=context.environment,
            )

    def _case(self, context: ExecutionContext, arguments: Sequence[str]) -> _Case:
        normalized = tuple(str(argument) for argument in arguments)
        cache_key = (str(Path(context.output_directory).resolve()), normalized)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        work_root = Path(context.output_directory) / "propeller_cli_work"
        work_root.mkdir(parents=True, exist_ok=True)
        working_directory = Path(tempfile.mkdtemp(prefix="case_", dir=work_root))
        run = self._cli_runner(self._source_project, normalized, working_directory)
        if run.exit_code != 0:
            detail = run.stderr.strip() or run.stdout.strip() or "no CLI diagnostic"
            raise _CaseFailure(f"The public CLI exited with {run.exit_code}: {detail}")
        result_paths = [path for path in run.generated_csv_paths if path.name == "results.csv"]
        if not result_paths:
            raise _CaseFailure("The public CLI did not generate results.csv.")
        result_path = result_paths[-1]
        with result_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise _CaseFailure("The public CLI generated an empty results.csv.")
        values: dict[str, float | str] = {}
        for name, raw_value in rows[-1].items():
            try:
                values[name] = float(raw_value)
            except (TypeError, ValueError):
                values[name] = raw_value
        case = _Case(values, run.command, tuple(str(path) for path in run.generated_csv_paths))
        self._cache[cache_key] = case
        return case

    def _cases(self, context: ExecutionContext, argument_sets: Sequence[Sequence[str]]) -> tuple[_Case, ...]:
        return tuple(self._case(context, arguments) for arguments in argument_sets)

    def _coefficient_identities(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, BASE)
        density = case.number("cfg_rho_used")
        shaft_rate = case.number("rotor_rpm") / 60.0
        diameter = case.number("rotor_D")
        thrust_expected = case.number("Thrust") / (density * shaft_rate**2 * diameter**4)
        power_expected = case.number("Power") / (density * shaft_rate**3 * diameter**5)
        efficiency_expected = case.number("J_z") * thrust_expected / power_expected
        errors = {
            "CT_prop_relative_error": _relative_error(case.number("CT_prop"), thrust_expected),
            "CP_prop_relative_error": _relative_error(case.number("CP_prop"), power_expected),
            "eta_prop_relative_error": _relative_error(case.number("eta_prop"), efficiency_expected),
        }
        return _Evaluation(
            max(errors.values()) <= 1e-10,
            errors,
            {"maximum_relative_error": 1e-10},
            "Each coefficient identity must agree within 1e-10 relative error.",
            "The expected coefficients use dimensional outputs and independent definitions.",
            (case,),
        )

    def _shaft_power_identity(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, BASE)
        expected = case.number("Torque") * case.number("rotor_Omega")
        error = _relative_error(case.number("Power"), expected)
        return _Evaluation(
            error <= 1e-12,
            {"relative_error": error, "power_W": case.number("Power")},
            {"power_W": expected},
            "Power must equal torque times angular speed within 1e-12 relative error.",
            "This check uses the mechanical power identity.",
            (case,),
        )

    def _induced_power_bookkeeping(self, context: ExecutionContext) -> _Evaluation:
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", value, "--collective", "0")
            for value in ("0", "0.4", "0.8")
        ])
        ratios = [
            case.number("Power_i") /
            (case.number("Thrust") * (case.number("Vz") + case.number("Vi")))
            for case in cases
        ]
        return _Evaluation(
            all(0.95 <= ratio <= 1.10 for ratio in ratios),
            {"induced_power_ratios": ratios},
            {"ratio_range": [0.95, 1.10]},
            "P_i/[T(V+v_i)] must stay from 0.95 to 1.10 to allow wake-swirl power.",
            "Actuator-disk induced power is T(V+v_i). Finite swirl can add a small excess.",
            cases,
        )

    def _gentle_twist_hover(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, (
            "--rpm", "2400", "--v-axial", "0", "--collective", "0",
            "--geom-preset", "tapered", "--geom-chord", "0.147",
            "--geom-taper-ratio", "0.51", "--geom-twist-root", "20",
            "--geom-twist-tip", "8",
        ))
        ct_internal = 4.0 * case.number("CT_prop") / math.pi**3
        ideal = math.sqrt(ct_internal / 2.0) * case.number("rotor_Omega") * case.number("rotor_R")
        ratio = case.number("Vi") / ideal
        return _Evaluation(
            1.05 <= ratio <= 1.15,
            {"induced_velocity_ratio": ratio, "Vi_m_s": case.number("Vi")},
            {"ratio_range": [1.05, 1.15], "ideal_Vi_m_s": ideal},
            "The finite-blade induced velocity must be 1.05 to 1.15 times the ideal hover value.",
            "Uniform momentum theory supplies the ideal value for the same thrust coefficient.",
            (case,),
        )

    def _oblique_reference(self, context: ExecutionContext) -> _Evaluation:
        cases = self._cases(context, [
            ("--rpm", "600", "--v-axial", "7.5", "--v-inplane", cross,
             "--collective", "0", "--set", "config.use_compressibility=false")
            for cross in ("0", "30", "60")
        ])
        coefficients = [case.number("CT_prop") for case in cases]
        observed = _nondecreasing(coefficients)
        return _Evaluation(
            observed,
            {"cross_speed_m_s": [0.0, 30.0, 60.0], "CT_prop": coefficients},
            {"reference_observation": "CT_prop increases across the scaled subsonic sweep."},
            "Record the trend only. No independent literature tolerance is available.",
            "The retained report calls this trend plausible but does not validate it independently.",
            cases,
            FinalStatus.INCONCLUSIVE,
        )

    def _induced_power_factor(self, context: ExecutionContext) -> _Evaluation:
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", f"{value:.1f}", "--collective", "0")
            for value in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2)
        ])
        factors = []
        for case in cases:
            density = case.number("cfg_rho_used")
            area = math.pi * case.number("rotor_R")**2
            velocity = case.number("Vz")
            ideal = 0.5 * (
                math.sqrt(velocity**2 + 2.0 * case.number("Thrust") / (density * area))
                - velocity
            )
            factors.append((velocity + case.number("Vi")) / (velocity + ideal))
        passed = all(1.0 <= factor <= 1.15 for factor in factors) and _nonincreasing(factors, 1e-6)
        return _Evaluation(
            passed,
            {"kappa": factors},
            {"range": [1.0, 1.15], "trend": "nonincreasing with J"},
            "Kappa must stay from 1.0 to 1.15 and decrease as the propeller unloads.",
            "Momentum theory defines the minimum induced power at each measured thrust.",
            cases,
        )

    def _azimuthal_convergence(self, context: ExecutionContext) -> _Evaluation:
        arguments = []
        for cross in ("0", "20"):
            for count in ("12", "36", "72"):
                arguments.append((
                    "--rpm", "2400", "--v-axial", "30", "--v-inplane", cross,
                    "--collective", "0", "--set", f"config.Npsi={count}",
                ))
        cases = self._cases(context, arguments)
        axial_ct = [case.number("CT_prop") for case in cases[:3]]
        cross_ct = [case.number("CT_prop") for case in cases[3:]]
        cross_force = [case.number("H") for case in cases[3:]]
        spreads = {
            "axial_CT_relative_spread": _relative_spread(axial_ct),
            "cross_CT_relative_spread": _relative_spread(cross_ct),
            "cross_H_relative_spread": _relative_spread(cross_force),
        }
        return _Evaluation(
            max(spreads.values()) <= 1e-4,
            spreads,
            {"maximum_relative_spread": 1e-4},
            "Npsi values 12, 36, and 72 must agree within 1e-4 relative spread.",
            "An azimuth-converged axial or first-harmonic solution is independent of Npsi.",
            cases,
        )

    def _profile_drag_scaling(self, context: ExecutionContext) -> _Evaluation:
        cd_values = (0.004, 0.008, 0.016)
        cases = self._cases(context, [
            (*BASE, "--set", f"airfoil.cd0={value}") for value in cd_values
        ])
        profile_power = [case.number("CPp") for case in cases]
        thrust = [case.number("CT_prop") for case in cases]
        slopes = [
            (profile_power[index + 1] - profile_power[index]) /
            (cd_values[index + 1] - cd_values[index])
            for index in range(2)
        ]
        slope_spread = _relative_spread(slopes)
        return _Evaluation(
            slope_spread <= 0.02 and _nonincreasing(thrust),
            {"CPp": profile_power, "slope_relative_spread": slope_spread, "CT_prop": thrust},
            {"slope_relative_spread_max": 0.02, "CT_trend": "nonincreasing"},
            "The Cd0 contribution to CPp must be linear within 2%, and CT must not increase.",
            "Profile drag is linear in the zero-lift drag coefficient at fixed loading.",
            cases,
        )

    def _reverse_thrust(self, context: ExecutionContext) -> _Evaluation:
        collectives = (-20, -10, -5, 0, 10)
        common = (
            "--rpm", "2400", "--v-axial", "0", "--geom-preset", "tapered",
            "--geom-chord", "0.147", "--geom-taper-ratio", "0.51",
            "--geom-twist-root", "5", "--geom-twist-tip", "5",
        )
        cases = self._cases(context, [(*common, "--collective", str(value)) for value in collectives])
        thrust = [case.number("Thrust") for case in cases]
        passed = _nondecreasing(thrust) and thrust[1] < 0.0 < thrust[2]
        return _Evaluation(
            passed,
            {"collective_deg": list(collectives), "thrust_N": thrust},
            {"trend": "increasing", "zero_crossing_deg": [-10, -5]},
            "Thrust must increase with collective and cross zero between -10 and -5 degrees.",
            "A symmetric 5-degree twist removes the starter blade's large root-twist bias.",
            cases,
        )

    def _extreme_collective(self, context: ExecutionContext) -> _Evaluation:
        arguments = [
            ("--rpm", "2400", "--j-axial", j_value, "--collective", collective)
            for j_value in ("0", "1") for collective in ("25", "30", "40")
        ]
        cases = self._cases(context, arguments)
        static_ct = [case.number("CT_prop") for case in cases[:3]]
        finite = all(math.isfinite(case.number("CT_prop")) for case in cases)
        converged = all(case.number("convergence_pct") >= 99.5 for case in cases)
        return _Evaluation(
            finite and converged and _nonincreasing(static_ct),
            {"static_CT_prop": static_ct, "minimum_convergence_pct": min(case.number("convergence_pct") for case in cases)},
            {"static_trend": "nonincreasing", "minimum_convergence_pct": 99.5},
            "All cases must be finite and at least 99.5% converged. Static CT must decrease after full stall.",
            "A full-range stall model must remain finite and lose lift as pitch increases in deep stall.",
            cases,
        )

    def _borderline_convergence(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, ("--rpm", "2400", "--j-axial", "0", "--collective", "8"))
        convergence = case.number("convergence_pct")
        return _Evaluation(
            98.0 <= convergence <= 100.0,
            {"convergence_pct": convergence},
            {"range_pct": [98.0, 100.0], "historical_value_pct": 98.6},
            "The reference case must remain finite with 98% to 100% mesh convergence.",
            "This claim records a known borderline element rather than an accuracy verdict.",
            (case,),
        )

    def _starter_reverse_limit(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, ("--rpm", "2400", "--v-axial", "0", "--collective", "-20"))
        thrust = case.number("Thrust")
        return _Evaluation(
            thrust > 0.0,
            {"thrust_N": thrust},
            {"thrust_sign": "positive"},
            "The original high-twist starter blade must retain positive static thrust at -20 degrees collective.",
            "The 42-degree root twist dominates the negative collective setting.",
            (case,),
        )

    def _mesh_convergence(self, context: ExecutionContext) -> _Evaluation:
        grids = ((18, 12), (36, 24), (72, 36), (108, 48))
        cases = self._cases(context, [
            (*BASE, "--set", f"config.Ne={elements}", "--set", f"config.Npsi={azimuths}")
            for elements, azimuths in grids
        ])
        coefficients = [case.number("CT_prop") for case in cases]
        total_travel = _relative_error(coefficients[0], coefficients[-1])
        final_change = _relative_error(coefficients[-2], coefficients[-1])
        return _Evaluation(
            _nondecreasing(coefficients) and total_travel <= 0.02 and final_change <= 0.01,
            {"grids": [list(grid) for grid in grids], "CT_prop": coefficients,
             "total_relative_travel": total_travel, "final_relative_change": final_change},
            {"trend": "nondecreasing", "total_relative_travel_max": 0.02,
             "final_relative_change_max": 0.01},
            "CT must settle monotonically, move by at most 2%, and change by at most 1% on the last refinement.",
            "A consistent quadrature approaches one mesh-independent coefficient.",
            cases,
        )

    def _momentum_efficiency_bound(self, context: ExecutionContext) -> _Evaluation:
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", value, "--collective", "0")
            for value in ("0.4", "0.8", "1.2")
        ])
        margins = []
        for case in cases:
            induction_minimum = 0.5 * (-1.0 + math.sqrt(1.0 + case.number("CT_prop")))
            bound = 1.0 / (1.0 + induction_minimum)
            margins.append(bound - case.number("eta_prop"))
        return _Evaluation(
            all(margin >= -1e-10 for margin in margins),
            {"efficiency_bound_margin": margins},
            {"minimum_margin": 0.0},
            "Propeller efficiency must not exceed the actuator-disk momentum bound.",
            "The bound uses Glauert's minimum induced loss for the measured thrust coefficient.",
            cases,
        )

    def _momentum_induced_velocity(self, context: ExecutionContext) -> _Evaluation:
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", value, "--collective", "0")
            for value in ("0", "0.4", "0.8")
        ])
        ratios = []
        for case in cases:
            density = case.number("cfg_rho_used")
            area = math.pi * case.number("rotor_R")**2
            velocity = case.number("Vz")
            ideal = 0.5 * (
                math.sqrt(velocity**2 + 2.0 * case.number("Thrust") / (density * area))
                - velocity
            )
            ratios.append(case.number("Vi") / ideal)
        return _Evaluation(
            all(ratio > 1.0 for ratio in ratios),
            {"Vi_over_momentum_minimum": ratios},
            {"minimum_ratio_exclusive": 1.0},
            "The finite, non-optimally twisted blade must require more induced velocity than an ideal disk.",
            "Momentum theory supplies the uniform-inflow minimum at the measured thrust.",
            cases,
        )

    def _static_figure_of_merit(self, context: ExecutionContext) -> _Evaluation:
        case = self._case(context, ("--rpm", "2400", "--v-axial", "0", "--collective", "0"))
        value = case.number("FM")
        return _Evaluation(
            0.5 <= value <= 0.75,
            {"FM": value},
            {"literature_range": [0.5, 0.75]},
            "The static figure of merit must stay in the 0.5 to 0.75 literature range.",
            "McCormick chapter 6 gives this range for efficient fixed-pitch propellers.",
            (case,),
        )

    def _curve_shapes(self, context: ExecutionContext) -> _Evaluation:
        advance = tuple(index / 5 for index in range(9))
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", str(value), "--collective", "0")
            for value in advance
        ])
        thrust = [case.number("CT_prop") for case in cases]
        efficiency = [case.number("eta_prop") for case in cases]
        peak_index = max(range(len(efficiency)), key=efficiency.__getitem__)
        shape = (
            _nonincreasing(thrust[1:], 5e-3)
            and 0 < peak_index < len(efficiency) - 1
            and _nondecreasing(efficiency[:peak_index + 1], 1e-8)
            and _nonincreasing(efficiency[peak_index:], 1e-8)
        )
        return _Evaluation(
            shape,
            {"J": list(advance), "CT_prop": thrust, "eta_prop": efficiency,
             "eta_peak_J": advance[peak_index]},
            {"CT_trend": "nonincreasing after the static pocket", "eta_peaks": 1},
            "CT must decay after the static pocket, and efficiency must have one interior peak.",
            "Classical propeller charts show decreasing loading and one propulsive-efficiency maximum.",
            cases,
        )

    def _prandtl_ordering(self, context: ExecutionContext) -> _Evaluation:
        modes = ("off", "root", "tip", "both")
        cases = self._cases(context, [(*BASE, "--prandtl-loss-mode", mode) for mode in modes])
        coefficients = [case.number("CT_prop") for case in cases]
        passed = coefficients[0] >= coefficients[1] >= coefficients[2] >= coefficients[3]
        return _Evaluation(
            passed,
            {"modes": list(modes), "CT_prop": coefficients},
            {"ordering": "off >= root >= tip >= both"},
            "Prandtl losses must only remove lift, and tip loss must exceed root loss for this blade.",
            "The finite-blade loss factor cannot add circulation.",
            cases,
        )

    def _solver_agreement(self, context: ExecutionContext) -> _Evaluation:
        solvers = ("newton", "bisection", "fixed_point", "aitken")
        cases = self._cases(context, [(*BASE, "--solver", solver) for solver in solvers])
        coefficients = [case.number("CT_prop") for case in cases]
        spread = _relative_spread(coefficients)
        convergence = min(case.number("convergence_pct") for case in cases)
        return _Evaluation(
            spread <= 0.005 and convergence >= 99.5,
            {"solvers": list(solvers), "CT_prop": coefficients,
             "relative_spread": spread, "minimum_convergence_pct": convergence},
            {"relative_spread_max": 0.005, "minimum_convergence_pct": 99.5},
            "All converged solvers must agree within 0.5% relative CT spread.",
            "The physical fixed point is independent of the numerical root method.",
            cases,
        )

    def _rpm_similarity(self, context: ExecutionContext) -> _Evaluation:
        speeds = (1200, 2400, 3600, 4800)
        cases = self._cases(context, [
            ("--rpm", str(speed), "--j-axial", "0.6", "--collective", "0",
             "--set", "config.use_compressibility=false")
            for speed in speeds
        ])
        thrust = [case.number("CT_prop") for case in cases]
        power = [case.number("CP_prop") for case in cases]
        spread = max(_relative_spread(thrust), _relative_spread(power))
        return _Evaluation(
            spread <= 1e-10,
            {"rpm": list(speeds), "CT_prop": thrust, "CP_prop": power,
             "maximum_relative_spread": spread},
            {"maximum_relative_spread": 1e-10},
            "With compressibility disabled, CT and CP must be RPM-invariant within 1e-10.",
            "A Reynolds-independent non-dimensional BEMT system is self-similar at fixed J.",
            cases,
        )

    def _density_similarity(self, context: ExecutionContext) -> _Evaluation:
        densities = (0.8, 1.0, 1.225)
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", "0.6", "--collective", "0",
             "--set", f"config.rho={density}")
            for density in densities
        ])
        coefficients = [case.number("CT_prop") for case in cases]
        normalized_thrust = [case.number("Thrust") / density for case, density in zip(cases, densities)]
        spread = max(_relative_spread(coefficients), _relative_spread(normalized_thrust))
        return _Evaluation(
            spread <= 1e-10,
            {"rho_kg_m3": list(densities), "CT_prop": coefficients,
             "thrust_over_rho": normalized_thrust, "maximum_relative_spread": spread},
            {"maximum_relative_spread": 1e-10},
            "CT and thrust divided by density must be invariant within 1e-10.",
            "Aerodynamic force is linear in density when the coefficient solution is unchanged.",
            cases,
        )

    def _crossflow_symmetry(self, context: ExecutionContext) -> _Evaluation:
        cross_values = (-40, -20, -10, 0, 10, 20, 40)
        cases = self._cases(context, [
            ("--rpm", "2400", "--v-axial", "30", "--v-inplane", str(cross),
             "--collective", "0") for cross in cross_values
        ])
        by_cross = dict(zip(cross_values, cases))
        errors = []
        for magnitude in (10, 20, 40):
            negative = by_cross[-magnitude]
            positive = by_cross[magnitude]
            errors.extend([
                _relative_error(negative.number("Thrust"), positive.number("Thrust")),
                _relative_error(negative.number("Power"), positive.number("Power")),
                _relative_error(negative.number("H"), -positive.number("H")),
                _relative_error(negative.number("My"), -positive.number("My")),
            ])
        normal_fraction = abs(by_cross[40].number("H") / by_cross[40].number("Thrust"))
        return _Evaluation(
            max(errors) <= 1e-6 and 0.01 <= normal_fraction <= 0.20,
            {"maximum_symmetry_error": max(errors), "normal_force_fraction_at_40_m_s": normal_fraction},
            {"maximum_symmetry_error": 1e-6, "normal_force_fraction_range": [0.01, 0.20]},
            "Thrust and power must be even. H and My must be odd. The normal force must be 1% to 20% of thrust.",
            "Reflection symmetry fixes even and odd load components in oblique flow.",
            cases,
        )

    def _windmill_regimes(self, context: ExecutionContext) -> _Evaluation:
        cases = self._cases(context, [
            ("--rpm", "2400", "--j-axial", value, "--collective", "0")
            for value in ("1.2", "1.6", "1.99")
        ] + [
            ("--rpm", "2400", "--v-axial", "-20", "--collective", "0"),
        ])
        passed = (
            cases[0].number("CT_prop") >= 0.0
            and cases[1].number("CT_prop") < 0.0
            and cases[2].number("CT_prop") < 0.0
            and cases[1].number("CP_prop") < 0.0
            and cases[2].number("CP_prop") < 0.0
            and cases[3].number("CT_prop") > 0.0
            and all(case.number("convergence_pct") >= 99.5 for case in cases)
        )
        return _Evaluation(
            passed,
            {"CT_prop": [case.number("CT_prop") for case in cases],
             "CP_prop": [case.number("CP_prop") for case in cases]},
            {"signs": ["near-positive", "negative", "negative", "positive-reverse-speed"]},
            "Loading must cross into negative thrust and power beyond J0 and recover for reversed axial speed.",
            "A windmilling disk absorbs shaft power after the zero-thrust advance ratio.",
            cases,
        )

    def _blade_count_scaling(self, context: ExecutionContext) -> _Evaluation:
        blade_counts = (1, 2, 3, 4, 5, 6)
        cases = self._cases(context, [
            (*BASE, "--geom-n-blades", str(count)) for count in blade_counts
        ])
        coefficients = [case.number("CT_prop") for case in cases]
        per_blade = [coefficient / count for coefficient, count in zip(coefficients, blade_counts)]
        return _Evaluation(
            _nondecreasing(coefficients) and _nonincreasing(per_blade),
            {"blade_count": list(blade_counts), "CT_prop": coefficients, "CT_per_blade": per_blade},
            {"CT_trend": "increasing", "CT_per_blade_trend": "decreasing"},
            "Total CT must increase while CT per blade decreases as blade count rises.",
            "Additional blades raise loading but increase induced interference per blade.",
            cases,
        )

    def _radius_scaling(self, context: ExecutionContext) -> _Evaluation:
        radii = (0.7, 0.94, 1.2)
        cases = self._cases(context, [
            (*BASE, "--geom-radius", str(radius)) for radius in radii
        ])
        thrust = [case.number("Thrust") for case in cases]
        coefficients = [case.number("CT_prop") for case in cases]
        return _Evaluation(
            _nondecreasing(thrust) and _nondecreasing(coefficients),
            {"radius_m": list(radii), "thrust_N": thrust, "CT_prop": coefficients},
            {"thrust_trend": "increasing", "CT_prop_trend": "nondecreasing with compressibility enabled"},
            "Thrust and CT must not decrease as radius raises tip Mach at fixed RPM and J.",
            "Dimensional thrust scales with diameter to the fourth power. Compressibility can also raise CT.",
            cases,
        )

    def _combine(self, first: _Evaluation, second: _Evaluation, name: str) -> _Evaluation:
        measured = {"first": dict(first.measured), "second": dict(second.measured)}
        expected = {"first": dict(first.expected), "second": dict(second.expected)}
        return _Evaluation(
            first.passed and second.passed,
            measured,
            expected,
            f"Both retained assertions in {name} must satisfy their individual rules.",
            f"This summary combines two independent retained checks: {first.notes} {second.notes}",
            first.cases + second.cases,
        )

    def _power_summary(self, context: ExecutionContext) -> _Evaluation:
        return self._combine(
            self._shaft_power_identity(context),
            self._induced_power_bookkeeping(context),
            "the power summary",
        )

    def _momentum_summary(self, context: ExecutionContext) -> _Evaluation:
        return self._combine(
            self._momentum_efficiency_bound(context),
            self._momentum_induced_velocity(context),
            "the momentum summary",
        )

    def _static_summary(self, context: ExecutionContext) -> _Evaluation:
        return self._combine(
            self._static_figure_of_merit(context),
            self._gentle_twist_hover(context),
            "the static-performance summary",
        )

    def _geometry_summary(self, context: ExecutionContext) -> _Evaluation:
        return self._combine(
            self._blade_count_scaling(context),
            self._radius_scaling(context),
            "the geometry summary",
        )
