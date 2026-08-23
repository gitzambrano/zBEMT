"""Requirement-derived guardrails.

Every test in this file exists because a defect reached the branch even
though the suite was green. The class docstrings name the escape each
one closes, so the next "how did the tests not catch this?" has an
answer in code. The requirements live in docs/software_requirements.md
and in AGENTS.md's GUI rules; these tests pin the parts of them that
used to be enforced only by eye.
"""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import (QApplication, QAbstractSpinBox, QCheckBox,
                                 QComboBox, QFormLayout, QLabel, QLineEdit,
                                 QTextEdit, QWidget)
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

from zbemt import airfoils, api, external_solvers

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _starter_copy(tmp_root: str) -> str:
    dest = os.path.join(tmp_root, "starter_rotor")
    shutil.copytree(os.path.join(REPO, "projects", "starter_rotor"), dest)
    return dest


def _effective_tooltip(widget) -> str:
    """The tooltip the user actually sees: the widget's own, or the
    nearest ancestor's within three hops (composite inputs keep the
    text on the container)."""
    node, hops = widget, 0
    while node is not None and hops < 3:
        tip = (node.toolTip() or "").strip()
        if tip:
            return tip
        node = node.parentWidget()
        hops += 1
    return ""


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class _WindowBase(unittest.TestCase):
    """One real MainWindow on a throwaway copy of the starter project."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls._tmp = tempfile.mkdtemp(prefix="guardrails_")
        project = api.open_project(_starter_copy(cls._tmp))
        from zbemt.gui import app as gui
        cls.gui = gui
        cls.win = gui.MainWindow()
        cls.win.resize(1500, 1000)
        cls.win.state.set_project(project)
        cls.win.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.win.hide()
        cls.win.deleteLater()
        cls.app.processEvents()
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _tabs(self):
        for i in range(self.win.tabs.count()):
            yield type(self.win.tabs.widget(i)).__name__, self.win.tabs.widget(i)
        yield "GeometryDesignerWindow", self.win.geometry_designer


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestEveryVisibleInputObeysPr2(_WindowBase):
    """ESCAPE CLOSED: enabled-but-empty combos and tooltip-less inputs
    shipped in the Results and Run Batch tabs. PR-2 says a real-but-
    blocked control stays visible and DISABLED, and every field explains
    itself; nothing swept for that automatically."""

    def test_no_visible_combo_is_enabled_and_empty(self):
        offenders = []
        for tab_name, tab in self._tabs():
            for combo in tab.findChildren(QComboBox):
                if (combo.isVisibleTo(tab) and combo.isEnabled()
                        and combo.count() == 0):
                    offenders.append(f"{tab_name}: {combo.toolTip()[:40]!r}")
        self.assertEqual(offenders, [],
                         "visible combos must never be enabled AND empty (PR-2): "
                         + str(offenders))

    def test_every_visible_input_explains_itself(self):
        mute = []
        for tab_name, tab in self._tabs():
            for cls in (QComboBox, QAbstractSpinBox, QCheckBox):
                for w in tab.findChildren(cls):
                    if w.isVisibleTo(tab) and not _effective_tooltip(w):
                        mute.append(f"{tab_name}:{cls.__name__}")
        self.assertEqual(mute, [],
                         "visible inputs need a tooltip (own or composite): "
                         + str(sorted(set(mute))))


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestFormFieldColumnsShareEdges(_WindowBase):
    """ESCAPE CLOSED: the Airfoil 'Source' dropdown sat ~460px short of
    the editors in its own column. The alignment rule ("align fields
    vertically across forms") had NO test -- the only layout test in the
    suite enforced the opposite heuristic (enums must stay narrow), so
    the defect passed CI while violating the rule the user sees.

    Scope: free-text fields (line edits, plain-text edits) and combos
    flagged as full-column members must share the column edges. Numeric
    spins and enum-capped combos follow their OWN width policies
    (NUMBER_WIDTH / ENUM caps) and are deliberately outside this
    invariant -- mixing them in one form is house style, not a defect."""

    LEFT_TOLERANCE = 2      # px
    RIGHT_TOLERANCE = 6     # px: borders/padding of wrapped containers

    @staticmethod
    def _column_member(field) -> bool:
        if isinstance(field, (QLineEdit, QTextEdit)):
            return True
        return isinstance(field, QComboBox) and bool(
            field.property("_form_width_stretch"))

    def test_text_fields_of_each_form_share_the_column_edges(self):
        bad = []
        for tab_name, tab in self._tabs():
            for fi, form in enumerate(tab.findChildren(QFormLayout)):
                lefts, rights = [], []
                for r in range(form.rowCount()):
                    label_item = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
                    field_item = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
                    if label_item is None or field_item is None:
                        continue
                    label, field = label_item.widget(), field_item.widget()
                    if not isinstance(label, QLabel) or field is None:
                        continue      # spanning rows have no field column
                    if not field.isVisibleTo(tab):
                        continue
                    if not self._column_member(field):
                        continue
                    top_left = field.mapTo(tab, QPoint(0, 0))
                    lefts.append(top_left.x())
                    rights.append(top_left.x() + field.width())
                if len(lefts) < 2:
                    continue
                if max(lefts) - min(lefts) > self.LEFT_TOLERANCE:
                    bad.append(f"{tab_name} form#{fi}: left edges "
                               f"{min(lefts)}..{max(lefts)}")
                if max(rights) - min(rights) > self.RIGHT_TOLERANCE:
                    bad.append(f"{tab_name} form#{fi}: right edges "
                               f"{min(rights)}..{max(rights)}")
        self.assertEqual(bad, [],
                         "text fields of one form must share the column edges: "
                         + str(bad))


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestAirfoilSourcesAreReachable(_WindowBase):
    """ESCAPE CLOSED: XFOIL shipped with fields, a worker and a run
    branch -- and NO way to select it (the engine combo was hidden and
    forced to neuralfoil/none). The suite asserted visibility rules for
    whatever state the code set; nothing asserted that a user acting
    only on the UI can reach each advertised mode. CST/Bezier had the
    inverse failure: a test asserted the REDUCED option list, encoding
    the bug as specification."""

    def test_contour_sources_cover_every_family(self):
        tab = self._airfoil()
        offered = [tab.profile_source_combo.itemText(i)
                   for i in range(tab.profile_source_combo.count())]
        self.assertEqual(offered, ["naca4", "naca5", "cst", "bezier",
                                   "parsec", "joukowski", "biconvex",
                                   "imported"])

    def test_every_polar_source_mode_is_user_reachable_and_complete(self):
        tab = self._airfoil()
        offered = [tab.source_combo.itemText(i)
                   for i in range(tab.source_combo.count())]
        self.assertEqual(offered,
                         ["analytical", "table", "neuralfoil", "xfoil"])
        for mode, engine in (("analytical", "none"), ("table", "none"),
                             ("neuralfoil", "neuralfoil"), ("xfoil", "xfoil")):
            with self.subTest(mode=mode):
                tab.source_combo.setCurrentText(mode)   # what a user does
                self.app.processEvents()
                self.assertEqual(tab.engine_combo.currentText(), engine,
                                 "the hidden engine must follow the source")
                generated = mode in ("neuralfoil", "xfoil")
                self.assertEqual(tab.geometry_box.isVisibleTo(tab), generated)
                self.assertEqual(tab.external_box.isVisibleTo(tab), generated)
                for w in (tab.ext_ncrit, tab.ext_xtr_top, tab.ext_xtr_bot):
                    self.assertEqual(w.isVisibleTo(tab.external_box),
                                     mode == "xfoil",
                                     f"{w.objectName()} must show only in xfoil")

    def _airfoil(self):
        for _name, tab in self._tabs():
            if type(tab).__name__ == "AirfoilTab":
                return tab
        raise AssertionError("AirfoilTab not found")


class TestMissingBinaryErrorIsActionable(unittest.TestCase):
    """ESCAPE CLOSED: the XFOIL dialog said 'install it' to a user who
    HAD it installed -- and the only test on that path checked an exit
    code and a substring. Requirement: any error must tell the user how
    to fix it. The message must name every lookup place AND a concrete
    remedy; the dialog must offer Locate… and the download link."""

    def test_engine_error_names_every_lookup_place_and_a_remedy(self):
        with tempfile.TemporaryDirectory() as home:
            old = os.environ.get("ZBEMT_HOME")
            os.environ["ZBEMT_HOME"] = home
            try:
                with unittest.mock.patch.object(external_solvers.shutil,
                                                "which", return_value=None):
                    with unittest.mock.patch.object(
                            external_solvers, "_known_xfoil_candidates",
                            return_value=[]):
                        self.assertIsNone(external_solvers.resolve_xfoil_binary())
                        with self.assertRaises(RuntimeError) as ctx:
                            external_solvers._run_polar_xfoil(
                                airfoils.generate_naca4("0012"),
                                [1e6], [0.1], -6, 6, 2.0)
            finally:
                if old is None:
                    os.environ.pop("ZBEMT_HOME", None)
                else:
                    os.environ["ZBEMT_HOME"] = old
        message = str(ctx.exception)
        for token in ("ZBEMT_XFOIL_BIN", "PATH", "Locate", "download"):
            self.assertIn(token, message,
                          f"error must tell the user HOW: missing {token!r}")

    def test_standard_folder_finds_a_real_install(self):
        """On machines with XFOIL in the standard folder the chain must
        resolve WITHOUT any configuration (the reported case)."""
        path = external_solvers.resolve_xfoil_binary()
        if path is None:
            raise unittest.SkipTest("no XFOIL in standard folders here")
        self.assertTrue(os.path.isfile(path))


import unittest.mock  # noqa: E402  (used by the actionable-error test)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestMissingBinaryDialogOffersAWayOut(_WindowBase):
    """ESCAPE CLOSED (GUI half): the dialog must offer Locate… (which
    remembers) and the download link, and must NOT appear at all when
    the binary is already found."""

    def test_found_binary_returns_true_without_dialog(self):
        from zbemt.gui import common
        with unittest.mock.patch.object(common, "MissingBinaryDialog") as marker:
            self.assertTrue(common.require_optional_binary(
                self.win, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                download_hint="unused"))
        marker.assert_not_called()

    def test_missing_binary_dialog_text_names_locate_and_link(self):
        from PyQt6.QtWidgets import QLabel as _QLabel
        from zbemt.gui import common
        shown = {}

        def fake_exec(dialog):
            shown["text"] = " ".join(
                lbl.text() for lbl in dialog.findChildren(_QLabel))

        real_dialog = common.MissingBinaryDialog
        with unittest.mock.patch.object(common, "resolve_xfoil_binary",
                                        return_value=None), \
             unittest.mock.patch.object(common, "MissingBinaryDialog",
                                        wraps=real_dialog) as spy, \
             unittest.mock.patch.object(real_dialog, "exec", fake_exec):
            result = common.require_optional_binary(
                self.win, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                download_hint="unused")
        self.assertFalse(result)
        self.assertTrue(spy.called, "a miss must show the actionable dialog")
        text = shown.get("text", "")
        self.assertIn("Locate", text,
                      "dialog must offer the Locate… remedy")
        self.assertIn("http", text.lower(),
                      "dialog must link the download page")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestHelpPopupsNeverOverflowEveryField(_WindowBase):
    """ESCAPE CLOSED: the popup test that existed covered TWO hand-picked
    fields; the clipping defect lived in a THIRD. A rule like 'no text
    may ever be clipped' must be asserted over the WHOLE registry, not a
    sample."""

    HARD_CAP_PX = 760

    def test_every_registered_field_renders_inside_the_screen(self):
        from zbemt.gui.help_content import FIELD_HELP
        from zbemt.gui.help_popup import HelpPopup
        host = QWidget()
        host.move(0, 0)
        host.resize(400, 300)
        host.show()
        popup = HelpPopup.instance(host)
        self.addCleanup(host.close)
        screen_w = self.win.screen().availableGeometry().width()
        cap = min(int(screen_w * 0.92), self.HARD_CAP_PX)
        bad = []
        for key in FIELD_HELP:
            popup.show_field(key, host)
            self.app.processEvents()
            if popup.frameGeometry().width() > cap + 1:
                bad.append(f"{key}: {popup.frameGeometry().width()}px > {cap}")
            for label in popup.findChildren(QLabel):
                if not label.wordWrap():
                    bad.append(f"{key}: unwrapped label {label.text()[:24]!r}")
            popup.close_popup()
        self.assertEqual(bad, [], str(bad[:6]))


class TestDocumentationStatesTheTruth(unittest.TestCase):
    """ESCAPE CLOSED: the docs tests check structure (links, numbering,
    anchors) but never TRUTH against the code -- so 'found through
    ZBEMT_XFOIL_BIN or PATH' survived three lookup places becoming four,
    and a removed field kept its section. Forbidden-stale-phrase and
    must-state checks pin the claims that already drifted once."""

    def test_no_stale_two_place_lookup_claim(self):
        with open(os.path.join(REPO, "docs", "documentation.html"),
                  encoding="utf-8") as handle:
            html = handle.read()
        self.assertNotIn("ZBEMT_XFOIL_BIN or PATH", html)

    def test_no_removed_geometry_spec_field_in_docs(self):
        with open(os.path.join(REPO, "docs", "documentation.html"),
                  encoding="utf-8") as handle:
            html = handle.read()
        self.assertNotIn("Geometry spec", html)

    def test_designer_chapter_opens_with_the_menu_path(self):
        with open(os.path.join(REPO, "docs", "documentation.html"),
                  encoding="utf-8") as handle:
            html = handle.read()
        start = html.index('id="cap-designer"')
        nxt = html.find("<h2", start + 1)
        chapter = html[start:nxt if nxt > start else len(html)]
        head = chapter[:3000]
        self.assertIn("Tools", head, "chapter must say WHICH menu")
        self.assertIn("Geometry Designer", head)
        self.assertIn("<ol", head, "opening must be a numbered how-to")


class TestGeneratorParamsRoundTripOnDisk(unittest.TestCase):
    """ESCAPE CLOSED: the analytic families were reachable in the GUI but
    nothing proved their parameters survive a save/open cycle -- the
    exact promise of `generator_params` (SC-10)."""

    def test_parsec_params_survive_save_and_open(self):
        from dataclasses import replace as dc_replace
        from tests.helpers import make_api_fast_project
        with tempfile.TemporaryDirectory() as tmp:
            project = make_api_fast_project(os.path.join(tmp, "proj"))
            contour = airfoils.generate_parsec(r_le=0.021, x_up=0.31)
            project.airfoil = dc_replace(project.airfoil, geometry=contour)
            api.save_project(project)
            reopened = api.open_project(project.path)
        geometry = reopened.airfoil.geometry
        self.assertEqual(geometry.source, "parsec")
        self.assertAlmostEqual(geometry.generator_params["r_le"], 0.021)
        self.assertAlmostEqual(geometry.generator_params["x_up"], 0.31)
        self.assertGreater(len(geometry.x), 10)


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
