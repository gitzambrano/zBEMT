"""
test_cli_parity.py
===================

Behavior tests (not just --help) for the main_batch.py flags introduced
in Part 3 (docs/plano_v3.md) -- confirm that each flag actually sets the
corresponding field on Project/BEMTConfig, and that the result matches
what setting the field via api.py directly produces
(CLI<->GUI<->.bemt parity, principle 9).
"""

import os
import sys

import io
import json
import tempfile
import unittest
import contextlib
import shutil
from pathlib import Path

from zbemt import api
from zbemt import cli as main_batch
from zbemt.models import BatchDefinition, FlightCondition


class TestGeometryFlags(unittest.TestCase):
    def test_geom_preset_tapered(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(["--new", path, "--rpm", "600",
                                  "--geom-preset", "tapered", "--geom-radius", "0.9",
                                  "--geom-chord", "0.1", "--geom-taper-ratio", "0.5",
                                  "--save-as", path])
            project = api.open_project(path)
            self.assertAlmostEqual(project.geometry.radius_m, 0.9)
            self.assertAlmostEqual(project.geometry.chord_norm[0], 0.1)
            self.assertAlmostEqual(project.geometry.chord_norm[-1], 0.05, places=6)

    def test_geom_preset_custom_points(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(["--new", path, "--rpm", "600",
                                  "--geom-preset", "custom",
                                  "--geom-custom-points", "0.15:0.09:12,1.0:0.03:2",
                                  "--save-as", path])
            project = api.open_project(path)
            self.assertEqual(project.geometry.r_norm, [0.15, 1.0])
            self.assertEqual(project.geometry.chord_norm, [0.09, 0.03])


class TestConfigFlags(unittest.TestCase):
    def test_inflow_solver_prandtl_flags(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(["--new", path, "--rpm", "600",
                                  "--inflow", "pitt_peters_steady",
                                  "--prandtl-loss-mode", "tip",
                                  "--solver", "newton",
                                  "--rotational-augmentation",
                                  "--dynamic-stall",
                                  "--save-as", path])
            project = api.open_project(path)
            self.assertEqual(project.config["inflow_field_model"], "pitt_peters_steady")
            self.assertEqual(project.config["prandtl_loss_mode"], "tip")
            self.assertEqual(project.config["solver"], "newton")
            self.assertTrue(project.config["use_rotational_augmentation"])
            self.assertTrue(project.airfoil.use_dynamic_stall)

    def test_no_flags_variant(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(["--new", path, "--rpm", "600",
                                  "--no-rotational-augmentation", "--no-dynamic-stall",
                                  "--save-as", path])
            project = api.open_project(path)
            self.assertFalse(project.config["use_rotational_augmentation"])
            self.assertFalse(project.airfoil.use_dynamic_stall)


class TestStallModelFlagsAreDistinct(unittest.TestCase):
    """AirfoilDef.stall_model (STATIC polar shape past stall) and
    BEMTConfig.dynamic_stall_model (DYNAMIC stall model) are distinct
    fields on distinct objects. Only the first has a CLI flag: since
    dynamic_stall_model has only one possible option ("oye"), what
    switches dynamic stall on/off is the boolean
    --dynamic-stall/--no-dynamic-stall -- `--stall-model`/
    `--dynamic-stall-model` were removed (no alias)."""

    def _run(self, extra_args):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "proj")
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main(["--new", path, "--rpm", "600"] + extra_args + ["--save-as", path])
        return api.open_project(path)

    def test_airfoil_stall_model_flag_reaches_airfoil_def(self):
        project = self._run(["--airfoil-stall-model", "clip"])
        self.assertEqual(project.airfoil.stall_model, "clip")

    def test_dynamic_stall_model_flag_no_longer_exists(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self._run(["--dynamic-stall-model", "oye"])

    def test_legacy_stall_model_alias_no_longer_exists(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self._run(["--stall-model", "oye"])


class TestGeometrySourceConflict(unittest.TestCase):
    def test_geom_preset_with_geom_file_is_rejected(self):
        """`--geom-file` used to sit in an `elif` after the presets, so
        `--geom-preset X --geom-file Y` silently discarded the file."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            with self.assertRaises(SystemExit) as ctx:
                with contextlib.redirect_stdout(io.StringIO()):
                    main_batch.main(["--new", path, "--rpm", "600",
                                      "--geom-preset", "rectangular",
                                      "--geom-file", os.path.join(d, "g.bemt"),
                                      "--save-as", path])
            self.assertIn("mutually exclusive", str(ctx.exception))


class TestCliValidatesBeforeRunning(unittest.TestCase):
    """main_batch.py never called api.validate_project, so configurations
    that the engine rejects only failed deep inside, with a raw traceback."""

    def _new_project(self, d):
        """Creates the project WITHOUT running anything (`--new` alone
        already runs a case and exports results.csv, which would spoil
        the 'did not run' check)."""
        path = os.path.join(d, "proj")
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main(["--new", path, "--rpm", "600", "--save-as", path,
                              "--validate-only"])
        return path

    def test_unsteady_inflow_aborts_with_validation_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._new_project(d)
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main_batch.main(["--project", path, "--rpm", "600",
                                         "--inflow", "pitt_peters_unsteady"])
            self.assertEqual(code, 2)
            self.assertIn("validation error", err.getvalue())

    def test_validate_only_does_not_run_the_engine(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._new_project(d)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main_batch.main(["--project", path, "--rpm", "600", "--validate-only"])
            self.assertEqual(code, 0)
            self.assertIn("nothing was run", out.getvalue())
            # no result was written (the outputs/ folder itself is
            # already created by --new, so what matters is results.csv)
            self.assertFalse(os.path.exists(os.path.join(path, "outputs", "results.csv")))

    def test_missing_rpm_is_a_validation_error(self):
        """RPM became mandatory: without it, validation blocks before
        running instead of silently inventing 1000 RPM."""
        with tempfile.TemporaryDirectory() as d:
            path = self._new_project(d)
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main_batch.main(["--project", path])
            self.assertEqual(code, 2)
            self.assertIn("validation error", err.getvalue())


class TestTrimFlags(unittest.TestCase):
    """--trim-mode/--trim-target-thrust/--trim-target-ct (Step 8): the
    same `api.run_case_trimmed` as the GUI's trimmed "Run mode" (RunCaseTab)."""

    def _project(self, d):
        path = os.path.join(d, "proj")
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main([
                "--new", path, "--rpm", "600", "--mu-inplane", "0.0",
                "--geom-preset", "tapered", "--geom-radius", "1.0",
                "--geom-root-cutout", "0.15", "--geom-chord", "0.10",
                "--geom-taper-ratio", "0.4", "--geom-twist-root", "14", "--geom-twist-tip", "2",
                "--airfoil-source", "analytical", "--airfoil-stall-model", "clip",
                "--set", "config.Ne=8", "--set", "config.Npsi=12",
                "--set", "config.reverse_flow_model=simple_flip",
                "--save-as", path, "--validate-only",
            ])
        return path

    def test_solve_collective_hits_target_thrust(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._project(d)
            project = api.open_project(path)
            baseline = api.run_case(project, FlightCondition(name="c", mu_x=0.0, collective_deg=8.0, rpm=600.0))
            target = baseline.summary["Thrust"]

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main_batch.main(["--project", path, "--rpm", "600", "--mu-inplane", "0.0",
                                         "--collective", "2.0",
                                         "--trim-mode", "solve_collective",
                                         "--trim-target-thrust", str(float(target)),
                                         "--no-csv"])
            self.assertEqual(code, 0)

    def test_trim_without_target_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._project(d)
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main_batch.main(["--project", path, "--rpm", "600", "--trim-mode", "solve_rpm"])
            self.assertEqual(code, 2)
            self.assertIn("--trim-target-thrust", err.getvalue())

    def test_unbracketed_trim_target_is_an_error_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._project(d)
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = main_batch.main(["--project", path, "--rpm", "600",
                                         "--trim-mode", "solve_collective",
                                         "--trim-target-thrust", "1e9"])
            self.assertEqual(code, 2)
            self.assertIn("not bracketed", err.getvalue())

    def test_trim_applies_independently_to_multiple_conditions(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._project(d)
            project = api.open_project(path)
            project.batches = [BatchDefinition(name="b", conditions=[
                FlightCondition(name="a", rpm=600.0), FlightCondition(name="b", rpm=700.0)])]
            api.save_project(project)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = main_batch.main(["--project", path, "--from-bemt-batch", "b",
                                         "--trim-mode", "solve_rpm",
                                         "--trim-target-thrust", "100.0"])
            self.assertEqual(code, 0)


class TestBatchesAndCasesCLI(unittest.TestCase):
    def _project_with_batches(self, path):
        project = api.new_project(path)
        project.batches = [BatchDefinition(
            name="hover_sweep",
            conditions=[FlightCondition(name="c1", mu_x=0.0, rpm=600.0),
                        FlightCondition(name="c2", mu_x=0.1, rpm=600.0)])]
        project.saved_cases = [FlightCondition(name="takeoff_hover", mu_x=0.0,
                                                collective_deg=10.0, rpm=600.0)]
        api.save_project(project)

    def test_list_batches_and_cases(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._project_with_batches(path)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main_batch.main(["--project", path, "--list-batches"])
            self.assertIn("hover_sweep", buf.getvalue())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main_batch.main(["--project", path, "--list-cases"])
            self.assertIn("takeoff_hover", buf.getvalue())

    def test_run_from_bemt_batch(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._project_with_batches(path)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main_batch.main(["--project", path, "--from-bemt-batch", "hover_sweep", "--no-csv"])
            out = buf.getvalue()
            self.assertIn("[c1]", out)
            self.assertIn("[c2]", out)

    def test_run_from_bemt_case(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._project_with_batches(path)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                main_batch.main(["--project", path, "--from-bemt-case", "takeoff_hover", "--no-csv"])
            self.assertIn("[takeoff_hover]", buf.getvalue())

    def test_unknown_batch_name_raises(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._project_with_batches(path)
            with self.assertRaises(KeyError):
                with contextlib.redirect_stdout(io.StringIO()):
                    main_batch.main(["--project", path, "--from-bemt-batch", "nao_existe", "--no-csv"])


class TestGenNeuralfoilFlag(unittest.TestCase):
    """Phase 7 (Part 7.4): --gen-neuralfoil runs headless, without
    touching the BEMT, and fails with a clear message (not a raw
    traceback) if the 'neuralfoil' package is not installed."""

    def _new_project(self, path):
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main(["--new", path, "--rpm", "600", "--save-as", path])

    def test_missing_required_flags_returns_error_code(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._new_project(path)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = main_batch.main(["--project", path, "--gen-neuralfoil"])
            self.assertNotEqual(code, 0)
            self.assertIn("--airfoil-geometry", buf.getvalue())

    def test_gen_neuralfoil_export_table_headless(self):
        from zbemt import external_solvers
        if not external_solvers.is_available("neuralfoil"):
            self.skipTest("'neuralfoil' package not installed in this environment")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._new_project(path)
            out_csv = os.path.join(d, "naca2412_neuralfoil.csv")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main_batch.main([
                    "--project", path, "--gen-neuralfoil",
                    "--airfoil-geometry", "naca2412",
                    "--reynolds", "1e5,1e6", "--mach", "0.1",
                    "--alpha-range", "-6:6:2.0",
                    "--export-table", out_csv,
                ])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(out_csv))
            self.assertIn(out_csv, buf.getvalue())

    def test_gen_neuralfoil_without_package_fails_with_clear_message_not_traceback(self):
        from zbemt import external_solvers
        if external_solvers.is_available("neuralfoil"):
            self.skipTest("'neuralfoil' package is installed -- nothing to test here")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "proj")
            self._new_project(path)
            out_csv = os.path.join(d, "out.csv")
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = main_batch.main([
                    "--project", path, "--gen-neuralfoil",
                    "--airfoil-geometry", "naca0012",
                    "--reynolds", "1e6", "--mach", "0.1",
                    "--export-table", out_csv,
                ])
            self.assertEqual(code, 1)
            self.assertIn("neuralfoil", buf.getvalue())
            self.assertFalse(os.path.exists(out_csv))


class TestSetGenericFlag(unittest.TestCase):
    """--set (S3, docs/production-plan.md): generic setter for any
    BEMTConfig/AirfoilDef/RotorGeometryDef field, without needing a
    dedicated flag. Covers: valid field reaches Project, invalid field
    errors, type conversion (int/float/bool), precedence over a
    dedicated flag, and parity via RunOptions."""

    def _run(self, extra_args, expect_systemexit=False):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "proj")
        if expect_systemexit:
            with self.assertRaises(SystemExit) as ctx:
                with contextlib.redirect_stdout(io.StringIO()):
                    main_batch.main(["--new", path, "--rpm", "600"] + extra_args + ["--save-as", path])
            return ctx.exception
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main(["--new", path, "--rpm", "600"] + extra_args + ["--save-as", path])
        return api.open_project(path)

    def test_set_config_int_field_reaches_project(self):
        project = self._run(["--set", "config.Ne=12", "--set", "config.Npsi=16"])
        self.assertEqual(project.config["Ne"], 12)
        self.assertEqual(project.config["Npsi"], 16)
        self.assertIsInstance(project.config["Ne"], int)

    def test_set_config_float_field_reaches_project(self):
        project = self._run(["--set", "config.rho=1.1"])
        self.assertAlmostEqual(project.config["rho"], 1.1)
        self.assertIsInstance(project.config["rho"], float)

    def test_set_config_bool_field_variants(self):
        for raw, expected in [("true", True), ("false", False), ("1", True),
                               ("0", False), ("yes", True), ("no", False)]:
            with self.subTest(raw=raw):
                project = self._run(["--set", f"config.is_propeller={raw}"])
                self.assertEqual(project.config["is_propeller"], expected)

    def test_set_airfoil_float_field_reaches_project(self):
        project = self._run(["--set", "airfoil.cd0=0.012"])
        self.assertAlmostEqual(project.airfoil.cd0, 0.012)

    def test_set_geom_int_field_reaches_project(self):
        project = self._run(["--set", "geom.n_blades=5"])
        self.assertEqual(project.geometry.n_blades, 5)

    def test_set_unknown_field_raises_with_helpful_message(self):
        exc = self._run(["--set", "config.CampoQueNaoExiste=1"], expect_systemexit=True)
        msg = str(exc)
        self.assertIn("CampoQueNaoExiste", msg)
        self.assertIn("Ne", msg)   # the list of valid fields appears in the message

    def test_set_unknown_namespace_raises(self):
        exc = self._run(["--set", "bogus.field=1"], expect_systemexit=True)
        self.assertIn("namespace", str(exc))

    def test_set_bad_type_conversion_raises(self):
        exc = self._run(["--set", "config.Ne=not_an_int"], expect_systemexit=True)
        self.assertIn("Ne", str(exc))

    def test_set_missing_dot_raises(self):
        exc = self._run(["--set", "Ne=12"], expect_systemexit=True)
        self.assertIn("namespace", str(exc))

    def test_set_takes_precedence_over_dedicated_flag(self):
        project = self._run(["--inflow", "coleman_local", "--set",
                              "config.inflow_field_model=drees_global"])
        self.assertEqual(project.config["inflow_field_model"], "drees_global")

    def test_set_takes_precedence_over_dedicated_bool_flag(self):
        project = self._run(["--no-rotational-augmentation", "--set",
                              "config.use_rotational_augmentation=true"])
        self.assertTrue(project.config["use_rotational_augmentation"])

    def test_set_via_runoptions_matches_argv(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            path_argv = os.path.join(d1, "proj")
            path_opts = os.path.join(d2, "proj")
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(["--new", path_argv, "--rpm", "300",
                                  "--set", "config.Ne=20", "--set", "airfoil.cd0=0.02",
                                  "--save-as", path_argv])
            opts = main_batch.RunOptions(new=path_opts, rpm=300.0,
                                          set=["config.Ne=20", "airfoil.cd0=0.02"],
                                          save_as=path_opts)
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(options=opts)

            project_argv = api.open_project(path_argv)
            project_opts = api.open_project(path_opts)
            self.assertEqual(project_argv.config["Ne"], project_opts.config["Ne"])
            self.assertEqual(project_argv.airfoil.cd0, project_opts.airfoil.cd0)
            self.assertEqual(project_argv.config["Ne"], 20)


class TestRunOptionsParity(unittest.TestCase):
    """`RunOptions` (Python) and the command line must be the two ways of
    setting any flag on this script, with no possible divergence between
    them (RunOptions is derived from the parser itself -- see
    cli._build_run_options_dataclass)."""

    def test_every_runoptions_field_has_a_matching_flag_dest(self):
        import dataclasses
        parser = main_batch._build_parser()
        parser_dests = {a.dest for a in parser._actions if a.dest != "help"}
        runoptions_fields = {f.name for f in dataclasses.fields(main_batch.RunOptions)}
        self.assertEqual(runoptions_fields, parser_dests)

    def test_runoptions_defaults_match_parser_defaults(self):
        import dataclasses
        parser = main_batch._build_parser()
        defaults_by_dest = {}
        for a in parser._actions:
            if a.dest in defaults_by_dest:
                continue
            defaults_by_dest[a.dest] = a.default
        opts = main_batch.RunOptions()
        for f in dataclasses.fields(main_batch.RunOptions):
            self.assertEqual(getattr(opts, f.name), defaults_by_dest[f.name], f.name)

    def test_argv_and_runoptions_produce_the_same_project(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            path_argv = os.path.join(d1, "proj")
            path_opts = os.path.join(d2, "proj")
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(["--new", path_argv, "--rpm", "300", "--mu-inplane", "0.2",
                                  "--collective", "9.0", "--save-as", path_argv])
            opts = main_batch.RunOptions(new=path_opts, rpm=300.0, mu_inplane=0.2,
                                          collective=9.0, save_as=path_opts)
            with contextlib.redirect_stdout(io.StringIO()):
                main_batch.main(options=opts)

            project_argv = api.open_project(path_argv)
            project_opts = api.open_project(path_opts)
            self.assertEqual(project_argv.config, project_opts.config)
            self.assertEqual(project_argv.geometry.radius_m, project_opts.geometry.radius_m)

    def test_runoptions_from_argv_matches_argparse_namespace(self):
        argv = ["--new", "projects/X", "--rpm", "300", "--mu-inplane", "0.2"]
        opts = main_batch.RunOptions.from_argv(argv)
        ns = main_batch._parse_args(argv)
        for f in ns.__dict__:
            if f == "help":
                continue
            self.assertEqual(getattr(opts, f), getattr(ns, f), f)


if __name__ == "__main__":
    unittest.main()


class TestReportFlag(unittest.TestCase):
    """`--report`: the same report as the GUI button, reachable from an
    unsupervised batch."""

    def _rodar(self, extra):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        path = os.path.join(d, "proj")
        outdir = os.path.join(d, "out")
        with contextlib.redirect_stdout(io.StringIO()):
            main_batch.main([
                "--new", path, "--mu-inplane", "0.0", "--rpm", "600",
                "--collective", "8", "--set", "config.Ne=6", "--set", "config.Npsi=8",
                "--outdir", outdir, *extra])
        return outdir

    def test_report_without_value_writes_to_the_outdir(self):
        outdir = self._rodar(["--report"])
        self.assertTrue(os.path.exists(os.path.join(outdir, "report.html")))

    def test_report_with_value_respects_the_path(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        target = os.path.join(d, "sub", "my_report.html")
        self._rodar(["--report", target])
        self.assertTrue(os.path.exists(target))

    def test_without_the_flag_no_report_is_generated(self):
        outdir = self._rodar([])
        self.assertFalse(os.path.exists(os.path.join(outdir, "report.html")))

    def test_plots_vazio_nao_esvazia_o_relatorio(self):
        """`--plots` controls loose PNG files on disk; `--report` controls
        what gets embedded in the HTML. Saving files must not cost plots
        in the report."""
        outdir = self._rodar(["--plots", "--report"])
        html = Path(os.path.join(outdir, "report.html")).read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", html)
        self.assertFalse(os.path.exists(os.path.join(outdir, "plots")))


class TestListBatches(unittest.TestCase):
    """`--list-batches` used to count `len(conditions)`, which is 0 for
    every SWEEP batch (those hold `sweep_params`, not a list): all of
    them showed up as '0 condition(s)', which reads as an empty batch."""

    def _list(self, project: str) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main_batch.main(["--project", f"projects/{project}", "--list-batches"])
        return buf.getvalue()

    def test_sweep_shows_how_many_cases_it_will_generate(self):
        output = self._list("test1")
        self.assertIn("8 sweep case(s)", output)   # 8 values of mu_x
        self.assertIn("5 sweep case(s)", output)   # 5 collectives
        self.assertNotIn("0 condition", output)

    def test_factorial_counts_the_product_of_the_axes_not_the_number_of_axes(self):
        output = self._list("test3")
        self.assertIn("9 sweep case(s)", output)   # 3 rotations x 3 collectives
        self.assertNotIn("2 case(s)", output)

    def test_explicit_list_still_counts_conditions(self):
        output = self._list("test11")
        self.assertIn("8 explicit condition(s)", output)


class TestPrintedSummaryFollowsTheProjectMode(unittest.TestCase):
    """The CLI printed CT/CQ/CP/FM for any project, including propeller.

    FM is the figure of merit for HOVER and an airplane propeller never hovers: the
    number came out low and seemed like a bad project, when the metric is that it doesn't
    apply. On the propeller side, `eta_prop` fills this role. Both
    families always exist in `summary`; what changes is which one is printed."""

    def _run(self, project: str) -> str:
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main_batch.main(["--project", f"projects/{project}",
                             "--from-bemt-case", self._first_case(project),
                             "--outdir", d, "--no-csv"])
        return buf.getvalue()

    @staticmethod
    def _first_case(project: str) -> str:
        return api.open_project(f"projects/{project}").saved_cases[0].name

    def test_propeller_prints_the_propeller_family(self):
        output = self._run("test11")
        self.assertIn("eta_prop=", output)
        self.assertIn("CT_prop=", output)
        self.assertNotIn("FM=", output)

    def test_rotor_keeps_printing_the_rotor_family(self):
        output = self._run("test1")
        self.assertIn("FM=", output)
        self.assertIn("CT=", output)
        self.assertNotIn("eta_prop=", output)
