"""Item 5, finding 2: the variant table's chord cells must match what
the base planform can actually read — a rectangular base gets one
'Chord c/R' column, an elliptic one 'Max chord c/R', and in both cases
the tip-chord cell is disabled with a tooltip saying why, instead of
accepting a value that would be silently dropped.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import HAS_QT

if HAS_QT:                                        # pragma: no branch
    from PyQt6.QtWidgets import QApplication

from tests.helpers import make_studies_project


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestChordCellGating(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window_for_base(self, kind):
        from dataclasses import replace
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        project = make_studies_project()
        origin = dict(project.geometry.origin_params)
        origin["kind"] = kind
        project.geometry = replace(project.geometry,
                                    origin_params=origin)
        state = AppState()
        state.set_project(project)
        window = GeometryDesignerWindow(state)
        self.addCleanup(window.deleteLater)
        return window, project

    def _tip_flags(self, window):
        item = window.variants_table.item(0,
                                           window._COL_TIP_CHORD)
        return item.flags()

    def test_rectangular_renames_root_header_and_disables_tip(self):
        window, _project = self._window_for_base("rectangular")
        self.assertEqual(
            window.variants_table.horizontalHeaderItem(
                window._COL_ROOT_CHORD).text(),
            "Chord c/R")
        flags = self._tip_flags(window)
        self.assertFalse(bool(flags & __import__("PyQt6.QtCore",
                                                  fromlist=["Qt"]).Qt.ItemFlag.ItemIsEditable))

    def test_elliptic_names_the_peak_and_disables_tip(self):
        window, _project = self._window_for_base("elliptic")
        self.assertEqual(
            window.variants_table.horizontalHeaderItem(
                window._COL_ROOT_CHORD).text(),
            "Max chord c/R")
        flags = self._tip_flags(window)
        self.assertFalse(bool(flags & __import__("PyQt6.QtCore",
                                                  fromlist=["Qt"]).Qt.ItemFlag.ItemIsEditable))

    def test_tapered_keeps_both_cells_editable(self):
        window, _project = self._window_for_base("tapered")
        self.assertEqual(
            window.variants_table.horizontalHeaderItem(
                window._COL_ROOT_CHORD).text(),
            "Root chord c/R")
        flags = self._tip_flags(window)
        self.assertTrue(bool(flags & __import__("PyQt6.QtCore",
                                                 fromlist=["Qt"]).Qt.ItemFlag.ItemIsEditable))


if __name__ == "__main__":
    unittest.main()
