"""Verify the standardized public-CLI checks for the core BEMT domain."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.physics_checks.core_bemt_executor import (
    CLAIM_IDS,
    execute_core_bemt_claim,
)
from tools.physics_checks.ledger import select_claims
from tools.physics_checks.models import CheckResult, ExecutionContext, FinalStatus


class TestCoreBemtExecutorCoverage(unittest.TestCase):
    """Keep every canonical core-BEMT claim connected to an executor."""

    def test_executor_claim_ids_equal_the_domain_ledger(self):
        ledger_ids = {claim.claim_id for claim in select_claims(domains=["core_bemt"])}
        self.assertEqual(CLAIM_IDS, ledger_ids)
        self.assertEqual(len(CLAIM_IDS), 15)

    def test_executor_rejects_a_claim_from_another_domain(self):
        claim = select_claims(claim_ids=["PROP-T1"])[0]
        with tempfile.TemporaryDirectory() as directory:
            context = ExecutionContext(Path(directory), "test", {"runner": "unittest"})
            with self.assertRaisesRegex(ValueError, "Unsupported core BEMT claim"):
                execute_core_bemt_claim(claim, context)


class TestCoreBemtExecutorRealCli(unittest.TestCase):
    """Run representative theory, correction, and convention checks."""

    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.context = ExecutionContext(
            output_directory=Path(cls.temporary_directory.name),
            commit="test",
            environment={"interface": "public CLI"},
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def _execute(self, claim_id: str) -> CheckResult:
        claim = select_claims(claim_ids=[claim_id])[0]
        result = execute_core_bemt_claim(claim, self.context)
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

    def test_hover_closed_form_runs_through_public_cli(self):
        result = self._execute("BEMT-C1")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["relative_error"], 0.007)
        self.assertIn("-m zbemt.cli", result.command)

    def test_radial_drag_matches_independent_closed_form(self):
        result = self._execute("BEMT-C6")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["off_error"], 0.03)
        self.assertLessEqual(result.measured_data["on_error"], 0.03)

    def test_rotational_augmentation_is_gated_by_stall(self):
        result = self._execute("BEMT-C11")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["hover_CT_relative_change"], 1e-12)
        self.assertGreater(result.measured_data["stalled_forward_CT_relative_change"], 0.0)

    def test_angle_identity_uses_cli_velocities(self):
        result = self._execute("BEMT-H2")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["rotor_error_deg"], 0.001)
        self.assertLessEqual(result.measured_data["disk_error_deg"], 0.001)

    def test_solver_agreement_uses_one_isolated_physical_root(self):
        result = self._execute("BEMT-C9")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["relative_span"], 0.0005)

    def test_attached_hover_rotational_augmentation_is_inactive(self):
        result = self._execute("BEMT-C11")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertLessEqual(result.measured_data["hover_CT_relative_change"], 1e-12)
        self.assertGreater(result.measured_data["stalled_forward_CT_relative_change"], 0.0)


if __name__ == "__main__":
    unittest.main()
