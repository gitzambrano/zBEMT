"""Tests for the model-limitation, reporting, and product-quality executors.

These five executors close the claim groups that had no executor at all:
declared model limits, marched-result reporting, input validation,
repository quality, and the Snel stall-delay ratio.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.physics_checks.input_validation_executor import execute_input_validation_claim
from tools.physics_checks.ledger import CLAIMS
from tools.physics_checks.model_limitation_executor import ModelLimitationExecutor
from tools.physics_checks.models import ExecutionContext, FinalStatus
from tools.physics_checks.registry import build_executor_registry
from tools.physics_checks.reporting_executor import ReportingExecutor
from tools.physics_checks.repository_quality_executor import (
    execute_repository_quality_claim,
)
from tools.physics_checks.stall_delay_executor import execute_stall_delay_claim


CLAIMS_BY_ID = {claim.claim_id: claim for claim in CLAIMS}


def _context(output_directory: Path) -> ExecutionContext:
    return ExecutionContext(output_directory, "test-commit", {"python": "test"})


def _run(executor, claim_id: str):
    with tempfile.TemporaryDirectory() as temporary_directory:
        return executor(CLAIMS_BY_ID[claim_id], _context(Path(temporary_directory)))


class TestEveryClaimHasAnExecutor(unittest.TestCase):
    """No claim may stay unexecuted because its executor name is unknown."""

    def test_the_registry_resolves_every_declared_executor_name(self):
        registry = build_executor_registry()
        missing = sorted({claim.executor_name for claim in CLAIMS
                          if registry.get(claim.executor_name) is None})
        self.assertEqual(missing, [])


class TestModelLimitationExecutor(unittest.TestCase):
    """Each declared limit must be measured, not asserted."""

    def test_every_model_limitation_claim_returns_a_complete_result(self):
        claims = [claim for claim in CLAIMS
                  if claim.domain == "model_limitation"]
        self.assertTrue(claims)
        executor = ModelLimitationExecutor()
        with tempfile.TemporaryDirectory() as temporary_directory:
            context = _context(Path(temporary_directory))
            results = [executor(claim, context) for claim in claims]
        for result in results:
            self.assertIn(result.final_status, set(FinalStatus))
            self.assertTrue(result.measured_data, result.claim_id)
            self.assertTrue(result.notes, result.claim_id)
            self.assertTrue(result.artifacts, result.claim_id)

    def test_the_phase_convention_reproduces_the_documented_inflow_field(self):
        result = _run(ModelLimitationExecutor(), "PP-PHASE-CONVENTION")
        self.assertEqual(result.final_status, FinalStatus.OUT_OF_SCOPE_LIMITATION)
        self.assertLessEqual(
            result.measured_data["state_to_axis_mapping_error"], 1e-12)
        self.assertLessEqual(
            result.measured_data["phase_rotation_field_error"], 1e-12)

    def test_the_reversed_inflow_fraction_is_reported_and_not_clamped(self):
        result = _run(ModelLimitationExecutor(), "PP-LINEAR-LIMITATION")
        self.assertEqual(result.final_status, FinalStatus.OUT_OF_SCOPE_LIMITATION)
        self.assertGreater(result.measured_data["measured_reversed_fraction"], 0.0)
        self.assertLess(result.measured_data["minimum_total_inflow"], 0.0)

    def test_a_derivative_study_carries_its_flap_convergence(self):
        result = _run(ModelLimitationExecutor(), "DERIV-A5")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        for record in result.measured_data["studies"].values():
            self.assertEqual(record["usable"], record["flap_converged"])


class TestReportingExecutor(unittest.TestCase):
    """A marched result must report its interval, substeps, and residual."""

    def test_the_separation_history_carries_three_axes(self):
        result = _run(ReportingExecutor(), "DS-MANEUVER-REPORTING")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertEqual(len(result.measured_data["history_shape"]), 3)
        self.assertEqual(result.measured_data["marched_steps"], 288)

    def test_every_marched_sample_reports_the_required_fields(self):
        result = _run(ReportingExecutor(), "PP-B9")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertTrue(all(result.measured_data["required_fields_present"].values()))
        self.assertTrue(result.measured_data["later_samples_have_substeps"])


class TestProductQualityExecutors(unittest.TestCase):
    """Validation, warning language, and the stall-delay ratio."""

    def test_a_non_positive_density_is_refused_by_the_public_interface(self):
        result = _run(execute_input_validation_claim, "PROP-K8")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        for record in result.measured_data.values():
            for mode in ("validate_only", "full_run"):
                self.assertNotEqual(record[mode]["exit_code"], 0)
                self.assertEqual(record[mode]["result_files"], [])

    def test_the_pitt_peters_warning_is_english(self):
        result = _run(execute_repository_quality_claim, "REPO-PITT-WARNING")
        self.assertEqual(result.final_status, FinalStatus.CONFIRMED_CORRECT)
        self.assertEqual(result.measured_data["portuguese_words_found"], [])
        self.assertTrue(result.measured_data["warning_exported_in_result_row"])

    def test_the_stall_delay_ratio_matches_its_published_form_in_axial_flow(self):
        result = _run(execute_stall_delay_claim, "STALL-DELAY-RATIO")
        self.assertEqual(result.final_status, FinalStatus.NOT_REPRODUCED)
        self.assertLessEqual(
            result.measured_data["axial_maximum_relative_difference"], 1e-12)
        self.assertLessEqual(
            result.measured_data["implemented_factor_maximum"], 1.0)
        self.assertGreater(
            result.measured_data["forward_published_factor_maximum"], 1.0)


if __name__ == "__main__":
    unittest.main()
