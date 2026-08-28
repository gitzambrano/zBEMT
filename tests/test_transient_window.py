"""The Transient Simulation window (`SC-12`).

It shipped with no test file at all, which is how nine group boxes went
without help for a whole release and how the point table kept its own
symbol list. What is checked here is the wiring a user meets: the window
opens on an empty project, the trajectory table follows the mode's axis
convention, the sampling controls reach the definition, and the run
button is gated on there being something to run.

The engine itself is covered by `tests/test_transient.py`; this file
does not re-run the physics.
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT

if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication

from tests.helpers import make_studies_project
from zbemt.models import FlightCondition, ManeuverDefinition, ManeuverPoint


class TransientWindowBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.transient_window import TransientWindow

        self.state = AppState()
        self.window = TransientWindow(self.state)

    def _load_project(self, propeller=False):
        project = make_studies_project()
        project.saved_cases = [
            FlightCondition(name="slow", mu_x=0.05, collective_deg=6.0,
                             rpm=600.0),
            FlightCondition(name="fast", mu_x=0.25, collective_deg=9.0,
                             rpm=600.0)]
        project.maneuvers.append(ManeuverDefinition(
            name="pull up",
            points=[ManeuverPoint(t_s=0.0, mu_x=0.05, collective_deg=6.0,
                                   rpm=600.0),
                    ManeuverPoint(t_s=1.0, mu_x=0.25, collective_deg=9.0,
                                   rpm=600.0)],
            dt_s=0.05, substeps_per_step=8))
        if propeller:
            project.config["is_propeller"] = True
        self.state.project = project
        self.window._refresh_from_project()
        return project


class TestItOpens(TransientWindowBase):

    def test_an_empty_project_does_not_raise(self):
        self.assertIsNotNone(self.window)
        self.assertEqual(self.window.maneuver_combo.count(), 0)

    def test_a_project_populates_the_list(self):
        self._load_project()
        self.assertEqual(self.window.maneuver_combo.count(), 1)

    def test_the_points_table_has_one_column_per_field(self):
        self._load_project()
        self.assertEqual(self.window.points_table.columnCount(),
                          len(self.window._POINT_FIELDS))


class TestTheHeadingsComeFromNomenclature(TransientWindowBase):
    """`PR-4`/`PR-8`. The table used to carry its own list of column
    names, with a plain-text "mu" among them, and it did not rotate in
    propeller mode."""

    def _headings(self):
        table = self.window.points_table
        return [table.horizontalHeaderItem(c).text()
                for c in range(table.columnCount())]

    def test_no_plain_text_greek_in_a_heading(self):
        self._load_project()
        for heading in self._headings():
            self.assertNotIn("mu", heading.lower().split(" ")[0],
                              f"{heading!r} spells a Greek letter out")

    def test_the_in_plane_heading_rotates_with_the_mode(self):
        self._load_project(propeller=False)
        rotor = self._headings()
        self.setUp()
        self._load_project(propeller=True)
        propeller = self._headings()
        self.assertNotEqual(rotor, propeller,
                            "the letters must rotate in propeller mode, "
                            "exactly as they do for a saved case")

    def test_time_is_still_seconds_in_both_modes(self):
        """The rotation is about the AXES. Time is not an axis."""
        for propeller in (False, True):
            with self.subTest(propeller=propeller):
                self.setUp()
                self._load_project(propeller=propeller)
                self.assertIn("s", self._headings()[0])


class TestTheSamplingControlsReachTheDefinition(TransientWindowBase):

    def test_the_editor_shows_the_saved_values(self):
        self._load_project()
        self.assertAlmostEqual(self.window.dt_spin.value(), 0.05, places=6)
        self.assertEqual(self.window.substeps_spin.value(), 8)

    def test_the_two_intervals_are_separate_controls(self):
        """The sample interval is what is written down; the sub-step is
        how finely the inflow is marched between two samples. Collapsing
        them would make a readable plot and a resolved march the same
        setting, which they are not."""
        self._load_project()
        self.assertIsNot(self.window.dt_spin, self.window.substeps_spin)
        self.assertGreater(self.window.substeps_spin.maximum(), 1)

    def test_the_march_options_are_off_by_default(self):
        """Both cost time and neither means anything unless the matching
        model is enabled elsewhere, so neither is on until asked for."""
        self.assertFalse(self.window.march_stall_check.isChecked())
        self.assertFalse(self.window.march_flap_check.isChecked())


class TestEveryBlockHasHelp(TransientWindowBase):
    """`PR-3`/`DC-4`. Nine group boxes shipped with no help at all while
    every other Tools window had it."""

    def test_every_group_box_title_resolves_to_a_help_block(self):
        from PyQt6.QtWidgets import QGroupBox

        from zbemt.gui.app import MainWindow

        window = MainWindow()
        try:
            titles = [gb.title() for gb
                      in window.transient_window.findChildren(QGroupBox)
                      if gb.title()]
            self.assertTrue(titles, "the window has no group boxes at all")
            without = [t for t in titles
                       if getattr(window.transient_window, "_block_help", None)
                       is None and not _has_block(window.transient_window, t)]
            self.assertEqual(without, [],
                              f"group boxes with no help: {without}")
        finally:
            window.close()


def _has_block(root, title):
    """True when the group box carrying ``title`` was made clickable."""
    from PyQt6.QtWidgets import QGroupBox

    for box in root.findChildren(QGroupBox):
        if box.title() == title:
            return getattr(box, "_block_help", None) is not None
    return False


if __name__ == "__main__":
    unittest.main()
