"""Tests for the quality-suite taxonomy and command orchestrator."""
from __future__ import annotations

import importlib.util
import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "tests"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSuiteManifest(unittest.TestCase):
    """The manifest must classify every discovered pytest file once."""

    def test_manifest_classifies_every_test_file_once(self):
        manifest_path = TESTS_DIR / "suite_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(set(manifest), {"architecture", "regression", "physics"})

        listed = [name for suite in manifest.values() for name in suite]
        discovered = {
            path.relative_to(ROOT).as_posix()
            for path in TESTS_DIR.rglob("test_*.py")
        }
        self.assertEqual(set(listed), discovered)
        self.assertEqual(len(listed), len(set(listed)))


class TestSuiteRunnerSelection(unittest.TestCase):
    """The isolated pytest runner must use the manifest selection."""

    @classmethod
    def setUpClass(cls):
        cls.runner = _load_module("run_all_tests_for_quality_test",
                                  TESTS_DIR / "run_all_tests.py")

    def test_architecture_selection_contains_only_architecture_files(self):
        selected = {path.name for path in self.runner.select_test_files("architecture")}
        self.assertEqual(selected, {
            "test_agent_instructions.py",
            "test_documentation.py",
            "test_user_facing_documentation.py",
            "test_every_field_has_a_popup.py",
            "test_gui_cli_parity.py",
            "test_help_content.py",
            "test_help_registry.py",
            "test_nomenclature_parity.py",
            "test_notation.py",
            "test_quality_orchestrator.py",
            "test_requirements_guardrails.py",
        })

    def test_fast_selection_contains_every_discovered_test_file(self):
        selected = {path.name for path in self.runner.select_test_files("fast")}
        discovered = {path.name for path in TESTS_DIR.rglob("test_*.py")}
        self.assertEqual(selected, discovered)

    def test_physics_selection_contains_only_physics_test_files(self):
        selected = {
            path.relative_to(ROOT).as_posix()
            for path in self.runner.select_test_files("physics")
        }
        # The manifest is the single assignment of a file to a suite, so
        # the selection is compared with it. A hardcoded list here broke
        # every time the physics evidence gained a module.
        manifest = json.loads(
            (TESTS_DIR / "suite_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(selected, set(manifest["physics"]))
        self.assertTrue(all(name.startswith("tests/physics/")
                            for name in selected))


class TestQualityCommandOrchestrator(unittest.TestCase):
    """The public quality command must report each delegated command."""

    @classmethod
    def setUpClass(cls):
        cls.orchestrator = _load_module(
            "run_quality_checks_for_quality_test",
            ROOT / "tools" / "run_quality_checks.py",
        )

    def test_all_suite_constructs_fast_then_physics_commands(self):
        commands = self.orchestrator.build_commands("all", "airfoil")
        self.assertEqual(commands, [
            [self.orchestrator.sys.executable,
             str(ROOT / "tests" / "run_all_tests.py"),
             "--suite", "fast", "-k", "airfoil"],
            [self.orchestrator.sys.executable,
             str(ROOT / "tools" / "run_physics_checks.py"),
             "-k", "airfoil"],
        ])

    def test_physics_suite_constructs_unit_and_campaign_commands(self):
        commands = self.orchestrator.build_commands("physics")
        self.assertEqual(commands, [
            [self.orchestrator.sys.executable,
             str(ROOT / "tests" / "run_all_tests.py"),
             "--suite", "physics"],
            [self.orchestrator.sys.executable,
             str(ROOT / "tools" / "run_physics_checks.py")],
        ])

    def test_command_text_quotes_an_argument_that_contains_a_space(self):
        command = ["python", r"C:\Quality Checks\run.py", "--suite", "fast"]
        expected = (self.orchestrator.subprocess.list2cmdline(command)
                    if os.name == "nt" else shlex.join(command))
        displayed = self.orchestrator._command_text(command)
        self.assertEqual(displayed, expected)
        # Windows list2cmdline uses double quotes; POSIX shlex.join uses
        # single quotes. The old assertion required Windows quoting even
        # on Linux CI, contradicting the expected value above.
        quoted_path = (r'"C:\Quality Checks\run.py"' if os.name == "nt"
                       else r"'C:\Quality Checks\run.py'")
        self.assertIn(quoted_path, displayed)

    def test_dry_run_writes_report_without_starting_subprocesses(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "quality-report.txt"
            with patch.object(self.orchestrator.subprocess, "run") as run:
                result = self.orchestrator.main([
                    "--suite", "all", "--dry-run", "--output", str(report_path),
                ])
            self.assertEqual(result, 0)
            run.assert_not_called()
            self.assertIn("DRY RUN", report_path.read_text(encoding="utf-8"))

    def test_keep_going_runs_later_command_after_a_failure(self):
        outcomes = iter([
            SimpleNamespace(returncode=1, stdout="fast failed\n", stderr=""),
            SimpleNamespace(returncode=0, stdout="physics passed\n", stderr=""),
        ])
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "quality-report.txt"
            with patch.object(self.orchestrator.subprocess, "run",
                              side_effect=lambda *args, **kwargs: next(outcomes)) as run:
                result = self.orchestrator.main([
                    "--suite", "all", "--keep-going", "--output", str(report_path),
                ])
            self.assertEqual(result, 1)
            self.assertEqual(run.call_count, 2)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("exit code: 1", report)
            self.assertIn("exit code: 0", report)

    def test_any_subprocess_failure_gives_a_nonzero_aggregate_status(self):
        result = SimpleNamespace(returncode=3, stdout="failed\n", stderr="")
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "quality-report.txt"
            with patch.object(self.orchestrator.subprocess, "run", return_value=result):
                status = self.orchestrator.main([
                    "--suite", "architecture", "--output", str(report_path),
                ])
        self.assertEqual(status, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
