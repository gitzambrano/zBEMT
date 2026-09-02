"""Tests for the standardized dynamic-stall physics executor."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.physics_checks.ledger import CLAIMS
from tools.physics_checks.models import ExecutionContext, FinalStatus
from tools.physics_checks.dynamic_stall_executor import DynamicStallExecutor


class TestDynamicStallExecutor(unittest.TestCase):
    """The executor must classify each dynamic-stall claim from public results."""

    def _context(self, output_directory: Path) -> ExecutionContext:
        return ExecutionContext(output_directory, "test-commit", {"python": "test"})

    def test_every_dynamic_stall_claim_returns_a_complete_result(self):
        claims = [claim for claim in CLAIMS if claim.domain == "dynamic_stall"]
        self.assertEqual(len(claims), 21)
        with tempfile.TemporaryDirectory() as temporary_directory:
            context = self._context(Path(temporary_directory))
            executor = DynamicStallExecutor()
            results = [executor(claim, context) for claim in claims]

        self.assertEqual({result.claim_id for result in results},
                         {claim.claim_id for claim in claims})
        for result in results:
            self.assertIn(result.final_status, set(FinalStatus))
            self.assertTrue(result.measured_data, result.claim_id)
            self.assertTrue(result.expected_data, result.claim_id)
            self.assertTrue(result.tolerance_rule, result.claim_id)
            self.assertTrue(result.command, result.claim_id)
            self.assertTrue(result.notes, result.claim_id)
            self.assertEqual(result.commit, "test-commit")
            self.assertEqual(result.environment, {"python": "test"})

    def test_hover_invariance_uses_the_real_public_api(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A7")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["maximum_absolute_CT_change"], 1e-12)
        self.assertIn("api.run_case", result.command)
        self.assertTrue(result.artifacts)

    def test_method_agreement_is_limited_to_the_low_advance_envelope(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A8")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        differences = result.measured_data["relative_CT_differences"]
        self.assertLess(max(differences[:2]), 0.01)
        self.assertGreater(differences[-1], differences[1])

    def test_periodic_residual_decreases_and_warns_when_unsettled(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A5")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertGreater(result.measured_data["residual_2_revolutions"],
                           result.measured_data["residual_4_revolutions"])
        self.assertTrue(result.measured_data["warning_at_4_revolutions"])

    def test_the_frequency_method_reproduces_the_analytical_first_order_lag(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A2")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        record = result.measured_data["frequency_method"]
        self.assertLessEqual(record["frequency_amplitude_error"], 1e-4)
        self.assertLessEqual(record["frequency_phase_error"], 1e-4)
        self.assertTrue(
            result.measured_data["march_phase_lag_is_one_half_azimuth_step"])

    def test_the_step_response_is_the_exact_exponential(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A4")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["maximum_absolute_error"], 1e-12)

    def test_a_maneuver_threads_the_separation_state_without_a_reset(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A6")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["threaded_initial_residual"], 1e-12)
        self.assertGreater(result.measured_data["reset_initial_residual"],
                           result.measured_data["threaded_initial_residual"])

    def test_the_hysteresis_loop_turns_in_the_expected_direction(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A9")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertGreater(result.measured_data["rising_lift"],
                           result.measured_data["falling_lift"])

    def test_a_disabled_airfoil_section_keeps_the_static_polar(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A18")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        stations = result.measured_data["stations"]
        self.assertEqual(stations["0.95"]["maximum_lift_correction"], 0.0)
        self.assertAlmostEqual(stations["0.81"]["maximum_enabled_weight"], 0.12,
                               places=2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
