"""`PA-1`/`PA-3`: the stability derivatives must be reachable from the CLI.

Every study the window can run has to have a command-line path, and
SC-14 was the one feature that had none: the chapter admitted it ran
"through the library today". A study that only the GUI can start cannot
be scripted, cannot be put in a batch file, and cannot be reproduced by
anyone who was sent the project.

The tests below drive the real parser and the real handlers, with the
solver replaced, so they check the wiring rather than the physics.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zbemt import api
from zbemt.models import DerivativeRequest, FlightCondition
from tests.helpers import make_studies_project


def _stub_case(project, condition, should_cancel=None):
    """A linear toy, so the wiring is what is being measured."""
    class _R:
        pass

    r = _R()
    w = float(condition.Vz)
    q = float(getattr(condition, "q_rate_deg_s", 0.0) or 0.0)
    r.summary = {"Thrust": 1000.0 - 25.0 * w, "Mx_total": -2.0 * q,
                 "convergence_pct": 100.0}
    return r


class _ProjectOnDisk(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "proj"
        project = make_studies_project()
        project.path = str(self.path)
        project.saved_cases = [FlightCondition(name="hover", mu_x=0.0,
                                                collective_deg=8.0, rpm=600.0)]
        project.derivatives.append(DerivativeRequest(
            name="hover damping", condition=project.saved_cases[0],
            trim="none", states=["w", "q"], controls=["theta_0"],
            outputs=["Thrust", "Mx_total"], richardson_check=False))
        api.save_project(project)
        self.project = api.open_project(str(self.path))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestTheStudyIsFoundByName(_ProjectOnDisk):

    def test_a_bare_call_returns_the_first_study(self):
        self.assertEqual(api.get_derivative_request(self.project).name,
                          "hover damping")

    def test_a_name_selects_its_study(self):
        self.assertEqual(
            api.get_derivative_request(self.project, "hover damping").name,
            "hover damping")

    def test_an_unknown_name_lists_what_there_is(self):
        with self.assertRaises(KeyError) as ctx:
            api.get_derivative_request(self.project, "no such study")
        message = ctx.exception.args[0]
        self.assertIn("no such study", message)
        self.assertIn("hover damping", message)

    def test_a_project_without_studies_says_where_to_look(self):
        empty = make_studies_project()
        with self.assertRaises(KeyError) as ctx:
            api.get_derivative_request(empty)
        self.assertIn("derivatives.bemt", ctx.exception.args[0])


class TestTheFlagsExist(unittest.TestCase):
    """The parser is the contract: a flag that does not parse cannot be
    scripted, whatever the handler does."""

    def _parse(self, argv):
        from zbemt.cli import _build_parser

        return _build_parser().parse_args(argv)

    def test_bare_derivatives_is_the_first_study(self):
        args = self._parse(["--project", "p", "--derivatives"])
        self.assertEqual(args.derivatives, "")

    def test_derivatives_takes_a_name(self):
        args = self._parse(["--project", "p", "--derivatives", "hover damping"])
        self.assertEqual(args.derivatives, "hover damping")

    def test_absent_means_none_not_empty(self):
        """`""` is a bare flag and `None` is no flag at all. Collapsing
        the two would make every ordinary run start a derivative study."""
        args = self._parse(["--project", "p"])
        self.assertIsNone(args.derivatives)

    def test_the_listing_and_the_csv_flags_parse(self):
        args = self._parse(["--project", "p", "--list-derivatives",
                             "--derivatives-csv", "out.csv"])
        self.assertTrue(args.list_derivatives)
        self.assertEqual(args.derivatives_csv, "out.csv")


class TestTheRunWritesItsMatrix(_ProjectOnDisk):

    def _main(self, argv):
        from zbemt import cli

        with mock.patch("zbemt.studies.run_single_case", _stub_case):
            return cli.main(argv)

    def test_the_study_runs_and_writes_a_csv(self):
        destination = self.tmp / "matrix.csv"
        code = self._main(["--project", str(self.path), "--derivatives",
                            "--derivatives-csv", str(destination)])
        self.assertEqual(code, 0)
        self.assertTrue(destination.exists())
        body = destination.read_text(encoding="utf-8")
        self.assertIn("Mx_total", body)
        self.assertIn("Thrust", body)

    def test_without_the_csv_flag_it_lands_in_the_outputs_folder(self):
        code = self._main(["--project", str(self.path), "--derivatives"])
        self.assertEqual(code, 0)
        written = list((self.path / "outputs").glob("*_derivatives.csv"))
        self.assertTrue(written, "no matrix was written")

    def test_an_unknown_study_fails_without_a_traceback(self):
        code = self._main(["--project", str(self.path), "--derivatives",
                            "nope"])
        self.assertEqual(code, 1)

    def test_listing_the_studies_succeeds(self):
        self.assertEqual(
            self._main(["--project", str(self.path), "--list-derivatives"]), 0)


class TestItIsOneJobAmongTheOthers(_ProjectOnDisk):
    """The design-tool modes each run their own workflow and write their
    own artifacts, so two in one call has no defined meaning."""

    def test_derivatives_conflicts_with_optimize(self):
        from zbemt import cli

        code = cli.main(["--project", str(self.path), "--derivatives",
                          "--optimize"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
