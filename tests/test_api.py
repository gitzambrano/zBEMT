"""Verify the application boundary and project lifecycle.

The tests exercise project creation, save/load, validation, single-case and batch
execution, optional polar generation, result exports, report content, naming, and
output-directory handling. Fixtures provide temporary projects and model inputs;
assertions cover returned objects and serialized artifacts. Solver accuracy is tested
only through the dedicated physics and golden-result suites.
"""

import re
import os
import tempfile
import shutil
import unittest
from unittest import mock
from pathlib import Path

from zbemt import api
from zbemt import geometry
from zbemt import validation
from zbemt.viz import visualization
from zbemt.models import Project, AirfoilDef, FlightCondition, BatchDefinition, ProfileGeometry, Results
from tests.helpers import make_api_fast_project as _make_fast_project


class TestProjectLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project_path = str(Path(self.tmp.name) / "MyProject")

    def test_new_project_creates_files_on_disk(self):
        project = api.new_project(self.project_path)
        self.assertEqual(project.name, "MyProject")
        for fname in ("config.bemt", "geom.bemt", "airfoil.bemt", "batches.bemt"):
            self.assertTrue((Path(self.project_path) / "inputs" / fname).exists(), fname)

    def test_open_project_roundtrips_new_project(self):
        created = api.new_project(self.project_path)
        opened = api.open_project(self.project_path)
        self.assertEqual(opened.geometry, created.geometry)
        self.assertEqual(opened.airfoil, created.airfoil)
        self.assertEqual(opened.config["Ne"], created.config["Ne"])

    def test_open_project_with_missing_files_falls_back_to_defaults(self):
        empty_path = str(Path(self.tmp.name) / "empty")
        project = api.open_project(empty_path)
        self.assertEqual(project.config, {})
        self.assertIsNotNone(project.geometry)

    def test_save_project_persists_edits(self):
        project = api.new_project(self.project_path)
        project.geometry.n_blades = 6
        api.save_project(project)
        reopened = api.open_project(self.project_path)
        self.assertEqual(reopened.geometry.n_blades, 6)

    def test_list_projects(self):
        api.new_project(str(Path(self.tmp.name) / "ProjA"))
        api.new_project(str(Path(self.tmp.name) / "ProjB"))
        names = api.list_projects(self.tmp.name)
        self.assertEqual(names, ["ProjA", "ProjB"])

    def test_list_projects_missing_root_returns_empty(self):
        self.assertEqual(api.list_projects(str(Path(self.tmp.name) / "missing")), [])


class TestValidateProject(unittest.TestCase):
    def test_delegates_to_validation_module(self):
        project = Project(airfoil=AirfoilDef(source="table", table_slices=[]))
        issues = api.validate_project(project)
        self.assertTrue(any(i.level == "error" for i in issues))
        self.assertIsInstance(issues[0], validation.Issue)


class TestRunCaseAndBatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = _make_fast_project(str(Path(self.tmp.name) / "p"))

    def test_run_case(self):
        res = api.run_case(self.project, FlightCondition(name="c1", rpm=600.0))
        self.assertIsInstance(res, Results)
        self.assertIn("Thrust", res.summary)

    def test_run_batch_with_explicit_conditions(self):
        batch = BatchDefinition(conditions=[
            FlightCondition(name="a", mu_x=0.0, rpm=600.0), FlightCondition(name="b", mu_x=0.1, rpm=600.0),
        ])
        results = api.run_batch(self.project, batch)
        self.assertEqual(len(results), 2)

    def test_run_mu_sweep_and_benchmark_solvers_pass_through(self):
        results = api.run_mu_sweep(self.project, [0.0, 0.1], rpm=600.0)
        self.assertEqual(len(results), 2)
        bench = api.benchmark_solvers(self.project, FlightCondition(name="c", rpm=600.0), solvers=("fixed_point",))
        self.assertEqual(len(bench), 1)

    def test_run_case_trimmed_passes_through_to_studies(self):
        cond = FlightCondition(name="c1", mu_x=0.0, rpm=600.0)
        baseline = api.run_case(self.project, cond)
        res = api.run_case_trimmed(
            self.project, cond, trim_mode="solve_collective",
            target_kind="thrust", target_value=baseline.summary["Thrust"])
        self.assertAlmostEqual(res.summary["collective_deg"], cond.collective_deg, places=2)


class TestRunExternalPolar(unittest.TestCase):
    def test_raises_value_error_without_geometry(self):
        airfoil = AirfoilDef(external_engine="neuralfoil", geometry=None)
        with self.assertRaises(ValueError):
            api.run_external_polar(airfoil)

    def test_run_with_geometry_uses_neuralfoil(self):
        from zbemt import external_solvers
        airfoil = AirfoilDef(external_engine="neuralfoil",
                              geometry=ProfileGeometry(source="naca4", naca_code="0012"),
                              external_reynolds_list=[1e6], external_mach_list=[0.1])
        if external_solvers.is_available("neuralfoil"):
            self.skipTest("geometry without generated coordinates -- covered by test_external_solvers.py")
        # 'neuralfoil' not installed in this environment: fails with a clear
        # message, not a generic NotImplementedError nor a raw traceback.
        with self.assertRaises(RuntimeError):
            api.run_external_polar(airfoil)

    def test_run_external_polar_from_geometry_roundtrip_export_import(self):
        from zbemt import external_solvers
        from zbemt import airfoils
        if not external_solvers.is_available("neuralfoil"):
            self.skipTest("'neuralfoil' package not installed in this environment")
        geom = airfoils.generate_naca4("0012")
        slices = api.run_external_polar_from_geometry(
            geom, reynolds_list=[1e5, 1e6], mach_list=[0.1, 0.3],
            alpha_min_deg=-6, alpha_max_deg=6, alpha_step_deg=2.0,
        )
        self.assertGreater(len(slices), 0)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        csv_path = str(Path(tmp.name) / "naca0012_neuralfoil.csv")
        out = api.export_polar_table(slices, csv_path)
        self.assertTrue(Path(out).exists())

        axes = airfoils.detect_csv_axes(str(out))
        self.assertIsNotNone(axes["reynolds"])
        self.assertIsNotNone(axes["mach"])

        reimported = airfoils.import_polar_csv(str(out))
        reimported_conditions = {(s.reynolds, s.mach) for s in reimported}
        original_conditions = {(s.reynolds, s.mach) for s in slices}
        self.assertEqual(reimported_conditions, original_conditions)


class TestExportResults(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = _make_fast_project(str(Path(self.tmp.name) / "p"))
        self.results = [
            api.run_case(self.project, FlightCondition(name="c1", mu_x=0.0, rpm=600.0)),
            api.run_case(self.project, FlightCondition(name="c2", mu_x=0.1, rpm=600.0)),
        ]

    def test_csv_written_by_default(self):
        outdir = Path(self.tmp.name) / "out1"
        written = api.export_results(self.results, str(outdir))
        self.assertEqual(len(written), 1)
        self.assertTrue((outdir / "results.csv").exists())

    def test_save_csv_false_skips_csv(self):
        outdir = Path(self.tmp.name) / "out2"
        written = api.export_results(self.results, str(outdir), save_csv=False)
        self.assertEqual(written, [])
        self.assertFalse((outdir / "results.csv").exists())

    def test_performance_plot_written(self):
        outdir = Path(self.tmp.name) / "out3"
        written = api.export_results(self.results, str(outdir), plots=["performance"], save_csv=False)
        self.assertEqual(len(written), 1)
        self.assertTrue(Path(written[0]).exists())

    def test_disk_map_plot_one_per_condition(self):
        outdir = Path(self.tmp.name) / "out4"
        written = api.export_results(self.results, str(outdir), plots=["disk_map_CT"], save_csv=False)
        self.assertEqual(len(written), 2)  # one per condition (c1, c2)
        for f in written:
            self.assertTrue(Path(f).exists())

    def test_convergence_plot_one_per_condition(self):
        outdir = Path(self.tmp.name) / "out5"
        written = api.export_results(self.results, str(outdir), plots=["convergence"], save_csv=False)
        self.assertEqual(len(written), 2)

    def test_unknown_plot_kind_silently_ignored(self):
        outdir = Path(self.tmp.name) / "out6"
        written = api.export_results(self.results, str(outdir), plots=["does_not_exist"], save_csv=False)
        self.assertEqual(written, [])

    def test_single_result_not_in_list_also_works(self):
        outdir = Path(self.tmp.name) / "out7"
        written = api.export_results(self.results[0], str(outdir))
        self.assertTrue((outdir / "results.csv").exists())

    def test_3d_plots_skip_gracefully_without_pyvista(self):
        if visualization.is_available():
            self.skipTest("PyVista installed -- this test specifically covers its absence.")
        outdir = Path(self.tmp.name) / "out8"
        written = api.export_results(self.results, str(outdir), plots=["rotor_3d", "load_3d_Fn"],
                                      save_csv=False, project=self.project)
        self.assertEqual(written, [])  # nothing generated, but NO exception

    def test_rotor_3d_without_project_is_skipped(self):
        outdir = Path(self.tmp.name) / "out9"
        # even if pyvista were installed, without `project=` it must skip
        written = api.export_results(self.results, str(outdir), plots=["rotor_3d"], save_csv=False)
        self.assertEqual(written, [])

    # --- docs/plano_v3.md Part 4.3: flat layout (default) vs per_case ---

    def test_layout_flat_is_default_and_unchanged(self):
        """Zero regression (Part 4.3): omitting `layout` still writes
        one file per case directly in plots_dir, with the condition's
        LABEL as suffix (`api.condition_labels`: "Case N", plus the
        name when it distinguishes the conditions) -- the suffix used
        to be the raw `condition_name`, which collapsed same-named
        conditions into the same file."""
        outdir = Path(self.tmp.name) / "out_flat"
        written = api.export_results(self.results, str(outdir), plots=["disk_map_CT"], save_csv=False)
        names = sorted(Path(f).name for f in written)
        # "disk_map_CT" resolves via the alias (_DISK_MAP_FIELD_ALIASES) to
        # the real elementary field "Fn" (see api._DISK_MAP_FIELD_ALIASES) --
        # the file name reflects the resolved field, not the requested alias.
        self.assertEqual(names, ["disk_map_Fn_Case 1 - c1.png",
                                 "disk_map_Fn_Case 2 - c2.png"])
        for f in written:
            self.assertTrue(Path(f).exists())
            self.assertEqual(Path(f).parent, outdir / "plots")

    def test_layout_per_case_creates_one_subfolder_per_condition(self):
        outdir = Path(self.tmp.name) / "out_per_case"
        written = api.export_results(self.results, str(outdir), plots=["disk_map_CT"],
                                      save_csv=False, layout="per_case")
        self.assertEqual(len(written), 2)
        for f in written:
            p = Path(f)
            self.assertTrue(p.exists())
            self.assertEqual(p.name, "disk_map_Fn.png")   # no condition suffix
            self.assertIn(p.parent.name, ("Case 1 - c1", "Case 2 - c2"))   # 1 subfolder per case

    def test_layout_per_case_applies_to_full_disk_map_grid_and_convergence(self):
        outdir = Path(self.tmp.name) / "out_per_case_grid"
        written = api.export_results(self.results, str(outdir), plots=["disk_map", "convergence"],
                                      save_csv=False, layout="per_case")
        for f in written:
            p = Path(f)
            self.assertTrue(p.exists())
            self.assertIn(p.parent.name, ("Case 1 - c1", "Case 2 - c2"))
        basenames = {Path(f).name for f in written}
        self.assertIn("disk_map_grid.png", basenames)
        self.assertIn("convergence.png", basenames)


class TestExportResultsTabular(unittest.TestCase):
    """Bug: `export_results_tabular` delegated to `df.to_csv` without
    `float_format`, so a small CT (e.g. 8.279954294566177e-05) came out in
    full-precision scientific notation -- Excel (pt-BR regional settings)
    imports that as text, not a number."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.results = Results(summary={"CT": 8.279954294566177e-05, "CQ": 0.01234})

    def test_scientific_notation_expanded_to_fixed_point(self):
        outdir = Path(self.tmp.name) / "out"
        path = api.export_results_tabular(self.results, str(outdir), sep=",")
        content = Path(path).read_text()
        self.assertNotIn("e-0", content.lower())
        self.assertIn("0,0000827995", content)

    def test_csv_uses_semicolon_and_comma_decimal(self):
        outdir = Path(self.tmp.name) / "out"
        path = api.export_results_tabular(self.results, str(outdir), sep=",")
        header, row = Path(path).read_text().splitlines()[:2]
        self.assertIn(";", header)
        self.assertIn("0,01234", row)

    def test_existing_file_is_not_overwritten(self):
        outdir = Path(self.tmp.name) / "out"
        first = api.export_results_tabular(self.results, str(outdir), sep=",")
        second = api.export_results_tabular(self.results, str(outdir), sep=",")
        self.assertNotEqual(first, second)
        self.assertTrue(Path(first).exists())
        self.assertTrue(Path(second).exists())
        self.assertTrue(Path(second).name.endswith("(2).csv"))


class TestSanitizeFilename(unittest.TestCase):
    """Q2 -- condition names are free text, and factorial batch names are
    assembled as `f"{k}={v:g}"`. A perfectly common case like
    `alpha=-5:mu_x=0.2` contains `:`, legal in a name and ILLEGAL in a file
    name on Windows: the export used to blow up partway through an
    already-run batch."""

    def test_windows_illegal_characters_become_hyphen(self):
        for name, expected in [
            ("alpha=-5:mu_x=0.2", "alpha=-5-mu_x=0.2"),
            ("mu_x=0.2/J_x=0.6", "mu_x=0.2-J_x=0.6"),
            ("caso*normal?", "caso-normal-"),
            ('as"pas', "as-pas"),
            ("barra\\invertida", "barra-invertida"),
            ("pipe|aqui", "pipe-aqui"),
            ("menor<maior>", "menor-maior-"),
        ]:
            with self.subTest(name=name):
                self.assertEqual(api.sanitize_filename(name), expected)

    def test_replaces_instead_of_deleting(self):
        """Deleting would turn `mu_x=0.2/J_x=0.6` into `mu_x=0.2J=0.6`, which
        reads wrong. The separator has to survive as something."""
        self.assertIn("-", api.sanitize_filename("mu_x=0.2/J_x=0.6"))

    def test_windows_reserved_names(self):
        """`CON.png` fails on Windows even with an extension."""
        for reserved in ("CON", "PRN", "AUX", "NUL", "COM1", "LPT9", "con", "Com1"):
            with self.subTest(name=reserved):
                self.assertNotEqual(api.sanitize_filename(reserved).upper(), reserved.upper())

    def test_empty_or_spaces_only(self):
        for name in ("", "   ", None, "...", " . "):
            with self.subTest(name=name):
                self.assertEqual(api.sanitize_filename(name), "unnamed")

    def test_too_long_name_is_truncated(self):
        result = api.sanitize_filename("x" * 500)
        self.assertLessEqual(len(result), 80)
        self.assertTrue(result)

    def test_does_not_end_in_period_or_space(self):
        """Windows refuses a name ending in a period or a space."""
        for name in ("termina com ponto.", "termina com espaco ", "ambos . "):
            with self.subTest(name=name):
                result = api.sanitize_filename(name)
                self.assertFalse(result.endswith((".", " ")))

    def test_accents_are_preserved(self):
        """An accent is legal in a file name -- there is no reason to mutilate
        `condition_with_accent`."""
        self.assertEqual(api.sanitize_filename("condição ok"), "condição ok")

    def test_collision_gets_suffix(self):
        """Two DIFFERENT names can sanitize to the same text; without
        disambiguation, one would silently overwrite the other's file."""
        mapping = api.filename_map(["a:b", "a?b", "a*b"])
        self.assertEqual(len(set(mapping.values())), 3, f"collided: {mapping}")

    def test_collision_ignores_case(self):
        """The Windows file system is case-insensitive:
        `Caso` and `caso` are the same file."""
        mapping = api.filename_map(["Caso:1", "caso:1"])
        values = [v.lower() for v in mapping.values()]
        self.assertEqual(len(set(values)), 2, f"collided: {mapping}")

    def test_mapping_is_stable_for_same_name(self):
        """`_result_plot_path` is called once per FIELD per condition
        (twelve disk-map fields). The name has to come out the same every
        time, otherwise a case's files spread out over `_2`, `_3`…"""
        mapping = api.filename_map(["caso:1", "caso:2"])
        for _ in range(12):
            self.assertEqual(api.filename_map(["caso:1", "caso:2"]), mapping)

    def test_export_with_hostile_name_does_not_blow_up(self):
        """The test that matters: a batch with a Windows-illegal name has
        to export, not raise."""
        with tempfile.TemporaryDirectory() as d:
            project = _make_fast_project(os.path.join(d, "proj"))
            batch = BatchDefinition(conditions=[
                FlightCondition(name="alpha=-5:mu_x=0.2", mu_x=0.1, collective_deg=8.0, rpm=600.0),
                FlightCondition(name="mu_x=0.2/J_x=0.6", mu_x=0.2, collective_deg=8.0, rpm=600.0),
            ])
            results = api.run_batch(project, batch)
            written = api.export_results(results, outdir=os.path.join(d, "out"),
                                          plots=["disk_map_CT"], save_csv=False)
            self.assertTrue(written)
            for f in written:
                self.assertTrue(Path(f).exists())
                self.assertFalse(set(Path(f).name) & set(':*?"<>|'))


if __name__ == "__main__":
    unittest.main()


class TestGenerateReport(unittest.TestCase):
    """`api.generate_report`: the report is the final product that leaves
    zBEMT (email, attachment, presentation), so it has to be a single
    file and it has to say what was run."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = _make_fast_project(os.path.join(self.tmp, "proj"))
        cond = FlightCondition(name="hover", mu_x=0.0, collective_deg=8.0, rpm=600.0)
        self.results = [api.run_case(self.project, cond)]

    def test_report_is_a_single_file_without_external_dependency(self):
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project)
        html = Path(dest).read_text(encoding="utf-8")
        # no reference to a local file: sending the HTML by email without
        # a folder of PNGs alongside it has to keep working
        self.assertNotRegex(html, r'src="(?!data:)')
        self.assertEqual(
            [p.name for p in Path(self.tmp).iterdir() if p.suffix == ".png"], [])

    def test_report_fetches_no_external_stylesheet_or_script(self):
        """PR-5. An `<img>` is not the only way out of the file. A
        stylesheet in a `<link>`, a library in a `<script src>` or a web
        font each turn the report into a page that looks right on the
        machine that generated it and wrong -- or blank -- on the machine
        it was sent to, which is worse than an obvious missing image
        because nothing announces the failure."""
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project)
        html = Path(dest).read_text(encoding="utf-8")
        self.assertNotRegex(html, r"<link[^>]+rel=[\"']?stylesheet",
                            "report links an external stylesheet")
        self.assertNotRegex(html, r"<script[^>]+src=",
                            "report loads a script from outside itself")
        self.assertNotIn("@import", html, "report imports an external stylesheet")
        self.assertNotRegex(html, r"url\(\s*[\"']?https?:",
                            "report pulls an asset over the network")

    def test_each_page_of_the_split_report_is_self_sufficient(self):
        """The self-containment rule holds for the satellites too. They
        are the pages that carry the figures, so a satellite that
        referenced a PNG on disk would break exactly the part of the
        report a reader opens the split version for."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 7)]
        dest = os.path.join(self.tmp, "split.html")
        api.generate_report([api.run_case(self.project, c) for c in conds],
                             dest, project=self.project)
        pages = [Path(dest)] + sorted(Path(self.tmp).glob("split_*.html"))
        self.assertGreater(len(pages), 1, "the report did not split")
        for page in pages:
            body = page.read_text(encoding="utf-8")
            self.assertNotRegex(body, r'src="(?!data:)',
                                f"{page.name} references a file outside itself")
            self.assertNotRegex(body, r"<script[^>]+src=",
                                f"{page.name} loads an external script")
        # the only files produced are the HTML pages themselves
        loose = sorted(p.name for p in Path(self.tmp).iterdir()
                       if p.is_file() and p.suffix not in (".html",))
        self.assertEqual(loose, [], "report left loose asset files: " + str(loose))

    def test_exports_all_sections_in_a_single_pass(self):
        """Generation must not redraw each section separately."""
        dest = os.path.join(self.tmp, "single_report.html")
        with mock.patch("zbemt.api.export_results", return_value=[]) as export:
            api.generate_report(
                self.results, dest, project=self.project,
                plots=["blade_geometry", "airfoil_polar", "azimuth", "span",
                       "disk_map", "convergence"],
            )
        self.assertEqual(export.call_count, 1)

    def test_one_plot_failure_does_not_erase_the_other_sections(self):
        """An optional figure with an error must not eliminate the visual report."""
        dest = os.path.join(self.tmp, "report_with_fallback.html")
        with mock.patch(
            "zbemt.api.export_results",
            side_effect=[RuntimeError("invalid plot"), [], []],
        ) as export:
            api.generate_report(
                self.results, dest, project=self.project,
                plots=["azimuth", "span"],
            )
        self.assertEqual(export.call_count, 3)

    def test_header_records_mesh_solver_and_rotor(self):
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project)
        html = Path(dest).read_text(encoding="utf-8")
        cfg = self.project.config
        self.assertIn(f"Ne={cfg['Ne']}", html)
        self.assertIn(f"Npsi={cfg['Npsi']}", html)
        self.assertIn(cfg["solver"], html)
        self.assertIn(str(self.project.geometry.n_blades), html)

    def test_header_carries_geometry_and_airfoil_beyond_the_mesh(self):
        """"What was run" used to be too short: twist, chord, airfoil
        coefficients, and the reverse flow model did not show up -- the
        only way to know was to read the `.bemt` back."""
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project)
        html = Path(dest).read_text(encoding="utf-8")
        self.assertIn("Twist (root", html)
        self.assertIn("Chord c/R (root", html)
        self.assertIn("Reverse flow", html)
        self.assertIn("Stall angles", html)

    def test_table_columns_have_symbol_unit_and_tooltip(self):
        """A raw `CT`/`CQ` header is code jargon. The header has three
        layers: symbol with subscript (C_T), the UNIT on a second line
        ([-] made explicit for dimensionless, because an empty cell reads
        as "they forgot to fill it in"), and the full description in a
        tooltip.

        The tooltip is a shared `position: fixed` bubble, positioned by
        JS on mouseover (not the native `title=`, which only appears after
        ~1 s parked over the cell -- on a 50-column header of one letter
        each, that turns into a queue of waits; nor a local `::after` on
        the `<th>`, which gets clipped by `.tablewrap`'s
        `overflow-x: auto` -- see the comment in `_REPORT_CSS`)."""
        dest = os.path.join(self.tmp, "rel.html")
        conds = [FlightCondition(name=f"c{i}", mu_x=0.1 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 3)]
        many = [api.run_case(self.project, c) for c in conds]
        api.generate_report(many, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        self.assertIn("C<sub>T</sub>", html)
        self.assertIn('data-tip="Thrust coefficient', html)
        self.assertIn('class="tt"', html)
        # unit row: dimensional and dimensionless, both cases
        self.assertIn('<th class="un">[m/s]</th>', html)
        self.assertIn('<th class="un">[-]</th>', html)
        # the JS that reads `data-tip` and positions the bubble has to be
        # embedded, otherwise the attribute shows nothing on screen
        self.assertIn("tt-popup", html)
        self.assertIn("closest(\".tt\")", html)
        self.assertIn("<script>", html)

    def test_report_carries_the_polar_and_geometry_not_only_results(self):
        """A rotor report without the POLAR and without the GEOMETRY does
        not let you check the aerodynamic hypothesis that produced the
        numbers -- you had to reopen the GUI to see the polar that was
        used. Both are inputs and come before the results."""
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project)
        generated = {p.name for p in Path(self.tmp).glob("rel_*.html")}
        self.assertIn("rel_airfoil_polars.html", generated)
        self.assertIn("rel_blade_geometry.html", generated)

        polars_html = (Path(self.tmp) / "rel_airfoil_polars.html").read_text(encoding="utf-8")
        self.assertIn("lift coefficient vs angle of attack", polars_html)
        self.assertIn("drag vs lift (drag polar)", polars_html)
        geom = (Path(self.tmp) / "rel_blade_geometry.html").read_text(encoding="utf-8")
        self.assertIn("Blade planform", geom)
        self.assertIn("chord and twist", geom)

    def test_multi_section_polar_outputs_one_per_section(self):
        """With 2+ sections the engine IGNORES `project.airfoil` (see
        `airfoils.to_blade_airfoil`): drawing only it would show a polar
        that was not used. A set comes out PER SECTION, labeled with r/R."""
        from dataclasses import replace
        proj = replace(self.project, airfoil_sections=[
            replace(self.project.airfoil, r_norm=0.3, name="root"),
            replace(self.project.airfoil, r_norm=0.9, name="tip"),
        ])
        dest = os.path.join(self.tmp, "ms.html")
        api.generate_report(self.results, dest, project=proj,
                             plots=["airfoil_polar"])
        polars_html = (Path(self.tmp) / "ms_airfoil_polars.html").read_text(encoding="utf-8")
        # section suffix in the label: r0p30 / r0p90
        self.assertIn("r0p30", polars_html)
        self.assertIn("r0p90", polars_html)

    def test_polar_with_reynolds_and_mach_generates_one_figure_per_reynolds(self):
        """If the table sweeps Reynolds AND Mach (e.g. 3 Re x 3 M),
        overlaying the 9 combinations on a single chart makes it
        impossible to read. The report must split: ONE figure PER
        Reynolds (with one curve per Mach inside it), for each
        coefficient. The figure captions in the final report carry
        `Re=<value>` in the title."""
        from dataclasses import replace
        from zbemt.models import PolarSlice
        slices = []
        for re in (1e6, 2e6, 3e6):
            for m in (0.1, 0.3, 0.5):
                slices.append(PolarSlice(alpha_deg=[0, 5, 10], cl=[0, 0.5, 1.0],
                                          cd=[0.01, 0.015, 0.03],
                                          reynolds=re, mach=m))
        proj = replace(self.project, airfoil=replace(
            self.project.airfoil, source="table", table_slices=slices))
        dest = os.path.join(self.tmp, "rem.html")
        api.generate_report(self.results, dest, project=proj,
                             plots=["airfoil_polar"])
        polars_html = (Path(self.tmp) / "rem_airfoil_polars.html").read_text(encoding="utf-8")
        # three Cl-alpha figures, one per Reynolds value (appearing
        # via `_figure_caption` as "... -- Re<value>")
        import re as _re
        cl_marks = _re.findall(
            r"lift coefficient vs angle of attack -- Re[0-9]+", polars_html)
        self.assertEqual(len(cl_marks), 3,
                          f"expected 3 Cl-alpha captions (one per Re), got {cl_marks}")

    def test_reynolds_only_polar_remains_a_single_chart(self):
        """Regression: with only Reynolds varying (no Mach), the previous
        behavior was ONE figure per coefficient, several curves -- no
        regression wanted toward one figure per Re."""
        from dataclasses import replace
        from zbemt.models import PolarSlice
        slices = [PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02],
                              reynolds=re) for re in (1e6, 2e6, 3e6)]
        proj = replace(self.project, airfoil=replace(
            self.project.airfoil, source="table", table_slices=slices))
        dest = os.path.join(self.tmp, "solo.html")
        api.generate_report(self.results, dest, project=proj,
                             plots=["airfoil_polar"])
        polars_html = (Path(self.tmp) / "solo_airfoil_polars.html").read_text(encoding="utf-8")
        # ONE Cl-alpha caption WITHOUT the "-- Re<value>" suffix
        import re as _re
        cl_with_re = _re.findall(
            r"lift coefficient vs angle of attack -- Re[0-9]+", polars_html)
        self.assertEqual(cl_with_re, [], "Re-only polar should not break into one figure per value")
        self.assertIn("lift coefficient vs angle of attack", polars_html)

    def test_tabulated_polar_metadata_shows_reynolds_not_analytic_fields(self):
        """`source="table"` has no `cl_alpha`/`cd0` -- showing those
        fields there would be showing garbage from the wrong mode. It
        must show how many slices and which Reynolds are covered."""
        from dataclasses import replace
        from zbemt.models import PolarSlice
        slice_a = PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02], reynolds=1e6)
        slice_b = PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02], reynolds=2e6)
        proj = replace(self.project, airfoil=replace(
            self.project.airfoil, source="table", table_slices=[slice_a, slice_b]))
        dest = os.path.join(self.tmp, "tab.html")
        api.generate_report(self.results, dest, project=proj)
        html = Path(dest).read_text(encoding="utf-8")
        self.assertIn("Polar table", html)
        self.assertIn("2 slice(s)", html)
        self.assertIn("Reynolds", html)
        self.assertNotIn("C<sub>l,&alpha;</sub>", html)

    def test_polar_that_cannot_evaluate_does_not_crash_the_report(self):
        """`source="external"` raises `NotImplementedError` in
        `to_airfoil`. A polar that cannot be evaluated has to skip the
        section, not abort the whole generation."""
        from dataclasses import replace
        proj = replace(self.project,
                        airfoil=replace(self.project.airfoil, source="external"))
        dest = os.path.join(self.tmp, "ext.html")
        api.generate_report(self.results, dest, project=proj)   # does not raise
        self.assertTrue(Path(dest).exists())

    def test_config_does_not_pollute_the_main_table(self):
        """The ~40 `cfg_*` keys of `Results.summary` are identical across
        every condition; mixed in with the quantities, they push CT/CQ/FM
        out of view."""
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        main_html, _, appendix = html.partition("<details>")
        # The SYMBOL, not the letters "CT": the description is rendered
        # too (PR-4), so the raw pair no longer appears anywhere and an
        # assertion on it would pass on the tooltip rather than on the
        # column it is meant to be checking.
        self.assertIn("C<sub>T</sub>", main_html)
        self.assertNotIn("cfg_Ne", main_html)
        # the config echo lives in the appendix, already with its own
        # symbol (N<sub>e</sub>) instead of the raw field name
        self.assertNotIn("N<sub>e</sub>", main_html)
        self.assertIn("N<sub>e</sub>", appendix)

    def test_config_echo_has_vertical_header_and_own_symbol(self):
        """Raw field names (`reverse_flow_model`, `dynamic_stall_A`...)
        do not fit a 74px column horizontally -- truncating with an
        ellipsis hid almost the whole name. The echo table rotates the
        header (`.tablewrap.vert`).

        Every `cfg_*` now has its own SYMBOL and DESCRIPTION in
        `_COLUMN_SYMBOL` (coverage locked in by
        `test_every_column_has_symbol_and_tooltip`): it used to fall back to
        `chave.removeprefix("cfg_")`, which showed the raw field name as
        both symbol AND tooltip -- the tooltip explained nothing, it just
        repeated the header."""
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        main_html, _, appendix = html.partition("<details>")
        self.assertIn('class="tablewrap vert"', appendix)
        self.assertNotIn(">cfg_Ne<", appendix)
        self.assertIn("N<sub>e</sub>", appendix)
        # tooltip is the DESCRIPTION, no longer an echo of the field's own name
        self.assertIn('data-tip="Number of radial stations in the mesh"', appendix)

    def test_single_condition_uses_the_same_matrix_as_several(self):
        """A SINGLE orientation, always: one row per condition, one
        quantity per column. Before, a single case came out transposed
        (quantity|value in blocks) and a sweep came out matrix-style --
        two different tables for the same data, and the reader had to
        relearn the table each time the report changed. The sideways
        scrolling that motivated the transposition lives inside
        `.tablewrap`, not on the page."""
        dest = os.path.join(self.tmp, "rel_one.html")
        api.generate_report(self.results, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        self.assertIn(">C<sub>T</sub></th>", html)      # header, not a cell
        self.assertIn('<div class="tablewrap">', html)
        self.assertNotIn('<div class="blocos">', html)

    def test_several_conditions_follow_the_matrix_orientation(self):
        """With a sweep, the matrix orientation is the right one: one
        row per condition is what allows comparing."""
        from zbemt.models import FlightCondition
        conds = [FlightCondition(name=f"c{i}", mu_x=0.1 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 4)]
        many = [api.run_case(self.project, c) for c in conds]
        dest = os.path.join(self.tmp, "rel_many.html")
        api.generate_report(many, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        self.assertIn(">C<sub>T</sub></th>", html)
        self.assertIn("condition</th>", html)

    def test_without_project_still_generates_a_report(self):
        """`project` is optional: a script that only has the `Results` in
        hand can still produce a report (it loses the header, not the report)."""
        dest = os.path.join(self.tmp, "rel_no_project.html")
        api.generate_report(self.results, dest)
        self.assertIn("CT", Path(dest).read_text(encoding="utf-8"))

    def test_empty_list_is_an_explicit_error(self):
        with self.assertRaises(ValueError):
            api.generate_report([], os.path.join(self.tmp, "x.html"))

    def test_user_notes_appear(self):
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project, plots=[],
                            notes="test rotor, coarse mesh")
        self.assertIn("test rotor, coarse mesh",
                      Path(dest).read_text(encoding="utf-8"))


class TestReportSections(unittest.TestCase):
    """The order and content of the chart sections.

    The report used to delegate the whole list to `export_results` and
    sort by file name: only `performance` came out (which is CT x mu_x, a
    single panel), azimuth and span never came out, and the panel with the
    12 combined maps came BEFORE the individual maps, by alphabetical
    accident.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = _make_fast_project(os.path.join(self.tmp, "proj"))
        cond = FlightCondition(name="c", mu_x=0.2, collective_deg=8.0, rpm=600.0)
        self.single = [api.run_case(self.project, cond)]

    def _html(self, results, **kw):
        dest = os.path.join(self.tmp, "r.html")
        api.generate_report(results, dest, project=self.project, **kw)
        return Path(dest).read_text(encoding="utf-8")

    def _full_html(self, results, **kw):
        """Master + ALL satellites concatenated.

        The chart sections live in their own files next to the master
        (see `_FIGURES_BEFORE_OWN_FILE`). A test that only looks
        at the master does not see the figures -- and a test that switched
        to looking at only one satellite would stop checking that the
        SOMEWHERE in the report", which is the question most of these
        tests ask."""
        dest = Path(self.tmp) / "r.html"
        api.generate_report(results, str(dest), project=self.project, **kw)
        parts = [dest.read_text(encoding="utf-8")]
        parts += [p.read_text(encoding="utf-8")
                  for p in sorted(dest.parent.glob("r_*.html"))]
        return "\n".join(parts)

    def test_azimuth_and_span_enter_the_report(self):
        html = self._full_html(self.single)
        self.assertIn("Loads along azimuth", html)
        self.assertIn("Loads along blade span", html)

    def test_obsolete_satellite_does_not_survive_a_new_export(self):
        """A new export must not leave an old section reusable."""
        stale = Path(self.tmp) / "r_blade_geometry.html"
        stale.write_text("blade_loads_vs_span", encoding="utf-8")
        self._html(self.single)
        current = stale.read_text(encoding="utf-8") if stale.exists() else ""
        self.assertNotIn("blade_loads_vs_span", current)

    def test_individual_maps_come_before_the_panel_of_12(self):
        """The panel is a visual index: it serves to find a field already
        examined again, not to introduce it."""
        satellite = Path(self.tmp) / "r_disk_maps.html"
        self._html(self.single)
        body = satellite.read_text(encoding="utf-8")
        first_individual = body.index("Disk map -- drag coefficient")
        panel = body.index("Disk maps (all fields)")
        self.assertLess(first_individual, panel)

    def test_sweep_carries_the_coefficients_not_only_CT(self):
        conds = [FlightCondition(name=f"c{i}", mu_x=0.1 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 4)]
        html = self._html([api.run_case(self.project, c) for c in conds])
        self.assertIn("Performance coefficients", html)
        self.assertIn("Performance coefficients vs mu_x", html)

    def test_a_single_case_has_no_performance_curve(self):
        """A single point is not a curve."""
        self.assertNotIn("Performance coefficients", self._html(self.single))

    def test_figure_caption_is_readable_not_a_raw_file_name(self):
        """Each figure's caption is what explains the image to someone
        reading the report without having looked at the code -- a raw
        file name (`disk_map_Cd_c`) is internal jargon, not a caption."""
        html = self._full_html(self.single)
        self.assertIn("<figcaption>Loads along azimuth", html)
        self.assertIn("<figcaption>Loads along blade span", html)
        self.assertNotIn("<figcaption>loads_vs_azimuth", html)
        self.assertNotIn("<figcaption>blade_loads_vs_span", html)
        self.assertNotIn("<figcaption>disk_map_Cd_", html)

    def test_matrix_table_scrolls_within_itself_not_the_whole_page(self):
        """A wide table (many conditions/columns) has to scroll WITHIN
        itself (`.tablewrap { overflow-x: auto }`), not stretch the whole
        page -- otherwise the reader has to scroll sideways to read
        anything below the table too."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.1 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 4)]
        html = self._html([api.run_case(self.project, c) for c in conds])
        self.assertIn('<div class="tablewrap">', html)
        self.assertIn("max-width: 1600px", html)
        self.assertIn(".tablewrap { overflow-x: auto", html)

    def test_every_output_quantity_stays_on_the_conditions_row(self):
        """EVERY output quantity goes into the matrix, on its condition's
        row -- no separate `<details>` "Additional quantities per
        condition" block, which repeated each quantity's NAME once per
        condition and forced scrolling between distant blocks to compare
        the same quantity across two cases. Only the config echo
        (identical across every condition, hence not output) stays
        collapsed."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.1 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 4)]
        html = self._html([api.run_case(self.project, c) for c in conds])
        self.assertNotIn("Additional quantities per condition", html)

        matrix = html.split("<details>")[0]
        ordered, cfg = api._sorted_keys([api.run_case(self.project, conds[0])])
        # every non-cfg key has to be in the main matrix
        for key in ordered:
            symbol, _ = api._COLUMN_SYMBOL[key]
            self.assertIn(f">{symbol}</th>", matrix,
                           f"{key} left the main matrix")
        # and the config echo does NOT (stays in the <details>)
        self.assertTrue(cfg, "expected cfg_* keys to check the separation")
        self.assertNotIn(">cfg_Ne</th>", matrix)

    def test_every_column_has_symbol_and_tooltip(self):
        """The matrix shows 90+ columns with a one-to-two-letter header --
        without `title=`, there is no way to know what the column is. A
        new key in `Results.summary` (including `cfg_*`, the BEMTConfig
        echo -- no longer excluded from coverage, see
        `_column_header`) with no entry in `_COLUMN_SYMBOL` would
        show up as raw `snake_case` amid the symbols, with no tooltip."""
        r = api.run_case(self.project, FlightCondition(
            name="c", mu_x=0.2, collective_deg=8.0, rpm=600.0))
        without_symbol = [k for k in r.summary if k not in api._COLUMN_SYMBOL]
        self.assertEqual(without_symbol, [],
                          f"summary keys without symbol/tooltip: {without_symbol}")

    def test_summary_metadata_exposed_publicly(self):
        """`SUMMARY_SYMBOLS`/`SUMMARY_UNITS`/`SUMMARY_PRIMARY_KEYS`/
        `format_summary_value`/`summary_keys_union` are the public source
        that the GUI (Run Case, Results) reuses so it doesn't duplicate by
        hand the same symbols/units/tooltips that the report already
        maintains -- they must remain the SAME object as the private
        implementation, not a copy that could diverge from it."""
        self.assertIs(api.SUMMARY_SYMBOLS, api._COLUMN_SYMBOL)
        self.assertIs(api.SUMMARY_UNITS, api._COLUMN_UNITS)
        self.assertIs(api.SUMMARY_PRIMARY_KEYS, api._MAIN_COLUMNS)
        self.assertIs(api.format_summary_value, api._format_value)
        self.assertIs(api.summary_keys_union, api._sorted_keys)

    def test_no_figure_is_dropped_in_a_large_sweep(self):
        """Before, above 3 conditions the report DISCARDED the 12 disk-map
        figures per case and announced the discard in a yellow box,
        offering "regenerate with fewer conditions" as the way out.
        A report that states in writing that it is incomplete is not a
        report. Now the heavy section becomes its own file alongside it,
        and EVERY figure ends up in one of them."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.02 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 7)]
        dest = os.path.join(self.tmp, "large.html")
        api.generate_report([api.run_case(self.project, c) for c in conds],
                             dest, project=self.project)
        master = Path(dest).read_text(encoding="utf-8")
        self.assertNotIn("Reduced figures in this selection", master)

        # the disk maps went out to a satellite, with ALL fields
        satellite = Path(self.tmp) / "large_disk_maps.html"
        self.assertTrue(satellite.exists(), "disk-map satellite was not generated")
        body = satellite.read_text(encoding="utf-8")
        self.assertIn("Disk map -- drag coefficient", body)
        self.assertIn("Disk maps (all fields)", body)
        self.assertIn('href="large.html"', body)   # link back to the master

    def test_master_has_tables_and_links_not_the_figures_weight(self):
        """The master is the page of INPUTS + OUTPUTS: table and links. With
        all the figures embedded in it, a batch of 4 conditions used to go
        past 3 MB and take a while to open -- precisely the page that is
        consulted first."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.1 * i, collective_deg=8.0, rpm=600.0)
                 for i in range(1, 5)]
        dest = os.path.join(self.tmp, "master.html")
        api.generate_report([api.run_case(self.project, c) for c in conds],
                             dest, project=self.project)
        master = Path(dest).read_text(encoding="utf-8")
        self.assertIn("Figure sets", master)
        self.assertIn('<ul class="satellites">', master)
        # the master does not carry the dozens of per-case figures
        self.assertLess(master.count("<figure>"), 3,
                         "master kept the heavy sections' figures loaded")
        # and the per-case sections exist as their own files
        generated = {p.name for p in Path(self.tmp).glob("master_*.html")}
        self.assertIn("master_disk_maps.html", generated)
        self.assertIn("master_loads_along_azimuth.html", generated)

    def test_chart_axis_is_what_varied(self):
        """A collective sweep plotted against mu_x would stack all the
        points on a single abscissa."""
        conds = [FlightCondition(name=f"c{i}", mu_x=0.2, collective_deg=float(4 + 2 * i),
                                  rpm=600.0) for i in range(3)]
        html = self._html([api.run_case(self.project, c) for c in conds])
        self.assertIn("Performance coefficients vs collective_deg", html)

    def test_figures_follow_results_list_order_not_alphabetical(self):
        """Condition names are free text, they don't happen to sort
        numerically: an alphabetical `sorted()` on top of the file name
        placed "mu_x=0.1"/"mu_x=0.2"/"mu_x=0.3" BEFORE "mu_x=0" (the "1" of
        ".1.png" comes before the "p" of ".png" in the ASCII table) -- the
        sweep 0, 0.1, 0.2, 0.3 came out in the report as 0.1, 0.2, 0.3, 0.
        The correct order is that of `results_list`, not alphabetical."""
        conds = [FlightCondition(name=f"mu_x={m:g}", mu_x=m, collective_deg=8.0, rpm=600.0)
                 for m in (0.0, 0.1, 0.2, 0.3)]
        html = self._full_html([api.run_case(self.project, c) for c in conds])
        positions = [html.index(f"Loads along azimuth -- Case {i} - mu_x={m:g}")
                     for i, m in enumerate((0.0, 0.1, 0.2, 0.3), start=1)]
        self.assertEqual(positions, sorted(positions),
                          "figures out of results_list order")


class TestConditionLabels(unittest.TestCase):
    """Every condition in the report is NUMBERED ("Case 1", "Case 2"...) and
    has its own file.

    The two defects that motivated these tests had the same root: the GUI
    names every Run Case case "caso" (`gui/tabs/run_case.py`), so a
    selection of five cases reached the report as five conditions with
    an IDENTICAL name.

    - in the table, five "caso" rows -- there's no way to cite any one of
      them;
        - in export, `filename_map` indexed by NAME: the five
      conditions collapsed into a single key, whose value was the suffix
      of the last one, and the five figures of each field went to the
      SAME file, overwriting each other. The report embedded five copies
      of case 5's figure, all captioned "caso 5" -- four cases lost in
      silence.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = _make_fast_project(os.path.join(self.tmp, "proj"))
        # equal names, DIFFERENT conditions -- exactly what the GUI produces
        self.results = [
            api.run_case(self.project, FlightCondition(
                name="caso", mu_x=0.05 * i, collective_deg=6.0 + i, rpm=600.0 + 10 * i))
            for i in range(1, 6)]

    def test_label_numbered_per_condition(self):
        self.assertEqual(api.condition_labels(self.results),
                          ["Case 1", "Case 2", "Case 3", "Case 4", "Case 5"])

    def test_name_enters_the_label_when_it_distinguishes(self):
        """A name that actually identifies the condition is not lost -- only
        the repeated name (which conveys nothing) is left out."""
        distinct = [Results(condition_name=f"mu_x={m:g}") for m in (0.0, 0.1)]
        self.assertEqual(api.condition_labels(distinct),
                          ["Case 1 - mu_x=0", "Case 2 - mu_x=0.1"])

    def test_each_condition_gets_its_own_file_even_with_repeated_names(self):
        outdir = os.path.join(self.tmp, "out")
        written = api.export_results(self.results, outdir, plots=["disk_map_CT"],
                                      save_csv=False)
        self.assertEqual(len(written), 5)
        self.assertEqual(len(set(written)), 5, "conditions wrote to the same file")
        for f in written:
            self.assertTrue(Path(f).exists())

    def test_summary_table_rows_are_numbered(self):
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        body = html.split("<h2>Summary</h2>")[1]
        for n in range(1, 6):
            self.assertIn(f"<td>Case {n}</td>", body)
        self.assertNotIn("<td>caso</td>", body)

    def test_each_figure_carries_its_conditions_caption(self):
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project,
                             plots=["convergence"])
        satellite = Path(self.tmp) / "rel_convergence.html"
        captions = re.findall(r"<figcaption>(.*?)</figcaption>",
                               satellite.read_text(encoding="utf-8"))
        self.assertEqual(captions, [f"Solver convergence -- Case {n}" for n in range(1, 6)])


class TestSummaryTableColumns(unittest.TestCase):
    """Reading order and absence of duplicate columns."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = _make_fast_project(os.path.join(self.tmp, "proj"))
        self.results = [api.run_case(self.project, FlightCondition(
            name="c", mu_x=0.2, collective_deg=8.0, rpm=600.0))]

    def test_collective_and_rpm_enter_with_the_other_inputs(self):
        """Collective and RPM are INPUTS, just as much as mu_x/J_x/alpha/Vz:
        without them you can't read a row of the table. They were falling
        after ~40 output columns, in the leftover tail of the dict."""
        ordered, _ = api._sorted_keys(self.results)
        for key in ("collective_deg", "rpm"):
            self.assertIn(key, ordered)
            self.assertLess(ordered.index(key), ordered.index("CT"),
                             f"{key} is not among the first columns")

    def test_rpm_does_not_appear_twice(self):
        """`rpm` and `rotor_rpm` carry the SAME number (`studies` defines
        one from the other); two "RPM" columns side by side make you
        search for a difference that doesn't exist."""
        ordered, _ = api._sorted_keys(self.results)
        self.assertIn("rpm", ordered)
        self.assertNotIn("rotor_rpm", ordered)

    def test_rotor_rpm_reappears_if_it_diverges_from_rpm(self):
        """Hiding it is safe only as long as they are the same number."""
        divergent = [Results(summary={"rpm": 600.0, "rotor_rpm": 610.0})]
        ordered, _ = api._sorted_keys(divergent)
        self.assertIn("rotor_rpm", ordered)

    def test_overflowing_cell_gets_instant_tooltip(self):
        """The report columns have a fixed, uniform width (that's how it's
        meant to be), so a long value from the config echo comes out cut
        off by `text-overflow: ellipsis` -- without a tooltip, there is
        NO way to read the whole value. Same mechanism as the header
        (`data-tip`, instant balloon), not the native `title=`."""
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report(self.results, dest, project=self.project, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        self.assertIn('<td class="tt" data-tip="fixed_point">fixed_point</td>', html)
        # a short value doesn't gain a tooltip for no reason
        self.assertIn("<td>Case 1 - c</td>", html)


class TestColumnNomenclatureAndOrder(unittest.TestCase):
    """The Run Case table, the Results tab table, and the HTML report table
    must show THE SAME quantities, in THE SAME order, with names that
    match the manual (`docs/documentation.html`, Section 2.1 "Nomenclature").

    Before: `_MAIN_COLUMNS` listed 25 of the 96 non-`cfg_` keys of
    `Results.summary`; the other 71 fell to the end, in the insertion
    order of the engine's dict -- an order that exists only by
    implementation accident and that the Run Case tab, with its own
    groups, contradicted. And the axial family came out with three names
    for two quantities (`Vz`, `Vz` and `mu_z` for the SAME climb
    velocity), while `lambda_i`/`lambda` -- which the manual defines
    side by side with `lambda_z` -- did not appear anywhere in the
    summary.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        project = _make_fast_project(os.path.join(cls.tmp, "p"))
        cls.result = api.run_case(project, FlightCondition(
            name="c", mu_x=0.15, Vz=3.0, collective_deg=8.0, rpm=1200.0))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_output_key_is_in_primary_columns(self):
        """Nothing "spills over" to the end: `_sorted_keys` returns
        primaries + remaining, and `remaining` is the catch-all with no
        thought-out order. With full coverage, the table order is the
        same across all three surfaces because all three read this single
        tuple."""
        missing = [k for k in self.result.summary
                   if not k.startswith("cfg_") and k not in api.SUMMARY_PRIMARY_KEYS]
        self.assertEqual(missing, [],
                          f"output keys outside _MAIN_COLUMNS: {missing}")

    def test_inputs_come_first_in_the_stated_order(self):
        """The inputs that define the operating point open the table: the
        x component first (the PRIMARY one in both modes), then z,
        then the two angles, then collective, the cyclic harmonics and
        RPM. `lambda_z` comes alongside `mu_z` because it is the SAME
        number in a different vocabulary."""
        self.assertEqual(
            tuple(api.SUMMARY_PRIMARY_KEYS[:13]),
            ("mu_x", "J_x", "Vx",
             "mu_z", "J_z", "Vz", "lambda_z",
             "alpha_rotor_deg", "alpha_disk_deg",
             "collective_deg", "cyclic_c_deg", "cyclic_s_deg", "rpm"))

    def test_no_quantity_appears_twice_in_the_order(self):
        """A repeated key makes `{k: i for i, k in enumerate(...)}` keep
        the index of the LAST occurrence -- that's how `mu_x` ended up at
        the end of the Run Case tab after the synonyms were merged."""
        keys = list(api.SUMMARY_PRIMARY_KEYS)
        repeated = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(repeated, [])

    def test_table_opens_with_the_x_component_in_BOTH_modes(self):
        """x is always the PRIMARY one -- the helicopter's advance, the
        propeller's flight speed --, and that's what the table starts
        with. Which key carries the letter x is what changes: `mu_x` on
        the rotor, `mu_z` on the propeller."""
        ordered, _cfg = api.summary_keys_union([self.result], True)
        self.assertEqual(tuple(ordered[:3]), ("mu_z", "J_z", "Vz"))
        ordered_rotor, _ = api.summary_keys_union([self.result], False)
        self.assertEqual(tuple(ordered_rotor[:3]), ("mu_x", "J_x", "Vx"))

    def test_no_synonym_is_left_over(self):
        """There used to be TWO keys for the same quantity (`mu`+`mu_x`,
        `J`+`J_x`). Now there is ONE, and it says which axis it belongs to."""
        for key in ("mu", "J"):
            with self.subTest(key=key):
                self.assertNotIn(key, api.SUMMARY_SYMBOLS)
                self.assertNotIn(key, self.result.summary)

    def test_axis_letters_rotate_but_the_number_does_not(self):
        """`is_propeller` swaps the VOCABULARY, never the value nor the
        key: the same key `Vz` is V_z on a rotor and V_x on a propeller."""
        self.assertEqual(api.summary_symbol("Vz", False)[0], "V<sub>z</sub>")
        self.assertEqual(api.summary_symbol("Vz", True)[0], "V<sub>x</sub>")
        self.assertEqual(api.summary_symbol("J_z", True)[0], "J<sub>x</sub>")
        self.assertEqual(api.summary_symbol("J_z", False)[0], "J<sub>z</sub>")
        self.assertEqual(api.summary_symbol("J_x", True)[0], "J<sub>z</sub>")
        self.assertEqual(api.summary_symbol("J_x", False)[0], "J<sub>x</sub>")
        # no new key, none disappear: only the labels change
        self.assertEqual(set(api.summary_symbols(True)),
                          set(api.summary_symbols(False)))

    def test_each_primary_column_has_symbol_unit_and_description(self):
        """A single-letter symbol without a description can't be read; and
        the description is what answers the nomenclature question ("is
        this V_z the disk's or the freestream's?") without leaving the
        table."""
        for key in api.SUMMARY_PRIMARY_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, api.SUMMARY_SYMBOLS)
                symbol, description = api.SUMMARY_SYMBOLS[key]
                self.assertTrue(symbol.strip())
                self.assertTrue(len(description.strip()) > len(key),
                                 f"{key}: description just echoes the name")
                self.assertIn(key, api.SUMMARY_UNITS)

    def test_inflow_triad_exists_and_closes(self):
        """The manual defines lambda = lambda_z + lambda_i (Section 2.6.2)
        and U_P = V_v + v_i (Section 2.4.2). Both identities must be
        verifiable by READING the table, otherwise the names don't mean
        what the manual says they mean."""
        s = self.result.summary
        for key in ("lambda_z", "lambda_i", "lambda_total", "Vz", "Vi", "Vz_total"):
            self.assertIn(key, s, key)
        self.assertAlmostEqual(s["lambda_total"], s["lambda_z"] + s["lambda_i"], places=12)
        self.assertAlmostEqual(s["Vz_total"], s["Vz"] + s["Vi"], places=9)
        self.assertAlmostEqual(s["Vi"], s["lambda_i"] * s["rotor_OmegaR"], places=9)
        self.assertGreater(s["Vi"], 0.0)

    def test_freestream_components_come_out_as_a_paired_pair(self):
        """The two freestream components come out as a PAIR of axis
        letters, x and z -- the axial one used to come out as "V_v", with
        no visible pair. And the letters rotate with the mode: in
        propeller mode x is the rotor axis."""
        self.assertEqual(api.summary_symbol("Vx", False)[0],
                          "V<sub>x</sub>")
        self.assertEqual(api.summary_symbol("Vz", False)[0], "V<sub>z</sub>")
        self.assertEqual(api.summary_symbol("Vx", True)[0],
                          "V<sub>z</sub>")
        self.assertEqual(api.summary_symbol("Vz", True)[0], "V<sub>x</sub>")

    def test_no_component_symbol_is_left_without_subscript(self):
        """There is no longer a bare "mu_x" or "J_x": every advance ratio
        states which AXIS it belongs to, in both modes."""
        for mode in (False, True):
            for key in ("mu_x", "J_x", "mu_z", "J_z"):
                with self.subTest(propeller=mode, key=key):
                    symbol = api.summary_symbol(key, mode)[0]
                    self.assertIn("<sub>", symbol, f"{key} without subscript")

    def test_total_velocity_is_not_a_clone_of_the_freestream_one(self):
        """`Vz_total` (what crosses the disk) is `Vz + v_i`; while the two
        were called `Vv`/`Vz`, one repeated the other, occupying a column
        that promised a different quantity."""
        s = self.result.summary
        self.assertNotAlmostEqual(s["Vz_total"], s["Vz"], places=6)

    def test_report_uses_the_primary_column_order(self):
        dest = os.path.join(self.tmp, "rel.html")
        api.generate_report([self.result], dest, plots=[])
        html = Path(dest).read_text(encoding="utf-8")
        matrix = html.split("<details>")[0]
        # `rotor_rpm` disappears when it is `rpm` again (see
        # `_rotor_rpm_e_redundante`) -- the matrix's effective list is
        # what `_sorted_keys` returns, not the raw tuple.
        ordered, _ = api.summary_keys_union([self.result])
        positions = []
        for key in ordered:
            symbol, _ = api.SUMMARY_SYMBOLS[key]
            mark = f">{symbol}</th>"
            self.assertIn(mark, matrix, f"{key} outside the main matrix")
            positions.append(matrix.index(mark))
        self.assertEqual(positions, sorted(positions),
                          "the report matrix does not follow SUMMARY_PRIMARY_KEYS")


class TestPlotExportDoesNotOverwrite(unittest.TestCase):
    """Exporting twice to the SAME folder must not erase the first one.

    `export_results_tabular` had always gone through
    `_path_without_overwrite`; `_result_plot_path` did not. Exporting a
    case's disk maps, adjusting something, and exporting again would
    erase the previous figure without a word -- the same class of silent
    loss as the bug where N same-named conditions landed in the same
    file."""

    def test_second_export_does_not_erase_the_first(self):
        with tempfile.TemporaryDirectory() as d:
            project = _make_fast_project(os.path.join(d, "proj"))
            res = api.run_case(project, FlightCondition(
                name="c", mu_x=0.1, collective_deg=8.0, rpm=600.0))
            outdir = os.path.join(d, "out")
            first = api.export_results([res], outdir=outdir,
                                        plots=["disk_map_CT"], save_csv=False)
            second = api.export_results([res], outdir=outdir,
                                         plots=["disk_map_CT"], save_csv=False)
            self.assertTrue(first and second)
            self.assertNotEqual(set(first), set(second),
                                 "the second export reused the same files")
            for f in first + second:
                self.assertTrue(Path(f).exists(), f)

    def test_names_stay_stable_within_one_export(self):
        """The anti-overwrite mechanism must not scatter a case's 12
        fields across `(2)`, `(3)`...: each field has its own base name,
        so none collides with the previous one WITHIN the same export."""
        with tempfile.TemporaryDirectory() as d:
            project = _make_fast_project(os.path.join(d, "proj"))
            res = api.run_case(project, FlightCondition(
                name="c", mu_x=0.1, collective_deg=8.0, rpm=600.0))
            written = api.export_results([res], outdir=os.path.join(d, "out"),
                                          plots=["disk_map"], save_csv=False)
            self.assertTrue(written)
            self.assertFalse([f for f in written if " (2)" in f],
                              "a clean export should not have a suffix")


class TestProjectOutputsDir(unittest.TestCase):
    """`<project>/outputs` was hardcoded in Run Case, Run Batch,
    Results and in the CLI. `api.project_outputs_dir` is the canonical definition --
    the same that `models.default_project_paths` already provided, now public."""

    def test_accepts_project_and_path(self):
        with tempfile.TemporaryDirectory() as d:
            project = _make_fast_project(os.path.join(d, "proj"))
            expected = str(Path(d) / "proj" / "outputs")
            self.assertEqual(api.project_outputs_dir(project), expected)
            self.assertEqual(api.project_outputs_dir(os.path.join(d, "proj")), expected)

    def test_without_project_falls_back_to_the_same_fallback_as_always(self):
        """Unsaved project continues exporting (to relative `outputs/`)
        instead of crashing."""
        self.assertEqual(api.project_outputs_dir(None), "outputs")
        self.assertEqual(api.project_outputs_dir(Project(name="x")), "outputs")

    def test_create_creates_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            dest = api.project_outputs_dir(os.path.join(d, "new"), create=True)
            self.assertTrue(Path(dest).is_dir())
