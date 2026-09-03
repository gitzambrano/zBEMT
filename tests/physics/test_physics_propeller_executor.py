"""Tests for the standardized propeller physics executor."""
from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path

from tools.physics_checks.ledger import CLAIMS
from tools.physics_checks.models import CliRunResult, ExecutionContext, FinalStatus
from tools.physics_checks.propeller_executor import PropellerExecutor


ROOT = Path(__file__).resolve().parents[2]


def _option(arguments: tuple[str, ...], flag: str, default: str) -> str:
    if flag not in arguments:
        return default
    return arguments[arguments.index(flag) + 1]


def _setting(arguments: tuple[str, ...], name: str, default: str) -> str:
    prefix = f"{name}="
    for index, argument in enumerate(arguments):
        if argument == "--set" and index + 1 < len(arguments):
            value = arguments[index + 1]
            if value.startswith(prefix):
                return value[len(prefix):]
    return default


def _synthetic_row(arguments: tuple[str, ...]) -> dict[str, float | str]:
    rpm = float(_option(arguments, "--rpm", "2400"))
    radius = float(_option(arguments, "--geom-radius", "0.94"))
    blades = int(_option(arguments, "--geom-n-blades", "3"))
    collective = float(_option(arguments, "--collective", "0"))
    density = float(_setting(arguments, "config.rho", "1.225"))
    sound_speed = 340.294
    element_count = int(_setting(arguments, "config.Ne", "72"))
    azimuth_count = int(_setting(arguments, "config.Npsi", "36"))
    compressibility = _setting(arguments, "config.use_compressibility", "true") == "true"
    cd0 = float(_setting(arguments, "airfoil.cd0", "0.008"))
    axial_speed = float(_option(arguments, "--v-axial", "nan"))
    shaft_rate = rpm / 60.0
    diameter = 2.0 * radius
    if math.isnan(axial_speed):
        advance_ratio = float(_option(arguments, "--j-axial", "0"))
        axial_speed = advance_ratio * shaft_rate * diameter
    else:
        advance_ratio = axial_speed / (shaft_rate * diameter)
    cross_speed = float(_option(arguments, "--v-inplane", "0"))

    root_twist = float(_option(arguments, "--geom-twist-root", "42"))
    tip_twist = float(_option(arguments, "--geom-twist-tip", "18"))
    symmetric_twist = root_twist == 5.0 and tip_twist == 5.0
    if symmetric_twist:
        thrust_coefficient = 0.012 * (collective + 7.0) - 0.08 * advance_ratio
    else:
        thrust_coefficient = 0.229 + 0.02 * advance_ratio - 0.168 * advance_ratio**2
        thrust_coefficient += 0.003 * collective
        if collective >= 25.0 and advance_ratio == 0.0:
            thrust_coefficient = 0.18 - 0.002 * (collective - 25.0)

    loss_mode = _option(arguments, "--prandtl-loss-mode", "both")
    thrust_coefficient *= {"off": 1.10, "root": 1.09, "tip": 1.01, "both": 1.0}[loss_mode]
    solver = _option(arguments, "--solver", "newton")
    if solver == "aitken":
        thrust_coefficient *= 1.003
    thrust_coefficient *= (blades / 3.0) ** 0.8
    if compressibility:
        thrust_coefficient *= 1.0 + 0.05 * (radius - 0.94)
    thrust_coefficient *= 1.0 - 0.15 / element_count
    thrust_coefficient -= 0.05 * (cd0 - 0.008)
    thrust_coefficient += 0.00004 * cross_speed**2

    power_coefficient = (
        0.118 + 0.10 * advance_ratio - 0.05 * advance_ratio**2
        - 0.05 * advance_ratio**3 + 0.004 * collective
    )
    if symmetric_twist:
        power_coefficient = 0.10 * math.copysign(1.0, thrust_coefficient)
    profile_power_coefficient = 0.00005 + 0.018 * cd0
    omega = 2.0 * math.pi * shaft_rate
    thrust = thrust_coefficient * density * shaft_rate**2 * diameter**4
    power = power_coefficient * density * shaft_rate**3 * diameter**5
    torque = power / omega
    area = math.pi * radius**2
    if thrust > 0.0:
        ideal_induced = 0.5 * (
            math.sqrt(axial_speed**2 + 2.0 * thrust / (density * area)) - axial_speed
        )
        excess = 1.0 + max(0.0, 0.14 * (1.0 - max(0.0, advance_ratio) / 1.2))
        induced_speed = ideal_induced * excess
    else:
        ideal_induced = 0.0
        induced_speed = -1.0
    induced_power = thrust * (axial_speed + induced_speed) * 1.02
    efficiency = (
        advance_ratio * thrust_coefficient / power_coefficient
        if advance_ratio > 0.0 and thrust_coefficient > 0.0 and power_coefficient > 0.0
        else 0.0
    )
    figure_of_merit = (
        thrust_coefficient**1.5 / (math.sqrt(2.0) * power_coefficient)
        if thrust_coefficient > 0.0 and power_coefficient > 0.0 else 0.0
    )
    convergence = 98.6 if collective == 8.0 and advance_ratio == 0.0 else 100.0
    return {
        "J_z": advance_ratio,
        "Vz": axial_speed,
        "Vi": induced_speed,
        "Vz_total": axial_speed + induced_speed,
        "Thrust": thrust,
        "Torque": torque,
        "Power": power,
        "Power_i": induced_power,
        "H": cross_speed * 10.0,
        "My": -cross_speed * 20.0,
        "CT_prop": thrust_coefficient,
        "CP_prop": power_coefficient,
        "CPp": profile_power_coefficient,
        "eta_prop": efficiency,
        "FM": figure_of_merit,
        "convergence_pct": convergence,
        "cfg_rho_used": density,
        "rotor_R": radius,
        "rotor_D": diameter,
        "rotor_Omega": omega,
        "rotor_OmegaR": omega * radius,
        "rotor_rpm": rpm,
        # The disk angle is measured from the shaft, so it is zero in
        # straight axial flight and grows with the cross-flow speed.
        "alpha_disk_deg": math.degrees(math.atan2(cross_speed, axial_speed))
        if (cross_speed or axial_speed) else 0.0,
        "cfg_Ne": element_count,
        "cfg_Npsi": azimuth_count,
        "cfg_a_sound": sound_speed,
    }


class FakeCliRunner:
    """Return complete synthetic CLI records from literal physical rules."""

    def __init__(self, corrupt_power: bool = False, fail: bool = False) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.corrupt_power = corrupt_power
        self.fail = fail

    def __call__(self, project: Path, arguments, working_directory: Path) -> CliRunResult:
        normalized = tuple(arguments)
        self.calls.append(normalized)
        copied_project = working_directory / "project"
        copied_project.mkdir(parents=True)
        if self.fail:
            return CliRunResult("", "controlled CLI failure", 2, (), "fake command", copied_project)

        row = _synthetic_row(normalized)
        if self.corrupt_power:
            row["Power"] = float(row["Power"]) * 1.2
        csv_path = copied_project / "outputs" / "results.csv"
        csv_path.parent.mkdir(parents=True)
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return CliRunResult("completed\n", "", 0, (csv_path,), "fake command", copied_project)


class TestPropellerExecutor(unittest.TestCase):
    """The executor must evaluate every registered propeller claim."""

    def _context(self, output_directory: Path) -> ExecutionContext:
        return ExecutionContext(output_directory, "test-commit", {"python": "test"})

    def test_every_propeller_claim_returns_a_complete_result(self):
        claims = [claim for claim in CLAIMS if claim.domain == "propeller"]
        self.assertEqual(len(claims), 29)
        fake = FakeCliRunner()
        executor = PropellerExecutor(cli_runner=fake, source_project=ROOT / "projects" / "starter_propeller")
        with tempfile.TemporaryDirectory() as temporary_directory:
            results = [executor(claim, self._context(Path(temporary_directory))) for claim in claims]

        expected_statuses = {
            "PROP-N2": FinalStatus.CONFIRMED_CORRECT,
        }
        for result in results:
            self.assertEqual(
                result.final_status,
                expected_statuses.get(result.claim_id, FinalStatus.CONFIRMED_CORRECT),
                result.claim_id,
            )
            self.assertTrue(result.measured_data, result.claim_id)
            self.assertTrue(result.expected_data, result.claim_id)
            self.assertTrue(result.tolerance_rule, result.claim_id)
            self.assertTrue(result.command, result.claim_id)
            self.assertTrue(result.artifacts, result.claim_id)
            self.assertTrue(result.started_at, result.claim_id)
            self.assertTrue(result.ended_at, result.claim_id)
            self.assertEqual(result.commit, "test-commit")
            self.assertEqual(result.environment, {"python": "test"})
        self.assertLess(len(fake.calls), 80)

    def test_shared_case_cache_runs_an_identical_command_once(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "PROP-C14")
        fake = FakeCliRunner()
        executor = PropellerExecutor(cli_runner=fake, source_project=ROOT / "projects" / "starter_propeller")
        with tempfile.TemporaryDirectory() as temporary_directory:
            context = self._context(Path(temporary_directory))
            first = executor(claim, context)
            second = executor(claim, context)
        self.assertEqual(first.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertEqual(second.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertEqual(len(fake.calls), 1)

    def test_failed_identity_is_a_confirmed_defect(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "PROP-C14")
        executor = PropellerExecutor(
            cli_runner=FakeCliRunner(corrupt_power=True),
            source_project=ROOT / "projects" / "starter_propeller",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_DEFECT)

    def test_cli_failure_is_inconclusive(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "PROP-T1")
        executor = PropellerExecutor(
            cli_runner=FakeCliRunner(fail=True),
            source_project=ROOT / "projects" / "starter_propeller",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.INCONCLUSIVE)
        self.assertIn("controlled CLI failure", result.notes)

    def test_representative_identity_uses_the_real_public_cli(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "PROP-T1")
        executor = PropellerExecutor(source_project=ROOT / "projects" / "starter_propeller")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertIn("python", result.command.lower())
        self.assertTrue(result.artifacts)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
