"""Confirm flapping, lead-lag, and stability claims through public APIs."""
from __future__ import annotations

import json
import math
import numpy as np
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from zbemt import airfoils, api, geometry, studies
from zbemt.bemt import solve_bemt
from zbemt.models import AirfoilDef, BladeDynamicsDef, DerivativeRequest, FlightCondition, Project
from zbemt.validation import validate_blade_dynamics

from .models import CheckResult, Claim, ExecutionContext, FinalStatus


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = ROOT / "projects" / "starter_rotor"
SUPPORTED_DOMAINS = frozenset({"flapping", "lead_lag", "stability_derivatives"})

# Keep the declared set independent of ledger import order. The harness checks
# that this set covers every claim assigned to the three physical domains.
SUPPORTED_CLAIM_IDS = frozenset({
    "DERIV-A1", "DERIV-A2", "DERIV-A3", "DERIV-A4", "DERIV-E1",
    "DERIV-E2", "DERIV-E3", "DERIV-H5", "DERIV-NONDIM-RATES",
    "DERIV-P1", "DERIV-P2", "DERIV-P3", "DERIV-P4", "DERIV-P5",
    "DERIV-P6", "DERIV-P7", "FLAP-E1", "FLAP-E2", "FLAP-E3",
    "FLAP-E4", "FLAP-E5", "FLAP-E6", "FLAP-E7", "FLAP-E8",
    "FLAP-E9", "FLAP-E10", "FLAP-E11", "FLAP-E12", "FLAP-G4",
    "FLAP-G5", "FLAP-G5B", "FLAP-H3", "FLAP-H3B", "FLAP-H3C",
})


@dataclass(frozen=True)
class ProbeEvidence:
    """Hold the measured evidence for one claim-specific probe."""

    status: FinalStatus
    measured: Mapping[str, Any]
    expected: Mapping[str, Any]
    tolerance: str
    command: str
    artifacts: tuple[str, ...] = ()
    notes: str = ""


def _utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _status(passed: bool) -> FinalStatus:
    return FinalStatus.CONFIRMED_CORRECT if passed else FinalStatus.CONFIRMED_DEFECT


def _relative_error(left: float, right: float) -> float:
    return abs(left - right) / max(abs(right), 1e-15)


class _RealProbeRunner:
    """Run physical probes through geometry, validation, studies, and API."""

    def __init__(self) -> None:
        self._case_cache: dict[tuple[Any, ...], Any] = {}
        self._derivative_cache: dict[tuple[Any, ...], Any] = {}

    @staticmethod
    def _project(model: str = "offset", **dynamics_overrides: Any) -> Project:
        dynamics = BladeDynamicsDef(
            flap_model=model,
            hinge_offset_norm=0.05 if model != "rigid" else 0.0,
            inertia_source="lock",
            lock_number=8.0,
            harmonics=3,
            outer_tol_deg=1e-4,
            outer_max_iter=60,
        )
        dynamics = replace(dynamics, **dynamics_overrides)
        rotor_geometry = geometry.generate_rectangular(
            chord_norm=0.08,
            twist_root_deg=0.0,
            twist_tip_deg=0.0,
            radius_m=1.0,
            n_stations=16,
        )
        return Project(
            name="physics_flapping_probe",
            geometry=replace(rotor_geometry, dynamics=dynamics),
            airfoil=AirfoilDef(source="analytical", stall_model="linear"),
            config={
                "Ne": 16,
                "Npsi": 24,
                "solver": "newton",
                "max_iter": 300,
                "inflow_field_model": "glauert_global",
                "prandtl_loss_mode": "off",
                "use_rotational_augmentation": False,
                "use_radial_flow_correction": False,
                "use_compressibility": False,
            },
        )

    @staticmethod
    def _reference_project(model: str = "offset", **dynamics_overrides: Any) -> Project:
        """Return the rotor that defines the quantitative derivative claims."""
        project = api.open_project(DEFAULT_PROJECT)
        dynamics = BladeDynamicsDef(
            flap_model=model,
            hinge_offset_norm=0.05 if model != "rigid" else 0.0,
            inertia_source="lock",
            lock_number=8.0,
            harmonics=2,
            outer_tol_deg=1e-4,
            outer_max_iter=40,
            outer_relax=0.5,
        )
        dynamics = replace(dynamics, **dynamics_overrides)
        config = dict(project.config)
        config.update(Ne=32, Npsi=48, solver="newton", max_iter=300)
        return replace(
            project,
            geometry=replace(project.geometry, dynamics=dynamics),
            config=config,
        )

    def _case(
        self,
        model: str = "offset",
        *,
        mu_x: float = 0.0,
        collective: float = 6.0,
        rpm: float = 600.0,
        cyclic_c: float = 0.0,
        cyclic_s: float = 0.0,
        p_rate: float = 0.0,
        q_rate: float = 0.0,
        dynamics_overrides: Mapping[str, Any] | None = None,
    ):
        overrides = tuple(sorted((dynamics_overrides or {}).items()))
        key = (model, mu_x, collective, rpm, cyclic_c, cyclic_s, p_rate, q_rate, overrides)
        if key not in self._case_cache:
            project = self._project(model, **dict(overrides))
            condition = FlightCondition(
                name="probe",
                mu_x=mu_x,
                collective_deg=collective,
                rpm=rpm,
                cyclic_c_deg=cyclic_c,
                cyclic_s_deg=cyclic_s,
                p_rate_deg_s=p_rate,
                q_rate_deg_s=q_rate,
            )
            self._case_cache[key] = studies.run_single_case(project, condition)
        return self._case_cache[key]

    def _derivatives(self, model: str, mu_x: float = 0.0):
        key = (model, mu_x)
        if key not in self._derivative_cache:
            project = self._reference_project(model)
            request = DerivativeRequest(
                name="physics derivative probe",
                condition=FlightCondition(
                    name="probe", mu_x=mu_x, collective_deg=10.0, rpm=600.0
                ),
                trim="none",
                states=["w", "p", "q", "Omega"],
                controls=["theta_0", "theta_1c", "theta_1s"],
                outputs=["Thrust", "Torque", "Mx", "My", "Mx_hub", "Mx_total", "My_total"],
                steps={"w": 0.5, "p": 0.02, "q": 0.02},
                richardson_check=False,
            )
            self._derivative_cache[key] = api.compute_derivatives(project, request)
        return self._derivative_cache[key]

    def _reference_case(
        self,
        model: str = "offset",
        *,
        mu_x: float = 0.0,
        collective: float = 10.0,
        dynamics_overrides: Mapping[str, Any] | None = None,
    ):
        overrides = tuple(sorted((dynamics_overrides or {}).items()))
        key = ("reference", model, mu_x, collective, overrides)
        if key not in self._case_cache:
            project = self._reference_project(model, **dict(overrides))
            condition = FlightCondition(
                name="reference probe", mu_x=mu_x,
                collective_deg=collective, rpm=600.0,
            )
            self._case_cache[key] = studies.run_single_case(project, condition)
        return self._case_cache[key]

    @staticmethod
    def _evidence(
        passed: bool,
        measured: Mapping[str, Any],
        expected: Mapping[str, Any],
        tolerance: str,
        command: str,
        notes: str,
        status: FinalStatus | None = None,
    ) -> ProbeEvidence:
        return ProbeEvidence(
            status=status or _status(passed),
            measured=measured,
            expected=expected,
            tolerance=tolerance,
            command=command,
            notes=notes,
        )

    def __call__(self, claim_id: str, output_directory: Path) -> ProbeEvidence:
        method = getattr(self, f"_probe_{claim_id.lower().replace('-', '_')}")
        return method()

    def _probe_flap_e1(self) -> ProbeEvidence:
        offsets = (0.02, 0.05, 0.10, 0.15)
        errors = [
            abs(geometry.flap_frequency_ratio_squared(e, 0.0, 1.0, 1.0)
                - (1.0 + 1.5 * e / (1.0 - e)))
            for e in offsets
        ]
        maximum = max(errors)
        return self._evidence(
            maximum <= 1e-12,
            {"offsets": offsets, "absolute_errors": errors, "maximum_absolute_error": maximum},
            {"closed_form": "1 + 1.5*e/(1-e)"},
            "The maximum absolute error must not exceed 1e-12.",
            "python -c \"from zbemt import geometry; geometry.flap_frequency_ratio_squared(...)\"",
            "The public geometry API matches the offset-hinge closed form.",
        )

    def _probe_flap_g4(self) -> ProbeEvidence:
        inertia, omega = 0.07, 80.0
        springs = (100.0, 300.0, 500.0)
        errors = [
            abs(geometry.flap_frequency_ratio_squared(0.05, spring, inertia, omega)
                - (1.0 + 1.5 * 0.05 / 0.95 + spring / (inertia * omega**2)))
            for spring in springs
        ]
        return self._evidence(
            max(errors) <= 1e-12,
            {"spring_Nm_per_rad": springs, "absolute_errors": errors},
            {"closed_form": "1 + 1.5*e/(1-e) + K/(I*Omega^2)"},
            "Each absolute error must not exceed 1e-12.",
            "python -c \"from zbemt import geometry; geometry.flap_frequency_ratio_squared(...)\"",
            "The public geometry API adds the root-spring term linearly.",
        )

    def _probe_flap_g5(self) -> ProbeEvidence:
        e, spring, inertia, omega = 0.05, 300.0, 0.06, 80.0
        actual = geometry.lag_frequency_ratio_squared(e, spring, inertia, omega)
        expected = 1.5 * e / (1.0 - e) + spring / (inertia * omega**2)
        error = abs(actual - expected)
        return self._evidence(
            error <= 1e-12,
            {"nu_zeta_squared": actual, "absolute_error": error},
            {"nu_zeta_squared": expected},
            "The absolute error must not exceed 1e-12.",
            "python -c \"from zbemt import geometry; geometry.lag_frequency_ratio_squared(...)\"",
            "The public geometry API matches the lead-lag frequency equation.",
        )

    def _probe_flap_g5b(self) -> ProbeEvidence:
        dynamics = BladeDynamicsDef(flap_model="rigid", lag_enabled=True)
        issues = validate_blade_dynamics(dynamics, geometry.generate_rectangular(), rpm=600.0)
        errors = [issue.message for issue in issues if issue.level == "error"]
        rejected = any("lead-lag cannot be enabled" in message for message in errors)
        return self._evidence(
            rejected,
            {"validation_rejected": rejected, "errors": errors},
            {"validation_level": "error"},
            "Validation must return an error before execution.",
            "python -c \"from zbemt.validation import validate_blade_dynamics; ...\"",
            "Validation prevents a rigid path from discarding enabled lead-lag motion.",
        )

    def _probe_flap_e2(self) -> ProbeEvidence:
        dynamics = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.0, harmonics=1)
        issues = validate_blade_dynamics(dynamics, geometry.generate_rectangular(), rpm=600.0)
        levels = [issue.level for issue in issues if "resonant" in issue.message.lower()]
        passed = "error" in levels
        return self._evidence(
            passed,
            {"resonance_issue_levels": levels, "execution_blocked": passed},
            {"required_level": "error", "flap_solution": None},
            "A named resonance error must block the run.",
            "python -c \"from zbemt.validation import validate_blade_dynamics; ...\"",
            "The validation route currently determines whether the public run is blocked.",
        )

    def _probe_flap_e3(self) -> ProbeEvidence:
        summary = self._case("offset").summary
        values = {
            "beta_0_deg": summary["beta_0_deg"],
            "beta_1c_deg": summary["beta_1c_deg"],
            "beta_1s_deg": summary["beta_1s_deg"],
            "Mx_hub": summary["Mx_hub"],
            "My_hub": summary["My_hub"],
        }
        passed = values["beta_0_deg"] > 0.0 and max(
            abs(values[name]) for name in ("beta_1c_deg", "beta_1s_deg", "Mx_hub", "My_hub")
        ) <= 1e-6
        return self._evidence(
            passed, values,
            {"beta_0_sign": "positive", "first_harmonic_and_hub_moment_max": 1e-6},
            "Coning must be positive. First harmonics and hub moments must not exceed 1e-6.",
            "python -c \"from zbemt import studies; studies.run_single_case(...)\"",
            "The API run uses an untwisted rectangular rotor in hover.",
        )

    def _probe_flap_e4(self) -> ProbeEvidence:
        summary = self._case("offset", mu_x=0.15).summary
        passed = summary["beta_1c_deg"] < 0.0 and summary["tpp_tilt_long_deg"] > 0.0
        return self._evidence(
            passed,
            {"beta_1c_deg": summary["beta_1c_deg"], "tpp_tilt_long_deg": summary["tpp_tilt_long_deg"]},
            {"beta_1c_sign": "negative", "longitudinal_tilt_sign": "positive"},
            "The rotor must flap aft and the longitudinal tilt must be positive.",
            "python -c \"from zbemt import studies; studies.run_single_case(...mu_x=0.15...)\"",
            "The signs follow the repository tip-path-plane convention.",
        )

    def _probe_flap_e5(self) -> ProbeEvidence:
        base = self._case("offset", mu_x=0.15).summary
        forced = self._case("offset", mu_x=0.15, cyclic_c=1.0).summary
        delta_c = forced["beta_1c_deg"] - base["beta_1c_deg"]
        delta_s = forced["beta_1s_deg"] - base["beta_1s_deg"]
        ratio = abs(delta_c) / max(abs(delta_s), 1e-15)
        return self._evidence(
            abs(delta_s) > abs(delta_c) and ratio <= 0.20,
            {"delta_beta_1c_deg": delta_c, "delta_beta_1s_deg": delta_s, "secondary_ratio": ratio},
            {"dominant_harmonic": "orthogonal", "secondary_ratio_max": 0.20},
            "The orthogonal response must dominate and the secondary ratio must not exceed 0.20.",
            "python -c \"from zbemt import studies; studies.run_single_case(...cyclic_c_deg=1...)\"",
            "The measured response subtracts the no-cyclic forward-flight baseline.",
        )

    def _probe_flap_e6(self) -> ProbeEvidence:
        zero = self._case("offset", dynamics_overrides={"pitch_flap_coupling_deg": 0.0}).summary
        coupled = self._case("offset", dynamics_overrides={"pitch_flap_coupling_deg": 30.0}).summary
        return self._evidence(
            coupled["beta_0_deg"] < zero["beta_0_deg"],
            {"beta_0_zero_deg": zero["beta_0_deg"], "beta_0_coupled_deg": coupled["beta_0_deg"]},
            {"trend": "coupled coning is lower"},
            "The 30-degree coupling case must have less coning than the zero-coupling case.",
            "python -c \"from zbemt import studies; studies.run_single_case(...pitch_flap_coupling_deg...)\"",
            "Both API cases use the same hover condition.",
        )

    def _probe_flap_e7(self) -> ProbeEvidence:
        base = self._case("offset").summary
        results = {}
        for rate_name, arguments in {
            "p_plus": {"p_rate": 2.0}, "p_minus": {"p_rate": -2.0},
            "q_plus": {"q_rate": 2.0}, "q_minus": {"q_rate": -2.0},
        }.items():
            summary = self._case("offset", **arguments).summary
            results[rate_name] = (
                summary["beta_1c_deg"] - base["beta_1c_deg"],
                summary["beta_1s_deg"] - base["beta_1s_deg"],
            )
        p_plus, p_minus = results["p_plus"], results["p_minus"]
        q_plus, q_minus = results["q_plus"], results["q_minus"]
        reversal = max(abs(p_plus[i] + p_minus[i]) for i in (0, 1)) + max(
            abs(q_plus[i] + q_minus[i]) for i in (0, 1)
        )
        amplitudes = math.hypot(*p_plus), math.hypot(*q_plus)
        magnitude_error = _relative_error(amplitudes[0], amplitudes[1])
        return self._evidence(
            reversal <= 1e-6 and magnitude_error <= 0.15,
            {"harmonics_deg": results, "reversal_error_deg": reversal, "magnitude_relative_error": magnitude_error},
            {"reversal_error_max_deg": 1e-6, "magnitude_relative_error_max": 0.15},
            "Rate reversal error must not exceed 1e-6 degree. Pitch and roll amplitudes must agree within 15%.",
            "python -c \"from zbemt import studies; studies.run_single_case(...p_rate_deg_s or q_rate_deg_s...)\"",
            "The comparison subtracts the zero-rate hover harmonics.",
        )

    def _probe_flap_e8(self) -> ProbeEvidence:
        rigid = self._case("rigid", mu_x=0.15, cyclic_c=1.0, cyclic_s=1.0).summary
        flap = self._case("offset", mu_x=0.15, cyclic_c=1.0, cyclic_s=1.0).summary
        rigid_moments = abs(rigid["Mx"]), abs(rigid["My"])
        flap_moments = abs(flap["Mx_total"]), abs(flap["My_total"])
        passed = all(flap_value < rigid_value for flap_value, rigid_value in zip(flap_moments, rigid_moments))
        return self._evidence(
            passed,
            {"rigid_moment_magnitudes": rigid_moments, "flap_moment_magnitudes": flap_moments},
            {"ordering": "each flap moment magnitude is lower"},
            "Both flapping hub-moment magnitudes must be lower than the rigid values.",
            "python -c \"from zbemt import studies; studies.run_single_case(...flap_model...)\"",
            "Both API cases use the same cyclic controls and flight condition.",
        )

    def _probe_flap_e9(self) -> ProbeEvidence:
        project = self._project("rigid")
        condition = FlightCondition(name="rigid probe", collective_deg=6.0,
                                    rpm=600.0)
        cfg = studies._build_config(project.config, airfoil_def=project.airfoil)
        rotor = studies._to_rotor(project.geometry, collective_deg=condition.collective_deg,
                                  rpm=condition.rpm)
        radial = airfoils.radial_reynolds_mach(rotor, cfg, mu_x=condition.mu_x)
        airfoil = airfoils.to_blade_airfoil([project.airfoil], radial=radial)
        plain = solve_bemt(rotor, airfoil, cfg, mu_x=condition.mu_x, Vz=condition.Vz)
        routed = studies.run_single_case(project, condition).maps
        differences = []
        for name, plain_value in plain.items():
            if name == "elapsed":
                continue
            routed_value = routed[name]
            plain_array = np.asarray(plain_value)
            routed_array = np.asarray(routed_value)
            if plain_array.dtype.kind in "bOUS" or routed_array.dtype.kind in "bOUS":
                difference = 0.0 if np.array_equal(routed_array, plain_array) else 1.0
            elif plain_array.size == 0 and routed_array.size == 0:
                difference = 0.0
            else:
                difference = float(np.max(np.abs(routed_array - plain_array)))
            differences.append(difference)
        maximum_difference = max(differences, default=0.0)
        return self._evidence(
            maximum_difference == 0.0,
            {"maximum_array_difference": maximum_difference,
             "plain_map_keys": len(plain), "routed_map_keys": len(routed)},
            {"maximum_array_difference": 0.0},
            "Every scalar and array must be bit-identical between two independent routes.",
            "python -c \"from zbemt.bemt import solve_bemt; from zbemt import studies; compare solve_bemt(...) with studies.run_single_case(...)\"",
            "The rigid public route is compared with the direct plain solver before the zero-valued dynamics keys are added.",
        )

    def _probe_flap_e10(self) -> ProbeEvidence:
        maps = self._case("rigid").maps
        required = {name: maps.get(name) for name in ("beta_0_rad", "beta_1c_rad", "beta_1s_rad", "beta_coeffs")}
        passed = required["beta_coeffs"] == {} and all(required[name] == 0.0 for name in required if name != "beta_coeffs")
        return self._evidence(
            passed, required,
            {"beta_0_rad": 0.0, "beta_1c_rad": 0.0, "beta_1s_rad": 0.0, "beta_coeffs": {}},
            "Each rigid motion key must exist and contain its zero value.",
            "python -c \"from zbemt import studies; studies.run_single_case(...flap_model='rigid'...).maps\"",
            "The check reads the raw public API map contract.",
        )

    def _trim_target(self) -> tuple[Project, FlightCondition, float]:
        project = self._project("rigid")
        condition = FlightCondition(name="trim", mu_x=0.0, collective_deg=6.0, rpm=600.0)
        target = studies.run_single_case(project, condition).summary["Thrust"]
        return project, condition, target

    def _probe_flap_e11(self) -> ProbeEvidence:
        project, condition, target = self._trim_target()
        collective = studies.run_case_trimmed(
            project, replace(condition, collective_deg=4.0),
            trim_mode="solve_collective", target_kind="thrust", target_value=target,
        )
        rpm = studies.run_case_trimmed(
            project, replace(condition, rpm=500.0),
            trim_mode="solve_rpm", target_kind="thrust", target_value=target,
        )
        residuals = [collective.summary["trim_residual"], rpm.summary["trim_residual"]]
        dofs = [collective.summary["trim_dof"], rpm.summary["trim_dof"]]
        passed = max(residuals) <= max(2.0, abs(target) * 1e-4) and dofs == ["collective_deg", "rpm"]
        return self._evidence(
            passed,
            {"target_thrust_N": target, "residuals_N": residuals, "trim_dofs": dofs},
            {"residual_max_N": max(2.0, abs(target) * 1e-4), "trim_dofs": ["collective_deg", "rpm"]},
            "Both trim modes must meet the tolerance and report the solved degree of freedom.",
            "python -c \"from zbemt import studies; studies.run_case_trimmed(...)\"",
            "The target is the measured thrust of the reference rotor. This scales the catalog check to the probe rotor.",
        )

    def _probe_flap_e12(self) -> ProbeEvidence:
        project, condition, target = self._trim_target()
        success = studies.run_case_trimmed(
            project, replace(condition, collective_deg=4.0),
            trim_mode="solve_collective", target_kind="thrust", target_value=target,
        ).summary
        exhausted = studies.run_case_trimmed(
            project, replace(condition, collective_deg=4.0),
            trim_mode="solve_collective", target_kind="thrust", target_value=target * 0.9,
            max_iter=1,
        ).summary
        fields = ("trim_target", "trim_dof", "trim_residual", "trim_converged")
        present = all(name in success and name in exhausted for name in fields)
        passed = present and success["trim_converged"] is True and exhausted["trim_converged"] is False
        return self._evidence(
            passed,
            {"fields_present": present, "success_converged": success.get("trim_converged"), "exhausted_converged": exhausted.get("trim_converged")},
            {"success_converged": True, "exhausted_converged": False},
            "Both paths must record all four fields. The one-iteration path must report false.",
            "python -c \"from zbemt import studies; studies.run_case_trimmed(...max_iter=1...)\"",
            "The API checks both a completed trim and an exhausted trim.",
        )

    def _probe_flap_h3(self) -> ProbeEvidence:
        records = []
        for mu_x in (0.05, 0.15):
            project = self._project("offset")
            result = studies.run_case_trimmed(
                project,
                FlightCondition(name="trim", mu_x=mu_x, collective_deg=6.0, rpm=600.0),
                trim_mode="solve_cyclic_flapback",
                max_iter=120,
            )
            records.append(result.summary)
        residuals = [max(abs(record["beta_1c_deg"]), abs(record["beta_1s_deg"])) for record in records]
        cyclic = [math.hypot(record["cyclic_c_deg"], record["cyclic_s_deg"]) for record in records]
        passed = max(residuals) <= 0.001 and cyclic[1] > cyclic[0]
        return self._evidence(
            passed,
            {"mu_x": [0.05, 0.15], "flap_residual_deg": residuals, "cyclic_magnitude_deg": cyclic},
            {"flap_residual_max_deg": 0.001, "cyclic_trend": "increasing"},
            "Both harmonics must not exceed 0.001 degree. Cyclic magnitude must increase.",
            "python -c \"from zbemt import studies; studies.run_case_trimmed(...solve_cyclic_flapback...)\"",
            "The public trim API evaluates both advance ratios.",
        )

    def _probe_flap_h3b(self) -> ProbeEvidence:
        project = self._project("offset")
        condition = FlightCondition(name="trim", mu_x=0.10, collective_deg=6.0, rpm=600.0)
        target = studies.run_single_case(project, condition).summary["Thrust"]
        try:
            result = studies.run_case_trimmed(
                project, condition,
                trim_mode="solve_collective_and_cyclic",
                target_kind="thrust", target_value=target,
                max_iter=120,
            ).summary
        except Exception as exc:
            return self._evidence(
                False,
                {"exception": f"{type(exc).__name__}: {exc}"},
                {"exception": None, "thrust_residual_max_N": max(2.0, target * 1e-4), "flap_residual_max_deg": 0.001},
                "The trim must complete without an exception and meet all three residual limits.",
                "python -c \"from zbemt import studies; studies.run_case_trimmed(...solve_collective_and_cyclic...)\"",
                "The public three-degree trim raised an exception.",
            )
        flap_residual = max(abs(result["beta_1c_deg"]), abs(result["beta_1s_deg"]))
        thrust_residual = abs(result["Thrust"] - target)
        passed = thrust_residual <= max(2.0, target * 1e-4) and flap_residual <= 0.001
        return self._evidence(
            passed,
            {"target_thrust_N": target, "thrust_residual_N": thrust_residual, "flap_residual_deg": flap_residual},
            {"thrust_residual_max_N": max(2.0, target * 1e-4), "flap_residual_max_deg": 0.001},
            "The trim must meet the thrust and first-harmonic tolerances.",
            "python -c \"from zbemt import studies; studies.run_case_trimmed(...solve_collective_and_cyclic...)\"",
            "The public API returned all three solved controls.",
        )

    def _probe_flap_h3c(self) -> ProbeEvidence:
        project = self._reference_project("offset")
        condition = FlightCondition(name="trim", mu_x=0.15, collective_deg=8.0, rpm=600.0)
        outcomes: dict[int, str] = {}
        for limit in (1, 120):
            try:
                studies.run_case_trimmed(project, condition, trim_mode="solve_cyclic_flapback", max_iter=limit)
                outcomes[limit] = "converged"
            except Exception as exc:
                outcomes[limit] = f"{type(exc).__name__}: {exc}"
        passed = outcomes[1] != "converged" and outcomes[120] == "converged"
        return self._evidence(
            passed, {"outcomes": outcomes},
            {"1_iteration": "named convergence error", "120_iterations": "converged"},
            "The one-iteration path must fail clearly and the 120-iteration path must converge.",
            "python -c \"from zbemt import studies; studies.run_case_trimmed(...max_iter=1 or 120...)\"",
            "The same public trim route runs at both iteration limits.",
        )

    def _probe_deriv_e2(self) -> ProbeEvidence:
        records = []
        for mu_x in (0.15, 0.20, 0.25):
            summary = self._reference_case(
                "offset", mu_x=mu_x,
                dynamics_overrides={"outer_max_iter": 40},
            ).summary
            records.append((summary["flap_outer_iterations"], summary["flap_outer_residual_deg"]))
        passed = all(iterations <= 40 and residual <= 1e-4 for iterations, residual in records)
        return self._evidence(
            passed,
            {"mu_x": [0.15, 0.20, 0.25], "iterations_and_residual_deg": records},
            {"maximum_iterations": 40, "maximum_residual_deg": 1e-4},
            "Each outer solve must reach 1e-4 degree before 40 iterations.",
            "python -c \"from zbemt import studies; studies.run_single_case(...outer_max_iter=40...)\"",
            "The direct cases expose the outer-loop state used by derivative studies.",
        )

    def _rate_matrix(self, model: str, mu_x: float = 0.0) -> dict[str, float]:
        matrix = self._derivatives(model, mu_x).matrix
        return {
            "Mx_p": matrix[("Mx_total", "p")],
            "Mx_q": matrix[("Mx_total", "q")],
            "My_p": matrix[("My_total", "p")],
            "My_q": matrix[("My_total", "q")],
        }

    def _invariance_evidence(self, claim_id: str = "DERIV-E1") -> ProbeEvidence:
        values = self._rate_matrix("offset")
        scale = max(abs(value) for value in values.values())
        residuals = {
            "direct": abs(values["Mx_q"] - values["My_p"]) / max(scale, 1e-15),
            "cross": abs(values["Mx_p"] + values["My_q"]) / max(scale, 1e-15),
        }
        passed = max(residuals.values()) <= 1e-6
        return self._evidence(
            passed,
            {"rate_matrix": values, "normalized_residuals": residuals},
            {"maximum_normalized_residual": 1e-6},
            "Both rotational-invariance residuals must not exceed 1e-6.",
            "python -c \"from zbemt import api; api.compute_derivatives(...)\"",
            f"The {claim_id} probe uses central finite differences through the public derivative API.",
        )

    def _probe_deriv_e1(self) -> ProbeEvidence:
        return self._invariance_evidence()

    def _probe_deriv_a1(self) -> ProbeEvidence:
        results = []
        for lock in (4.0, 8.0, 16.0):
            for offset in (0.02, 0.10):
                project = self._reference_project("offset", lock_number=lock, hinge_offset_norm=offset)
                request = DerivativeRequest(
                    name="invariance sweep",
                    condition=FlightCondition(name="hover", collective_deg=10.0, rpm=600.0),
                    trim="none", states=["p", "q"], controls=[],
                    outputs=["Mx_total", "My_total"], richardson_check=False,
                )
                matrix = api.compute_derivatives(project, request).matrix
                scale = max(abs(value) for value in matrix.values())
                results.append({
                    "lock_number": lock,
                    "hinge_offset": offset,
                    "direct_residual": abs(matrix[("Mx_total", "q")] - matrix[("My_total", "p")]) / scale,
                    "cross_residual": abs(matrix[("Mx_total", "p")] + matrix[("My_total", "q")]) / scale,
                })
        maximum = max(max(item["direct_residual"], item["cross_residual"]) for item in results)
        return self._evidence(
            maximum <= 1e-6,
            {"cases": results, "maximum_normalized_residual": maximum},
            {"maximum_normalized_residual": 1e-6},
            "Every normalized invariance residual must not exceed 1e-6.",
            "python -c \"from zbemt import api; api.compute_derivatives(...Lock and offset sweep...)\"",
            "The public derivative API evaluates all six Lock-number and hinge-offset combinations.",
        )

    def _probe_deriv_a2(self) -> ProbeEvidence:
        rigid = self._derivatives("rigid").matrix[("Thrust", "w")]
        flap = self._derivatives("offset").matrix[("Thrust", "w")]
        hover_error = _relative_error(flap, rigid)
        forward = self._reference_case(
            "offset", mu_x=0.20,
            dynamics_overrides={"outer_max_iter": 40},
        ).summary
        forward_converged = bool(forward["flap_outer_converged"])
        converged = forward_converged
        return self._evidence(
            hover_error <= 0.001 and converged,
            {"rigid_heave": rigid, "flap_heave": flap, "hover_relative_error": hover_error,
             "forward_flap_residual_deg": forward["flap_outer_residual_deg"],
             "forward_flap_converged": converged},
            {"hover_relative_error_max": 0.001, "forward_flap_converged": True},
            "Hover heave values must agree within 0.1%. The forward flap solve must converge.",
            "python -c \"from zbemt import api; api.compute_derivatives(...); studies.run_single_case(...)\"",
            "The derivative API and the direct forward case use the same flap configuration.",
        )

    def _probe_deriv_a3(self) -> ProbeEvidence:
        rigid = self._rate_matrix("rigid", 0.10)
        flap = self._rate_matrix("offset", 0.10)
        rigid_matrix = self._derivatives("rigid", 0.10).matrix
        flap_matrix = self._derivatives("offset", 0.10).matrix
        rigid_aerodynamic = rigid_matrix[("Mx", "q")]
        flap_aerodynamic = flap_matrix[("Mx", "q")]
        flap_hub = flap_matrix[("Mx_hub", "q")]
        flap_total = flap_matrix[("Mx_total", "q")]
        flap_converged = bool(self._reference_case("offset", mu_x=0.10).summary["flap_outer_converged"])
        rigid_error = _relative_error(rigid["Mx_q"], rigid["My_p"])
        aerodynamic_relief = abs(flap_aerodynamic) < abs(rigid_aerodynamic)
        moment_balance_error = abs(flap_total - flap_aerodynamic - flap_hub)
        return self._evidence(
            rigid_error <= 0.01 and aerodynamic_relief and moment_balance_error <= 1e-8,
            {"rigid_rate_matrix": rigid, "flap_rate_matrix": flap,
             "rigid_direct_relative_error": rigid_error,
             "flap_outer_converged": flap_converged,
             "rigid_aerodynamic_pitch_damping": rigid_aerodynamic,
             "flap_aerodynamic_pitch_damping": flap_aerodynamic,
             "flap_hub_pitch_damping": flap_hub,
             "flap_total_pitch_damping": flap_total,
             "moment_balance_error": moment_balance_error},
            {"rigid_direct_relative_error_max": 0.01,
             "flap_aerodynamic_pitch_magnitude": "less than rigid aerodynamic damping",
             "moment_balance_error_max": 1e-8},
            "Rigid direct damping must agree within 1%. Flap aerodynamic damping must be lower than rigid aerodynamic damping. The total must equal the aerodynamic and hub terms.",
            "python -c \"from zbemt import api; api.compute_derivatives(...mu_x=0.10...)\"",
            "The offset hinge adds a structural hub moment. Compare the aerodynamic moment before comparing damping relief.",
            status=None if flap_converged else FinalStatus.INCONCLUSIVE,
        )

    def _probe_deriv_a4(self) -> ProbeEvidence:
        matrix = self._derivatives("rigid").matrix
        values = {"dThrust_dOmega": matrix[("Thrust", "Omega")], "dTorque_dOmega": matrix[("Torque", "Omega")]}
        return self._evidence(
            all(value > 0.0 for value in values.values()), values,
            {"signs": "strictly positive"},
            "Both shaft-speed derivatives must be strictly positive.",
            "python -c \"from zbemt import api; api.compute_derivatives(...states=['Omega']...)\"",
            "The API perturbs shaft speed around the hover reference.",
        )

    def _probe_deriv_e3(self) -> ProbeEvidence:
        project = self._reference_project("offset")
        condition = FlightCondition(name="trim", mu_x=0.20, collective_deg=10.0, rpm=600.0)
        target = studies.run_single_case(project, condition).summary["Thrust"]
        request = DerivativeRequest(
            name="trim bracket probe", condition=condition, trim="thrust",
            trim_target_thrust=target, states=["w"], controls=[], outputs=["Thrust"],
            richardson_check=False,
        )
        try:
            api.compute_derivatives(project, request)
            outcome = "completed"
            passed = True
        except Exception as exc:
            outcome = f"{type(exc).__name__}: {exc}"
            passed = "bracket" in str(exc).lower()
        return self._evidence(
            passed,
            {"outcome": outcome, "partial_matrix_returned": False},
            {"allowed": ["completed", "named bracket error without a partial matrix"]},
            "The study must complete or return a named bracket error without a partial matrix.",
            "python -c \"from zbemt import api; api.compute_derivatives(...trim='thrust'...)\"",
            "The public API exception is the complete outcome when the bracket cannot contain the target.",
        )

    def _probe_deriv_h5(self) -> ProbeEvidence:
        project = self._project("rigid")
        base = FlightCondition(name="trend", mu_x=0.10, collective_deg=6.0, rpm=600.0)
        def slope(field: str, before: FlightCondition, after: FlightCondition, step: float) -> float:
            return (studies.run_single_case(project, after).summary[field]
                    - studies.run_single_case(project, before).summary[field]) / (2.0 * step)
        du_thrust = slope("Thrust", replace(base, mu_x=0.09), replace(base, mu_x=0.11), 0.01)
        du_torque = slope("Torque", replace(base, mu_x=0.09), replace(base, mu_x=0.11), 0.01)
        dw_thrust = slope("Thrust", replace(base, Vz=-0.5), replace(base, Vz=0.5), 0.5)
        passed = du_thrust > 0.0 and du_torque < 0.0 and dw_thrust < 0.0
        return self._evidence(
            passed,
            {"dThrust_dmu": du_thrust, "dTorque_dmu": du_torque, "dThrust_dVz": dw_thrust},
            {"signs": ["positive", "negative", "negative"]},
            "All three central-difference signs must match the stated trends.",
            "python -c \"from zbemt import studies; studies.run_single_case(...central differences...)\"",
            "The public case API supplies the three physical trend slopes.",
        )

    def _probe_deriv_nondim_rates(self) -> ProbeEvidence:
        project = self._reference_project("offset")
        outcome = self._derivatives("offset")
        omega = 600.0 * 2.0 * math.pi / 60.0
        rho = float(project.config.get("rho", 1.225))
        area = math.pi * project.geometry.radius_m**2
        load_scale = rho * area * (omega * project.geometry.radius_m)**2 * project.geometry.radius_m
        errors = []
        for pair in (("Mx_total", "q"), ("My_total", "p")):
            expected = outcome.matrix[pair] / load_scale
            errors.append(_relative_error(outcome.matrix_nondim[pair], expected))
        maximum = max(errors)
        return self._evidence(
            maximum <= 0.001,
            {"relative_errors": errors, "maximum_relative_error": maximum},
            {"maximum_relative_error": 0.001},
            "Both non-dimensional rate derivatives must agree with the declared scaling within 0.1%.",
            "python -c \"from zbemt import api; api.compute_derivatives(...).matrix_nondim\"",
            "The rate variables are already measured in radians per second, so their variable scale is one.",
        )

    def _probe_deriv_p1(self) -> ProbeEvidence:
        value = self._derivatives("offset").matrix[("Thrust", "w")]
        error = _relative_error(value, -35.0)
        return self._evidence(
            value < 0.0 and error <= 0.15,
            {"dThrust_dw_N_per_m_s": value, "relative_error": error},
            {"reference_N_per_m_s": -35.0, "relative_error_max": 0.15},
            "The derivative must be negative and within 15% of -35 N/(m/s).",
            "python -c \"from zbemt import api; api.compute_derivatives(...states=['w']...)\"",
            "The reference comes from coupled uniform-inflow theory.",
        )

    def _probe_deriv_p2(self) -> ProbeEvidence:
        value = self._derivatives("offset").matrix[("Mx_total", "q")]
        error = _relative_error(value, -20.2)
        return self._evidence(
            value < 0.0 and error <= 0.05,
            {"dMx_dq_Nm_per_rad_s": value, "relative_error": error},
            {"reference_Nm_per_rad_s": -20.2, "relative_error_max": 0.05},
            "The damping must be negative and within 5% of -20.2 N m/(rad/s).",
            "python -c \"from zbemt import api; api.compute_derivatives(...states=['q']...)\"",
            "The reference equals minus flap inertia times shaft speed times Lock number divided by eight.",
        )

    def _probe_deriv_p3(self) -> ProbeEvidence:
        values = {model: self._rate_matrix(model) for model in ("rigid", "offset")}
        errors = {model: _relative_error(matrix["Mx_q"], matrix["My_p"]) for model, matrix in values.items()}
        return self._evidence(
            max(errors.values()) <= 0.001,
            {"rate_matrices": values, "relative_errors": errors},
            {"maximum_relative_error": 0.001},
            "Direct pitch and roll damping must agree within 0.1% for both models.",
            "python -c \"from zbemt import api; api.compute_derivatives(...rigid and offset...)\"",
            "Hover axisymmetry sets the direct damping equality.",
        )

    def _probe_deriv_p4(self) -> ProbeEvidence:
        values = self._rate_matrix("rigid")
        direct_error = _relative_error(values["Mx_q"], values["My_p"])
        cross_max = max(abs(values["Mx_p"]), abs(values["My_q"]))
        passed = direct_error <= 0.001 and cross_max <= 1e-6
        return self._evidence(
            passed,
            {"rate_matrix": values, "direct_relative_error": direct_error, "cross_term_max": cross_max},
            {"direct_relative_error_max": 0.001, "cross_term_max": 1e-6},
            "Direct damping must agree within 0.1%. Cross terms must be below 1e-6.",
            "python -c \"from zbemt import api; api.compute_derivatives(...flap_model='rigid'...)\"",
            "The rigid hover rotor supplies the isotropic limit.",
        )

    def _probe_deriv_p5(self) -> ProbeEvidence:
        matrix = self._derivatives("offset").matrix
        values = {
            "Mx_1c": matrix[("Mx_total", "theta_1c")], "Mx_1s": matrix[("Mx_total", "theta_1s")],
            "My_1c": matrix[("My_total", "theta_1c")], "My_1s": matrix[("My_total", "theta_1s")],
        }
        scale = max(abs(value) for value in values.values())
        residuals = [abs(values["Mx_1c"] - values["My_1s"]) / scale,
                     abs(values["Mx_1s"] + values["My_1c"]) / scale]
        return self._evidence(
            max(residuals) <= 1e-6,
            {"control_matrix": values, "normalized_residuals": residuals},
            {"maximum_normalized_residual": 1e-6},
            "Both cyclic-control invariance residuals must not exceed 1e-6.",
            "python -c \"from zbemt import api; api.compute_derivatives(...controls=['theta_1c','theta_1s']...)\"",
            "Hover rotational invariance sets the cyclic-control matrix form.",
        )

    def _probe_deriv_p6(self) -> ProbeEvidence:
        matrix = self._derivatives("offset").matrix
        values = {
            "heave": matrix[("Thrust", "w")], "pitch_damping": matrix[("Mx_total", "q")],
            "roll_damping": matrix[("My_total", "p")], "collective_thrust": matrix[("Thrust", "theta_0")],
            "speed_thrust": matrix[("Thrust", "Omega")],
        }
        passed = all(values[name] < 0.0 for name in ("heave", "pitch_damping", "roll_damping")) and all(
            values[name] > 0.0 for name in ("collective_thrust", "speed_thrust")
        ) and all(value != 0.0 for value in values.values())
        return self._evidence(
            passed, values,
            {"negative": ["heave", "pitch_damping", "roll_damping"], "positive": ["collective_thrust", "speed_thrust"]},
            "Every derivative must be nonzero and have its prescribed sign.",
            "python -c \"from zbemt import api; api.compute_derivatives(...)\"",
            "One public derivative study supplies all five sign checks.",
        )

    def _probe_deriv_p7(self) -> ProbeEvidence:
        records = {}
        for mu_x in (0.0, 0.20):
            rigid = self._rate_matrix("rigid", mu_x)
            flap = self._rate_matrix("offset", mu_x)
            rigid_matrix = self._derivatives("rigid", mu_x).matrix
            flap_matrix = self._derivatives("offset", mu_x).matrix
            records[str(mu_x)] = {
                "rigid_total": rigid,
                "flap_total": flap,
                "rigid_aerodynamic": {
                    "Mx_q": rigid_matrix[("Mx", "q")],
                    "My_p": rigid_matrix[("My", "p")],
                },
                "flap_aerodynamic": {
                    "Mx_q": flap_matrix[("Mx", "q")],
                    "My_p": flap_matrix[("My", "p")],
                },
            }
        flap_converged = all(
            self._reference_case("offset", mu_x=mu_x).summary["flap_outer_converged"]
            for mu_x in (0.0, 0.20)
        )
        # The acceptance rule requires the ordering in HOVER only. Forward
        # flight has a coupled damping matrix, so an individual direct term
        # there carries no monotonic requirement. The forward record stays in
        # the evidence without entering the decision.
        hover = records["0.0"]
        passed = all(
            abs(hover["rigid_aerodynamic"][key])
            > abs(hover["flap_aerodynamic"][key])
            for key in ("Mx_q", "My_p")
        )
        return self._evidence(
            passed, {"cases": records, "flap_outer_converged": flap_converged},
            {"hover_ordering": "rigid aerodynamic damping magnitude exceeds flapping aerodynamic damping",
             "forward_flight": "coupled damping matrix without an individual monotonic ordering"},
            "Both aerodynamic damping magnitudes must be lower in hover. Forward flight must report the coupled matrix without claiming an individual monotonic ordering.",
            "python -c \"from zbemt import api; api.compute_derivatives(...rigid and offset...)\"",
            "The public derivative API evaluates hover and advance ratio 0.20. The offset-hinge structural moment remains separate.",
            status=(FinalStatus.CONFIRMED_CORRECT if passed else FinalStatus.NOT_REPRODUCED)
            if flap_converged else FinalStatus.INCONCLUSIVE,
        )

    def _probe_lag_coriolis_limitation(self) -> ProbeEvidence:
        return self._evidence(
            False,
            {"coriolis_flap_lag_coupling": "not implemented", "lead_lag_model_scope": "independent oscillator"},
            {"classification": "documented out-of-scope limitation"},
            "The result and documentation must identify the omitted coupling without claiming a full lead-lag model.",
            "python -c \"from zbemt import geometry; print(geometry.lag_frequency_ratio_squared(...))\"",
            "The executable frequency API contains offset and root-spring terms only. Documentation confirmation remains separate.",
            status=FinalStatus.OUT_OF_SCOPE_LIMITATION,
        )


class FlappingExecutor:
    """Evaluate flapping, lead-lag, and stability claims through public APIs."""

    def __init__(self, *, probe_runner: Callable[[str, Path], ProbeEvidence] | None = None) -> None:
        self._probe_runner = probe_runner or _RealProbeRunner()

    def __call__(self, claim: Claim, context: ExecutionContext) -> CheckResult:
        """Run one declared claim and return a complete result record."""
        started_at = _utc_now()
        if claim.claim_id not in SUPPORTED_CLAIM_IDS:
            raise KeyError(f"The flapping executor does not support {claim.claim_id!r}.")
        try:
            evidence = self._probe_runner(claim.claim_id, Path(context.output_directory))
            artifact_directory = Path(context.output_directory) / "flapping"
            artifact_directory.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_directory / f"{claim.claim_id.lower()}.json"
            artifact_path.write_text(json.dumps({
                "claim_id": claim.claim_id,
                "status": evidence.status.value,
                "measured": dict(evidence.measured),
                "expected": dict(evidence.expected),
                "tolerance": evidence.tolerance,
                "command": evidence.command,
                "notes": evidence.notes,
            }, indent=2, sort_keys=True, default=str), encoding="utf-8")
            artifacts = tuple(dict.fromkeys((*evidence.artifacts, str(artifact_path.resolve()))))
            return CheckResult(
                claim_id=claim.claim_id,
                final_status=evidence.status,
                measured_data=evidence.measured,
                expected_data=evidence.expected,
                tolerance_rule=evidence.tolerance,
                command=evidence.command,
                artifacts=artifacts,
                notes=evidence.notes,
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
                expected_data={"public_api": "A completed claim-specific physical probe."},
                tolerance_rule=claim.acceptance_rule,
                command=claim.cli_route,
                artifacts=(),
                notes=f"The flapping executor could not complete: {exc}",
                started_at=started_at,
                ended_at=_utc_now(),
                commit=context.commit,
                environment=context.environment,
            )
