"""Tests for the flapping and stability physics executor."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.physics_checks.flapping_executor import (
    FlappingExecutor,
    ProbeEvidence,
    SUPPORTED_CLAIM_IDS,
)
from tools.physics_checks.ledger import CLAIMS
from tools.physics_checks.models import ExecutionContext, FinalStatus


class FakeProbeRunner:
    """Return explicit evidence without calling the numerical engine."""

    def __init__(self, *, fail: bool = False) -> None:
        self.claim_ids: list[str] = []
        self.fail = fail

    def __call__(self, claim_id: str, output_directory: Path) -> ProbeEvidence:
        self.claim_ids.append(claim_id)
        if self.fail:
            raise RuntimeError("controlled probe failure")
        return ProbeEvidence(
            status=FinalStatus.CONFIRMED_CORRECT,
            measured={"claim_id": claim_id, "observed": 1.0},
            expected={"required": 1.0},
            tolerance="The observed value must equal 1.0.",
            command=f"python physical-probe.py {claim_id}",
            artifacts=(str(output_directory / f"{claim_id}.json"),),
            notes="The fake probe satisfies its literal rule.",
        )


class TestFlappingExecutor(unittest.TestCase):
    """The executor must produce complete claim-specific records."""

    @staticmethod
    def _context(output_directory: Path) -> ExecutionContext:
        return ExecutionContext(output_directory, "test-commit", {"python": "test"})

    def test_supported_ids_match_all_three_claim_domains(self):
        expected = {
            claim.claim_id for claim in CLAIMS
            if claim.domain in {"flapping", "lead_lag", "stability_derivatives"}
        }
        self.assertEqual(SUPPORTED_CLAIM_IDS, expected)
        self.assertEqual(len(expected), 34)

    def test_every_supported_claim_returns_complete_evidence(self):
        claims = [claim for claim in CLAIMS if claim.claim_id in SUPPORTED_CLAIM_IDS]
        fake = FakeProbeRunner()
        executor = FlappingExecutor(probe_runner=fake)
        with tempfile.TemporaryDirectory() as temporary_directory:
            context = self._context(Path(temporary_directory))
            results = [executor(claim, context) for claim in claims]

        self.assertEqual(set(fake.claim_ids), SUPPORTED_CLAIM_IDS)
        for result in results:
            self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
            self.assertTrue(result.measured_data)
            self.assertTrue(result.expected_data)
            self.assertTrue(result.tolerance_rule)
            self.assertTrue(result.command)
            self.assertTrue(result.artifacts)
            self.assertTrue(result.started_at)
            self.assertTrue(result.ended_at)
            self.assertEqual(result.commit, "test-commit")
            self.assertEqual(result.environment, {"python": "test"})

    def test_probe_failure_is_inconclusive(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "FLAP-E3")
        executor = FlappingExecutor(probe_runner=FakeProbeRunner(fail=True))
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.INCONCLUSIVE)
        self.assertIn("controlled probe failure", result.notes)

    def test_frequency_claim_uses_the_real_geometry_api(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "FLAP-E1")
        executor = FlappingExecutor()
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["maximum_absolute_error"], 1e-12)
        self.assertIn("geometry.flap_frequency_ratio_squared", result.command)

    def test_rigid_lag_claim_uses_real_validation(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "FLAP-G5B")
        executor = FlappingExecutor()
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertTrue(result.measured_data["validation_rejected"])

    def test_hover_invariance_uses_the_physical_direct_axes(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DERIV-E1")
        executor = FlappingExecutor()
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(
            max(result.measured_data["normalized_residuals"].values()),
            1e-6,
        )

    def test_forward_damping_separates_aerodynamic_and_hub_moments(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DERIV-A3")
        executor = FlappingExecutor()
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLess(
            abs(result.measured_data["flap_aerodynamic_pitch_damping"]),
            abs(result.measured_data["rigid_aerodynamic_pitch_damping"]),
        )
        self.assertAlmostEqual(
            result.measured_data["flap_total_pitch_damping"],
            result.measured_data["flap_aerodynamic_pitch_damping"]
            + result.measured_data["flap_hub_pitch_damping"],
            places=8,
        )

    def test_rigid_dynamics_matches_the_plain_bemt_map(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "FLAP-E9")
        executor = FlappingExecutor()
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = executor(claim, self._context(Path(temporary_directory)))
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertEqual(result.measured_data["maximum_array_difference"], 0.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
