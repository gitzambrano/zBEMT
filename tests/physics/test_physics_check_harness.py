"""Tests for the physics-check ledger and execution harness."""
from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.physics_checks.cli_helper import run_cli_in_project_copy
from tools.physics_checks.ledger import CLAIMS, SOURCE_INVENTORY, select_claims
from tools.physics_checks.models import (
    CheckResult,
    Claim,
    EvidenceGrade,
    FinalStatus,
    SourceReference,
)
from tools.physics_checks.registry import ExecutorRegistry, build_executor_registry
from tools.physics_checks.runner import run_campaign


ROOT = Path(__file__).resolve().parents[2]
SOURCE_REPORTS = {
    "report_propeller_vs_literature.md",
    "report_stability_derivatives_flapping.md",
    "report_stall_pittpeters.md",
    "docs/physics_audit_flapping_pittpeters.md",
    "docs/report_dynamic_stall_pitt_peters_review.md",
}


def _claim(claim_id: str, executor_name: str) -> Claim:
    return Claim(
        claim_id=claim_id,
        domain="test-domain",
        title=f"Test claim {claim_id}",
        source_references=(SourceReference("test-report.md", claim_id, "test-row"),),
        original_status="UNVERIFIED",
        requirement_codes=("QR-8",),
        evidence_grade=EvidenceGrade.UNVERIFIED,
        theory_reference_text="Compare the measured value with the independent reference value.",
        acceptance_rule="Accept when the absolute error is at most 0.01.",
        cli_route="Run the CLI test route.",
        gui_route="Open the GUI test route.",
        executor_name=executor_name,
    )


def _result(claim: Claim, status: FinalStatus) -> CheckResult:
    return CheckResult(
        claim_id=claim.claim_id,
        final_status=status,
        measured_data={"value": 1.0},
        expected_data={"value": 1.0},
        tolerance_rule="Absolute error <= 0.01.",
        command="fake-command",
        artifacts=(),
        notes="The fake executor completed.",
        started_at="2026-08-31T00:00:00+00:00",
        ended_at="2026-08-31T00:00:01+00:00",
        commit="test-commit",
        environment={"python": "test"},
    )


class TestSourceLedger(unittest.TestCase):
    """The static ledger must preserve and map every source occurrence."""

    def test_source_inventory_maps_each_occurrence_once(self):
        self.assertEqual({entry.report for entry in SOURCE_INVENTORY}, SOURCE_REPORTS)
        self.assertEqual(Counter(entry.report for entry in SOURCE_INVENTORY), {
            "report_propeller_vs_literature.md": 74,
            "report_stability_derivatives_flapping.md": 25,
            "report_stall_pittpeters.md": 20,
            "docs/physics_audit_flapping_pittpeters.md": 9,
            "docs/report_dynamic_stall_pitt_peters_review.md": 80,
        })
        occurrence_ids = [entry.occurrence_id for entry in SOURCE_INVENTORY]
        self.assertEqual(len(occurrence_ids), len(set(occurrence_ids)))

        claims_by_id = {claim.claim_id: claim for claim in CLAIMS}
        self.assertEqual(len(claims_by_id), len(CLAIMS))
        for entry in SOURCE_INVENTORY:
            self.assertIn(entry.canonical_claim_id, claims_by_id)
            matching_references = [
                reference
                for reference in claims_by_id[entry.canonical_claim_id].source_references
                if reference.report == entry.report
                and reference.original_id == entry.original_id
                and reference.locator == entry.locator
            ]
            self.assertEqual(len(matching_references), 1, entry.occurrence_id)

    def test_source_inventory_preserves_the_exact_occurrence_id_set(self):
        occurrence_ids = sorted(entry.occurrence_id for entry in SOURCE_INVENTORY)
        occurrence_digest = hashlib.sha256(
            "\n".join(occurrence_ids).encode("utf-8")
        ).hexdigest()
        self.assertEqual(len(occurrence_ids), 208)
        self.assertEqual(
            occurrence_digest,
            "758273cb6fd03302a470f38d8e3494aeecd550199e3cca65f78ad6f79056eeee",
        )

    def test_distinct_physical_assertions_are_not_declared_as_duplicates(self):
        entries = {entry.occurrence_id: entry for entry in SOURCE_INVENTORY}
        report = "report_propeller_vs_literature.md"
        expected_claim_ids = {
            f"{report}:heading:C14": "PROP-C14",
            f"{report}:heading:C13": "PROP-C13",
            f"{report}:verdict-summary-1:C14/C13": "PROP-POWER-SUMMARY",
            f"{report}:heading:T2a": "PROP-T2A",
            f"{report}:heading:T2b": "PROP-T2B",
            f"{report}:verdict-summary-1:T2a/T2b": "PROP-MOMENTUM-SUMMARY",
            f"{report}:heading:T3": "PROP-T3",
            f"{report}:heading:F5": "PROP-F5",
            f"{report}:verdict-summary-1:T3 / F5": "PROP-STATIC-SUMMARY",
            f"{report}:heading:T9a": "PROP-T9A",
            f"{report}:heading:T9b": "PROP-T9B",
            f"{report}:verdict-summary-1:T9a/T9b": "PROP-GEOMETRY-SUMMARY",
            "report_stall_pittpeters.md:pitt-peters-table:P5": "PP-P5-ASYMMETRY",
            "report_stall_pittpeters.md:pitt-peters-table:P6": "PP-P6-THRUST",
            "report_stall_pittpeters.md:dynamic-stall-table:D3": (
                "DS-D3-HYSTERESIS-DIRECTION"
            ),
            "report_stall_pittpeters.md:dynamic-stall-table:D3b": "DS-D3B-FADE-50",
            "docs/physics_audit_flapping_pittpeters.md:headed-check:The steady state and the march": (
                "PP-STEADY-MARCH-AUDIT"
            ),
            "docs/report_dynamic_stall_pitt_peters_review.md:section-B-table:B5": (
                "PP-B5-COMBINED"
            ),
        }
        for occurrence_id, claim_id in expected_claim_ids.items():
            with self.subTest(occurrence_id=occurrence_id):
                self.assertEqual(entries[occurrence_id].canonical_claim_id, claim_id)

        self.assertEqual(len(CLAIMS), 138)
        self.assertEqual(
            sum(entry.duplicate_of is not None for entry in SOURCE_INVENTORY),
            70,
        )

    def test_duplicates_resolve_to_an_existing_canonical_claim(self):
        duplicates = [entry for entry in SOURCE_INVENTORY if entry.duplicate_of]
        self.assertGreater(len(duplicates), 0)
        occurrence_ids = {entry.occurrence_id for entry in SOURCE_INVENTORY}
        for entry in duplicates:
            self.assertIn(entry.duplicate_of, occurrence_ids)
            canonical = next(
                item for item in SOURCE_INVENTORY
                if item.occurrence_id == entry.duplicate_of
            )
            self.assertEqual(entry.canonical_claim_id, canonical.canonical_claim_id)

    def test_claims_use_known_requirements_and_reproduction_routes(self):
        requirements = (ROOT / "docs" / "software_requirements.md").read_text(
            encoding="utf-8"
        )
        known_codes = set(re.findall(r"\b(?:SC|PR|AR|EN|PA|RP|DC|TB|QR)-\d+[a-z]?\b", requirements))
        for claim in CLAIMS:
            self.assertTrue(claim.requirement_codes, claim.claim_id)
            self.assertLessEqual(set(claim.requirement_codes), known_codes, claim.claim_id)
            self.assertTrue(claim.cli_route.strip(), claim.claim_id)
            self.assertTrue(claim.gui_route.strip(), claim.claim_id)
            self.assertEqual(claim.evidence_grade, EvidenceGrade.UNVERIFIED)
            self.assertEqual(claim.executor_name, f"{claim.domain}_executor")
        self.assertEqual({status.value for status in FinalStatus}, {
            "CONFIRMED_DEFECT",
            "CONFIRMED_CORRECT",
            "NOT_REPRODUCED",
            "INCONCLUSIVE",
            "OUT_OF_SCOPE_LIMITATION",
        })

    def test_claim_metadata_is_specific_to_the_physical_assertion(self):
        claims = {claim.claim_id: claim for claim in CLAIMS}
        generic_phrases = {
            "source" + " condition",
            "source" + " operating condition",
            "source" + " model",
            "source" + " project",
            "source" + " invalid value",
        }
        for claim in CLAIMS:
            combined_text = " ".join((
                claim.theory_reference_text,
                claim.acceptance_rule,
                claim.cli_route,
                claim.gui_route,
            )).casefold()
            for phrase in generic_phrases:
                self.assertNotIn(phrase, combined_text, claim.claim_id)
            self.assertIn("python -m zbemt.cli --project", claim.cli_route)

        self.assertIn("P = Q", claims["PROP-C14"].theory_reference_text)
        self.assertIn("0.1 W", claims["PROP-C14"].acceptance_rule)
        self.assertIn("--j-axial 0.6", claims["PROP-C14"].cli_route)
        self.assertIn("1.0 to 1.15", claims["PROP-K1"].acceptance_rule)
        self.assertIn("30", claims["PP-B7"].cli_route)
        self.assertEqual(
            claims["DERIV-NONDIM-RATES"].requirement_codes,
            ("SC-14", "QR-8"),
        )
        self.assertEqual(
            claims["LAG-CORIOLIS-LIMITATION"].requirement_codes,
            ("SC-11",),
        )
        self.assertFalse(any(
            "SC-5" in claim.requirement_codes for claim in CLAIMS
        ))

    def test_every_claim_has_claim_specific_reproduction_guidance(self):
        self.assertEqual(len({claim.cli_route for claim in CLAIMS}), len(CLAIMS))
        self.assertEqual(len({claim.gui_route for claim in CLAIMS}), len(CLAIMS))
        forbidden_fragments = {
            "option named by the claim",
            "model named by the claim",
            "setting named by the claim",
            "inspect the limitation fields",
            "--set geometry.",
        }
        for claim in CLAIMS:
            with self.subTest(claim_id=claim.claim_id):
                guidance = f"{claim.cli_route} {claim.gui_route}".casefold()
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, guidance)
                self.assertIn("python -m zbemt.cli --project", claim.cli_route)
                self.assertTrue(any(character.isdigit() for character in guidance))

    def test_gui_routes_name_the_owning_tab_and_possible_actions(self):
        claims = {claim.claim_id: claim for claim in CLAIMS}
        geometry_claims = {
            "DERIV-E2", "FLAP-E1", "FLAP-E2", "FLAP-E3", "FLAP-E6",
            "FLAP-G4", "FLAP-G5", "FLAP-G5B",
            "LAG-CORIOLIS-LIMITATION", "DERIV-A1",
        }
        for claim_id in geometry_claims:
            with self.subTest(claim_id=claim_id):
                self.assertIn("Geometry", claims[claim_id].gui_route)
                self.assertNotIn("In Config", claims[claim_id].gui_route)

        for claim_id in {"BEMT-C5", "BEMT-C12", "MODEL-G3"}:
            with self.subTest(claim_id=claim_id):
                self.assertIn("Airfoil", claims[claim_id].gui_route)
                self.assertNotIn("in Config", claims[claim_id].gui_route)

        rigid_lag_route = claims["FLAP-G5B"].gui_route
        self.assertIn("removes the inapplicable Lead-lag controls", rigid_lag_route)
        self.assertNotIn("select Rigid flap and enable Lead-lag", rigid_lag_route)
        self.assertIn("preview_polar", claims["MODEL-G1"].cli_route)
        self.assertIn("--collective 12", claims["MODEL-G1"].cli_route)

    def test_reproduction_guidance_matches_reviewed_claims_and_every_domain(self):
        claims = {claim.claim_id: claim for claim in CLAIMS}
        expected_fragments = {
            "BEMT-C1": (
                "--collective 4", "--collective 8", "--collective 12",
                "config.Ne=", "thrust coefficient", "Run Batch",
            ),
            "PP-B1": (
                "--mu-inplane 0", "--inflow pitt_peters_steady",
                "nu0", "CT", "Results",
            ),
            "MODEL-G1": (
                "--airfoil-stall-model linear", "--airfoil-stall-model clip",
                "--airfoil-stall-model enhanced", "--airfoil-stall-model viterna",
                "Airfoil", "35 degrees",
            ),
            "DERIV-A5": (
                "inputs/derivatives.bemt", "--derivatives", "0.15",
                "flap", "Stability Derivatives", "convergence",
            ),
            "FLAP-E12": (
                "--trim-mode solve_collective", "--trim-target-thrust 300",
                "trim_exhaustion_probe.py", "--max-iter 1", "trim_converged",
                "Run Case", "Results",
            ),
            "EXT-D1": (
                "--v-axial -12", "--v-axial 20", "CT",
                "Run Batch", "axial speed",
            ),
            "DERIV-A1": (
                "inputs/derivatives.bemt", "--derivatives hover-rates",
                "--lock-number 4", "--lock-number 16", "--hinge-offset 0.02",
                "Stability Derivatives", "rate matrix",
            ),
            "PROP-C13": (
                "--j-axial 0", "--j-axial 0.4", "--j-axial 0.8",
                "Power", "Thrust", "Vi", "Run Batch",
            ),
            "DS-A5": (
                "airfoil.dynamic_stall_time_march_revolutions=2",
                "airfoil.dynamic_stall_time_march_revolutions=4",
                "periodic residual", "Airfoil", "Results",
            ),
            "PROP-K8": (
                "--validate-only", "config.rho=-1", "Config", "validation",
            ),
            "FLAP-G5": (
                "--set geom.dynamics.lag_enabled=true", "8000", "100",
                "Geometry", "Lead-lag",
            ),
            "PP-B9": (
                "inputs/maneuvers.bemt", "--maneuver", "substep",
                "Transient", "periodic residual",
            ),
            "REPO-PITT-WARNING": (
                "--inflow pitt_peters_steady", "--mu-inplane 0.15",
                "warning", "Results",
            ),
            "STALL-DELAY-RATIO": (
                "--rotational-augmentation", "--collective 12",
                "Config", "rotational augmentation",
            ),
        }
        self.assertEqual(
            {claims[claim_id].domain for claim_id in expected_fragments},
            {claim.domain for claim in CLAIMS},
        )
        for claim_id, fragments in expected_fragments.items():
            guidance = f"{claims[claim_id].cli_route} {claims[claim_id].gui_route}"
            with self.subTest(claim_id=claim_id):
                for fragment in fragments:
                    self.assertIn(fragment, guidance)

    def test_selection_is_deterministic_and_supports_all_filters(self):
        claim = CLAIMS[0]
        selected = select_claims(
            claim_ids=[claim.claim_id],
            domains=[claim.domain],
            pattern=claim.title.split()[0],
        )
        self.assertEqual([item.claim_id for item in selected], [claim.claim_id])
        self.assertEqual(
            [item.claim_id for item in select_claims()],
            sorted(item.claim_id for item in CLAIMS),
        )


class TestCampaignRunner(unittest.TestCase):
    """The runner must preserve every selected result and its failure state."""

    def test_unimplemented_executor_is_inconclusive_without_harness_failure(self):
        claim = _claim("TEST-UNIMPLEMENTED", "unimplemented")
        with tempfile.TemporaryDirectory() as temporary_directory:
            outcome = run_campaign(
                [claim],
                ExecutorRegistry(),
                Path(temporary_directory),
                commit="test-commit",
                environment={"python": "test"},
            )
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(outcome.results[0].final_status, FinalStatus.INCONCLUSIVE)

    def test_default_registry_connects_completed_domain_executors(self):
        registry = build_executor_registry()
        for name in (
            "core_bemt_executor", "propeller_executor", "dynamic_stall_executor",
            "flapping_executor", "lead_lag_executor", "stability_derivatives_executor",
            "pitt_peters_executor", "model_effects_executor", "extremes_executor",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(registry.get(name))

    def test_executor_exception_is_recorded_and_later_claims_still_run(self):
        first = _claim("TEST-A", "broken")
        second = _claim("TEST-B", "correct")
        registry = ExecutorRegistry()

        def broken_executor(claim, context):
            raise RuntimeError("controlled executor failure")

        registry.register("broken", broken_executor)
        registry.register("correct", lambda claim, context: _result(claim, FinalStatus.CONFIRMED_CORRECT))

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            outcome = run_campaign(
                [second, first],
                registry,
                output,
                commit="test-commit",
                environment={"python": "test"},
            )
            payload = json.loads((output / "results.json").read_text(encoding="utf-8"))
            summary = (output / "summary.txt").read_text(encoding="utf-8")

        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(
            [result.claim_id for result in outcome.results],
            ["TEST-A", "TEST-B"],
        )
        self.assertEqual(outcome.results[0].final_status, FinalStatus.INCONCLUSIVE)
        self.assertIn("controlled executor failure", outcome.results[0].notes)
        self.assertEqual(payload["results"][0]["final_status"], "INCONCLUSIVE")
        self.assertEqual(set(payload["results"][0]), {
            "claim_id", "final_status", "measured_data", "expected_data",
            "tolerance_rule", "command", "artifacts", "notes", "started_at",
            "ended_at", "commit", "environment",
        })
        self.assertIn("TEST-B", summary)

    def test_confirmed_defect_changes_exit_only_when_requested(self):
        claim = _claim("TEST-DEFECT", "defect")
        registry = ExecutorRegistry()
        registry.register("defect", lambda item, context: _result(item, FinalStatus.CONFIRMED_DEFECT))
        with tempfile.TemporaryDirectory() as temporary_directory:
            normal = run_campaign(
                [claim], registry, Path(temporary_directory) / "normal",
                commit="test-commit", environment={"python": "test"},
            )
            strict = run_campaign(
                [claim], registry, Path(temporary_directory) / "strict",
                fail_on_defect=True, commit="test-commit", environment={"python": "test"},
            )
        self.assertEqual(normal.exit_code, 0)
        self.assertEqual(strict.exit_code, 1)

    def test_invalid_executor_final_status_is_an_execution_failure(self):
        claim = _claim("TEST-INVALID-STATUS", "invalid-status")
        registry = ExecutorRegistry()
        registry.register(
            "invalid-status",
            lambda item, context: _result(item, "INVALID_STATUS"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            outcome = run_campaign(
                [claim],
                registry,
                Path(temporary_directory),
                commit="test-commit",
                environment={"python": "test"},
            )

        self.assertEqual(outcome.exit_code, 1)
        self.assertEqual(outcome.execution_failures, 1)
        self.assertEqual(outcome.results[0].final_status, FinalStatus.INCONCLUSIVE)
        self.assertIn("final status", outcome.results[0].notes.casefold())


class TestCliHelper(unittest.TestCase):
    """The shared helper must invoke the public CLI from a project copy."""

    def test_helper_captures_command_process_output_and_generated_csv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            source_project = temporary_path / "source-project"
            source_project.mkdir()
            (source_project / "project.bemt").write_text("name: test\n", encoding="utf-8")
            work_directory = temporary_path / "work"

            def fake_run(command, **kwargs):
                copied_project = Path(command[command.index("--project") + 1])
                (copied_project / "generated.csv").write_text("value\n1\n", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="completed\n", stderr="")

            with patch("tools.physics_checks.cli_helper.subprocess.run", side_effect=fake_run):
                result = run_cli_in_project_copy(
                    source_project,
                    ["--rpm", "400"],
                    work_directory,
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "completed\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.generated_csv_paths), 1)
        self.assertEqual(result.generated_csv_paths[0].name, "generated.csv")
        self.assertIn(subprocess.list2cmdline([sys.executable, "-m", "zbemt.cli"]), result.command)

    def test_helper_rejects_project_and_destination_arguments(self):
        invalid_arguments = (
            ["--project", "elsewhere"],
            ["--project=elsewhere"],
            ["--new", "elsewhere"],
            ["--new=elsewhere"],
            ["--save-as", "elsewhere"],
            ["--save-as=elsewhere"],
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            source_project = temporary_path / "source-project"
            source_project.mkdir()
            for arguments in invalid_arguments:
                with self.subTest(arguments=arguments):
                    with patch("tools.physics_checks.cli_helper.subprocess.run") as run:
                        with self.assertRaisesRegex(ValueError, "reserved"):
                            run_cli_in_project_copy(
                                source_project,
                                arguments,
                                temporary_path / "work" / arguments[0].replace("=", "-"),
                            )
                    run.assert_not_called()

    def test_helper_rejects_working_directory_inside_source_project(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_project = Path(temporary_directory) / "source-project"
            source_project.mkdir()
            for work_directory in (source_project, source_project / "work"):
                with self.subTest(work_directory=work_directory):
                    with self.assertRaisesRegex(ValueError, "source project"):
                        run_cli_in_project_copy(source_project, [], work_directory)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
