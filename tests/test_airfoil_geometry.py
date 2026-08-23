"""Block "2D Profile Geometry" from the Airfoil tab:

* the "typical preset" combo was removed -- all six catalog entries are NACA
  codes, so the preset and "NACA code" field were two controls for a single
  choice;
* `cst`/`bezier` are first-class sources again (user decision reversing an
  earlier removal): the editors show for their option and the contour is
  never lost, whichever way a project was written;
* the remaining fields gained proper help (popup "?" and tooltip),
  including the format accepted by the `.dat` importer.
"""
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

from zbemt import airfoils
from zbemt.models import ProfileGeometry


class _TestWindow(unittest.TestCase):
    """Base with ONE real window for all tests in this file.

    The tab is read INSIDE the window, not instantiated standalone: the width
    and help policies are applied by the window from outside, so a standalone
    tab would not have them and the test would pass by accident. And the
    window is ONE per `setUpClass`: building a `MainWindow` per test crashes
    Qt on this machine (native failure, no Python exception) -- the same Qt
    teardown defect that prevents `tests/test_airfoil_tab.py` from running
    here.
    """

    @classmethod
    def setUpClass(cls):
        from zbemt.gui.app import MainWindow
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()
        cls.tab = None
        for i in range(cls.win.tabs.count()):
            if cls.win.tabs.tabText(i).replace("*", "").strip() == "Airfoil":
                cls.tab = cls.win.tabs.widget(i)
        assert cls.tab is not None, "Airfoil tab not found in the window"

    @classmethod
    def tearDownClass(cls):
        # The window is NOT closed here on purpose: `close()` on a window
        # that went through several project changes hangs the process at the
        # end of the suite on this machine. (Update: `tests/test_airfoil_tab.py`
        # turned out to have an unrelated bug -- its own `_app()` helper
        # discarded the QApplication it created, so nothing kept it alive;
        # that is fixed now and unrelated to this window.) Hiding avoided the
        # hang but left the actual C++-side teardown to whatever order
        # Python's interpreter-shutdown GC happens to run in, which is what
        # crashed the process (access violation) right after the last test
        # here. Force it now instead, while the QApplication and event loop
        # are still in a known-good state.
        cls.win.hide()
        win, cls.win = cls.win, None
        win.deleteLater()
        cls.app.processEvents()
        del win
        import gc
        gc.collect()

    def setUp(self):
        from tests.helpers import make_studies_project
        self.state = self.win.state
        self.state.set_project(make_studies_project())
        # The window is shared by the class (see `setUpClass`): without
        # resetting the source to default, a test that left it in
        # 'neuralfoil' makes the next one start already in the mode -- and
        # the automatic suggestion, which reacts to the TRANSITION, would
        # never fire.
        self.tab.source_combo.setCurrentText("analytical")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestContourSources(_TestWindow):

    def test_no_preset_combo(self):
        tab = self.tab
        self.assertFalse(hasattr(tab, "profile_preset_combo"),
                          "the preset combo was redundant with the NACA field")

    def test_all_five_contour_sources_in_the_list(self):
        tab = self.tab
        offered = [tab.profile_source_combo.itemText(i)
                   for i in range(tab.profile_source_combo.count())]
        self.assertEqual(offered,
                         ["naca4", "naca5", "cst", "bezier", "imported"])

    def test_legacy_project_in_cst_recovers_the_option(self):
        """Hiding an option must not mean losing data from who already used
        it."""
        tab, state = self.tab, self.state
        state.project.airfoil.geometry = ProfileGeometry(
            source="cst", cst_upper=[0.2, 0.2], cst_lower=[-0.1, -0.1])
        state.notify_airfoil()
        self.assertEqual(tab.profile_source_combo.currentText(), "cst")
        self.assertEqual(tab._collect_airfoil_def().geometry.source, "cst")
        self.assertEqual(tab._collect_airfoil_def().geometry.cst_upper, [0.2, 0.2])

    def test_imported_contour_appears_as_imported(self):
        """The combo was not synced with the project: a profile coming from
        .dat appeared labeled "naca4"."""
        tab, state = self.tab, self.state
        state.project.airfoil.geometry = ProfileGeometry(
            source="imported", x=[1.0, 0.0, 1.0], y=[0.0, 0.0, 0.0])
        state.notify_airfoil()
        self.assertEqual(tab.profile_source_combo.currentText(), "imported")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestBlockHelp(unittest.TestCase):
    """Help texts and catalog: all read from CLASS attributes and pure
    functions, without building any widgets.

    No widget is built, but the class attributes still come from a
    `zbemt.gui` module, which needs Qt to import."""

    @property
    def tab(self):
        from zbemt.gui.tabs.airfoil import AirfoilTab
        return AirfoilTab

    def test_contour_fields_have_a_help_popup(self):
        """They did not have entries in FIELD_HELP or anchors: the "?" did
        not appear in the row and the user got no explanation at all."""
        from zbemt.gui import help_content
        from zbemt.gui.field_help import field_anchor
        for field in ("naca_code", "cst_upper", "cst_lower", "bezier_control_points",
                      "geometry_spec"):
            with self.subTest(field=field):
                self.assertIn(field, help_content.FIELD_HELP)
                self.assertIsNotNone(field_anchor(field))

    def test_contour_importer_hint_states_the_format(self):
        tooltip = self.tab._DAT_IMPORT_TOOLTIP.lower()
        for term in ("x then y", "selig", "lednicer", "chord", ".dat", ".csv"):
            with self.subTest(term=term):
                self.assertIn(term, tooltip)

    def test_polar_importer_hint_states_columns_lines_and_blocks(self):
        """The old hint was "imports a polar CSV" -- someone who never saw
        the format had no way to build the file. The entire contract
        (required columns, what is a line, how to declare a sweep) must be
        written."""
        tooltip = self.tab._CSV_IMPORT_TOOLTIP
        for term in ("alpha_deg", "Cl", "Cd", "r_norm", "reynolds", "mach",
                     "ONE LINE = ONE ANGLE OF ATTACK", "ONE BLOCK = ONE COMBINATION"):
            with self.subTest(term=term):
                self.assertIn(term, tooltip)

    def test_polar_hint_lists_the_aliases_the_importer_accepts(self):
        """The alternative column names are those from
        `airfoils._COLUMN_ALIASES` -- if one stops being accepted, the hint
        stops being true."""
        tooltip = self.tab._CSV_IMPORT_TOOLTIP
        for alias in ("aoa", "r/R", "Re", "M"):
            with self.subTest(alias=alias):
                self.assertIn(alias, tooltip)
                self.assertTrue(
                    any(alias in aliases
                        for aliases in airfoils._COLUMN_ALIASES.values()),
                    f"the hint promises the alias {alias!r}, which the importer does not accept")

    def test_naca_catalog_enters_the_field_hint(self):
        """The note for each preset ("what is typical for") was the only
        content the removed combo added -- it survives in the field help,
        derived from the SAME catalog. Only the NACA families are listed:
        the hint sits in the NACA field, and the analytic presets
        (parsec/joukowski/biconvex) carry generator parameters, not a NACA
        code -- they are reachable through the Geometry spec field."""
        from zbemt.gui.tabs.airfoil import NACA_CATALOG_TEXT
        tooltip = NACA_CATALOG_TEXT()
        for alias, data in airfoils.AIRFOIL_PRESETS.items():
            if data["family"] not in ("naca4", "naca5"):
                continue
            with self.subTest(code=data["code"]):
                self.assertIn(data["code"], tooltip)

    def test_every_analytic_preset_is_named_by_a_catalog_entry(self):
        """The new analytic families are first-class: each one has a preset
        entry that `generate_preset` dispatches by family key."""
        families = {data["family"] for data in airfoils.AIRFOIL_PRESETS.values()}
        self.assertLessEqual({"parsec", "joukowski", "biconvex"}, families)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestGeometrySpecField(_TestWindow):
    """The Geometry spec field: one string feeding the same resolver the
    CLI uses, taking precedence over the Source/NACA fields when filled."""

    def test_spec_takes_precedence_over_the_combo(self):
        tab = self.tab
        tab.profile_source_combo.setCurrentText("naca4")
        tab.naca_code_edit.setText("2412")
        tab.geometry_spec_edit.setText("biconvex:0.08")
        tab._generate_profile()
        import numpy as np
        y = np.asarray(tab._profile.y)
        self.assertEqual(tab._profile.source, "biconvex")
        # tolerance covers the cosine grid not landing exactly on x=0.5
        self.assertAlmostEqual(float(y.max() - y.min()), 0.08, delta=1e-3)

    def test_empty_spec_falls_back_to_the_naca_field(self):
        tab = self.tab
        tab.geometry_spec_edit.clear()
        tab.profile_source_combo.setCurrentText("naca4")
        tab.naca_code_edit.setText("0012")
        tab._generate_profile()
        self.assertEqual(tab._profile.source, "naca4")
        self.assertEqual(tab._profile.naca_code, "0012")

    def test_invalid_spec_reports_an_error_and_keeps_the_previous_profile(self):
        from unittest.mock import patch
        tab = self.tab
        tab.geometry_spec_edit.setText("biconvex:0.06")
        tab._generate_profile()
        before = tab._profile
        with patch("zbemt.gui.tabs.airfoil.show_error") as err:
            tab.geometry_spec_edit.setText("parsec:1,2,3")
            tab._generate_profile()
        self.assertTrue(err.called, "an invalid spec must say so, not fail silently")
        self.assertIs(tab._profile, before)

    def test_preset_nicknames_resolve_through_the_spec_field(self):
        tab = self.tab
        for spec, expected_source in (("parsec_default", "parsec"),
                                      ("joukowski_t8c5", "joukowski"),
                                      ("biconvex_t6", "biconvex")):
            with self.subTest(spec=spec):
                tab.geometry_spec_edit.setText(spec)
                tab._generate_profile()
                self.assertEqual(tab._profile.source, expected_source)


class TestSuggestedEnvelope(unittest.TestCase):
    """The suggestion calculation -- pure function, no GUI."""

    def test_advance_enters_the_calculation(self):
        from zbemt import geometry
        geom = geometry.generate_tapered(radius_m=8.0, n_stations=12)
        hovering = airfoils.suggest_reynolds_mach_lists(geom, 300.0, mu_x=0.0)
        advancing = airfoils.suggest_reynolds_mach_lists(geom, 300.0, mu_x=0.4)
        self.assertGreater(max(advancing["mach"]), max(hovering["mach"]))
        self.assertGreater(max(advancing["reynolds"]), max(hovering["reynolds"]))


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestCompressibilityAvailable(_TestWindow):
    """The Prandtl-Glauert correction is only blocked when the polar IN USE
    already brings Mach as given. Before the condition only looked at the
    imported slices -- which remain stored when changing source --, so it was
    enough to pass through 'table' with a table swept in Mach for the toggle
    to stay gray forever, even in 'analytical', where no table is consulted."""

    def _table_swept_in_mach(self):
        from zbemt.models import PolarSlice
        return [PolarSlice(alpha_deg=[0, 5], cl=[0.0, 0.5], cd=[0.01, 0.02], mach=m)
                for m in (0.1, 0.5)]

    def test_blocks_in_table_and_returns_in_analytical(self):
        tab = self.tab
        checkbox = tab.cfg_use_compressibility
        tab._imported_slices = self._table_swept_in_mach()

        tab.source_combo.setCurrentText("table")
        self.assertFalse(checkbox.isEnabled(), "a table swept in Mach must block")

        tab.source_combo.setCurrentText("analytical")
        self.assertTrue(checkbox.isEnabled(),
                        "in 'analytical' no table is consulted: nothing to lock")

    def test_user_value_comes_back_when_re_enabled(self):
        """Blocking unchecks the box; without restoring the value, the
        user's choice would be lost in a source back-and-forth."""
        tab = self.tab
        checkbox = tab.cfg_use_compressibility
        checkbox.setChecked(True)
        tab._imported_slices = self._table_swept_in_mach()

        tab.source_combo.setCurrentText("table")
        self.assertFalse(checkbox.isChecked())
        tab.source_combo.setCurrentText("analytical")
        self.assertTrue(checkbox.isChecked())

    def test_table_without_a_mach_sweep_does_not_block(self):
        from zbemt.models import PolarSlice
        tab = self.tab
        tab._imported_slices = [
            PolarSlice(alpha_deg=[0, 5], cl=[0.0, 0.5], cd=[0.01, 0.02], reynolds=1e5),
            PolarSlice(alpha_deg=[0, 5], cl=[0.0, 0.5], cd=[0.01, 0.02], reynolds=5e5),
        ]
        tab.source_combo.setCurrentText("table")
        self.assertTrue(tab.cfg_use_compressibility.isEnabled())

    def test_blocked_tooltip_keeps_the_field_name(self):
        """`field_help` derives the field name from the first quoted token
        in the tooltip: if the blocking text replaced it, the help popup would
        disappear along with availability."""
        tab = self.tab
        tab._imported_slices = self._table_swept_in_mach()
        tab.source_combo.setCurrentText("table")
        self.assertIn('"use_compressibility"', tab.cfg_use_compressibility.toolTip())


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestReynoldsMachSuggestion(_TestWindow):
    """The NeuralFoil suggestion follows the operating point -- before it was
    calculated once when entering the mode and fell behind."""

    def test_reference_mu_is_the_largest_of_the_conditions(self):
        """An envelope that does not cover the fastest condition in the
        project is useless."""
        from zbemt.models import FlightCondition
        tab, state = self.tab, self.state
        state.project.saved_cases = [
            FlightCondition(name="a", mu_x=0.1, rpm=600.0),
            FlightCondition(name="b", mu_x=0.35, rpm=600.0),
        ]
        self.assertAlmostEqual(tab._reference_mu(), 0.35)

    def test_without_any_condition_hover_is_assumed(self):
        tab = self.tab
        self.assertEqual(tab._reference_mu(), 0.0)

    def test_geometry_change_redraws_the_suggestion(self):
        tab, state = self.tab, self.state
        tab.source_combo.setCurrentText("neuralfoil")
        before = tab.re_list_edit.text()
        state.project.geometry.radius_m *= 2.0
        state.notify_geometry()
        self.assertNotEqual(tab.re_list_edit.text(), before)

    def test_manually_typed_list_is_respected(self):
        """The suggestion follows the project UNTIL the user types theirs."""
        tab, state = self.tab, self.state
        tab.source_combo.setCurrentText("neuralfoil")
        tab.re_list_edit.setText("1e5, 2e5")
        tab._on_re_mach_edited()
        state.project.geometry.radius_m *= 2.0
        state.notify_geometry()
        self.assertEqual(tab.re_list_edit.text(), "1e5, 2e5")


if __name__ == "__main__":
    unittest.main()
