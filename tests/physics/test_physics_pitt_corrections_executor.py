"""Verify the Pitt-Peters, correction, and extreme-condition executor."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.physics_checks.ledger import select_claims
from tools.physics_checks.models import CheckResult, ExecutionContext, FinalStatus
from tools.physics_checks.pitt_corrections_executor import (
    CLAIM_IDS,
    PittCorrectionsExecutor,
)


DOMAINS = ("pitt_peters", "model_effects", "extremes")


class TestPittCorrectionsExecutorCoverage(unittest.TestCase):
    """Keep each selected claim connected to the executor."""

    def test_claim_ids_equal_the_three_domain_ledgers(self):
        ledger_ids = {claim.claim_id for claim in select_claims(domains=DOMAINS)}
        self.assertEqual(CLAIM_IDS, ledger_ids)
        self.assertEqual(len(CLAIM_IDS), 28)

    def test_executor_rejects_a_claim_from_another_domain(self):
        claim = select_claims(claim_ids=["BEMT-C1"])[0]
        executor = PittCorrectionsExecutor()
        with tempfile.TemporaryDirectory() as directory:
            context = ExecutionContext(Path(directory), "test", {"runner": "unittest"})
            with self.assertRaisesRegex(ValueError, "Unsupported Pitt or correction claim"):
                executor(claim, context)


class TestPittCorrectionsExecutorRealInterfaces(unittest.TestCase):
    """Run representative analytical checks through real interfaces."""

    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.context = ExecutionContext(
            Path(cls.temporary_directory.name),
            "test",
            {"interface": "public CLI and Python API"},
        )
        cls.executor = PittCorrectionsExecutor()

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def _execute(self, claim_id: str) -> CheckResult:
        claim = select_claims(claim_ids=[claim_id])[0]
        result = self.executor(claim, self.context)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.claim_id, claim_id)
        self.assertTrue(result.command)
        self.assertTrue(result.artifacts)
        self.assertTrue(result.measured_data)
        self.assertTrue(result.expected_data)
        self.assertTrue(result.tolerance_rule)
        for artifact in result.artifacts:
            self.assertTrue(Path(artifact).is_file(), artifact)
        return result

    def test_hover_pitt_peters_reduces_to_momentum(self):
        result = self._execute("PP-B1")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["relative_error"], 1e-5)

    def test_pitt_peters_mass_matrix_matches_published_constants(self):
        result = self._execute("PP-MASS-MATRIX")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["maximum_error"], 1e-12)

    def test_stall_models_have_the_declared_polar_shapes(self):
        result = self._execute("MODEL-G1")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertTrue(result.measured_data["linear_unbounded"])
        self.assertTrue(result.measured_data["clip_clamped"])

    def test_coefficient_normalization_uses_dimensional_cli_loads(self):
        result = self._execute("EXT-D3")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["maximum_error"], 1e-12)

    def test_axial_model_form_difference_is_not_called_a_defect(self):
        result = self._execute("PROP-FA")
        self.assertEqual(result.final_status, FinalStatus.NOT_REPRODUCED)
        self.assertGreater(result.measured_data["maximum_relative_difference"], 0.05)

    def test_a_constant_march_settles_on_its_algebraic_fixed_point(self):
        result = self._execute("PP-B2")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(
            result.measured_data["maximum_absolute_difference"], 1e-6)

    def test_sideslip_turns_the_local_field_with_the_free_stream(self):
        result = self._execute("PP-G7")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        for record in result.measured_data["models"].values():
            self.assertAlmostEqual(record["measured_shift_deg"], 30.0,
                                   delta=record["azimuth_cell_deg"])

    def test_strong_climb_is_classified_as_the_declared_limitation(self):
        result = self._execute("EXT-D2")
        self.assertEqual(result.final_status, FinalStatus.OUT_OF_SCOPE_LIMITATION)

    def test_autorotation_balances_the_driving_and_retarding_torques(self):
        """Autorotation is a balance, and the claim is now that balance.

        The source report named a transition speed of 19 to 20 m/s for a
        fixture it did not preserve, so that constant certified nothing.
        What certifies the model is that the profile torque always retards,
        that the induced torque changes sign as the inflow tilts the lift
        forward, and that the two cancel where the shaft torque vanishes."""
        result = self._execute("EXT-D5")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        measured = result.measured_data
        self.assertTrue(all(value > 0.0 for value in measured["CPp"]),
                        "profile drag must retard at every axial speed")
        self.assertGreater(measured["CPi"][0], 0.0)
        self.assertLess(measured["CPi"][-1], 0.0)
        # Both terms alive, equal and opposite: the zero is a cancellation,
        # not two vanishing terms.
        self.assertGreater(abs(measured["CPi_at_crossing"]), 1e-9)
        self.assertGreater(abs(measured["CPp_at_crossing"]), 1e-9)
        self.assertLess(measured["relative_imbalance_at_crossing"], 1e-3)
        self.assertGreater(measured["crossing_speed_m_s"], 5.0)
        self.assertLess(measured["crossing_speed_m_s"], 12.0)

    def test_empirical_inflow_spread_is_not_called_an_implementation_defect(self):
        result = self._execute("PP-P6-THRUST")
        self.assertEqual(result.final_status, FinalStatus.NOT_REPRODUCED)


if __name__ == "__main__":
    unittest.main()
