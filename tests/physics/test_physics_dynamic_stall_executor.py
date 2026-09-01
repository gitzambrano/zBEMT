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

    def test_missing_source_fixture_is_inconclusive_instead_of_guessed(self):
        claim = next(claim for claim in CLAIMS if claim.claim_id == "DS-A2")
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = DynamicStallExecutor()(claim, self._context(Path(temporary_directory)))

        self.assertEqual(result.final_status, FinalStatus.INCONCLUSIVE)
        self.assertIn("source fixture", result.notes.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
