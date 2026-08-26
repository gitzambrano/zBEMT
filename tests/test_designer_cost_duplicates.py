"""Item 5, phase 5.2: cost estimate timed from a real solve, and the
duplicate-variant warning that names both labels without blocking."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from tests.helpers import make_studies_project


class TestCostAndDuplicates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, project=None):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        state = AppState()
        if project is not None:
            state.set_project(project)
        window = GeometryDesignerWindow(state)
        self.addCleanup(window.deleteLater)
        return window

    def test_summary_includes_a_timed_wall_estimate(self):
        project = make_studies_project()
        window = self._window(project)
        if window.variants_table.rowCount() == 0:
            window.variants_table.setRowCount(1)   # the base row exists
        window._cached_solve_seconds = None   # force a fresh timing solve
        with patch("zbemt.api.run_case", return_value=None) as fake:
            window._update_summary_label()
        self.assertTrue(fake.called, "the estimate must time one solve")
        text = window.summary_label.text()
        self.assertIn("min at", text)
        self.assertIn("s/solve", text)

    def test_duplicate_variants_warn_with_both_labels(self):
        import numpy as np
        from dataclasses import replace
        project = make_studies_project()
        window = self._window(project)
        base = window._session_base_geometry()
        twin = replace(base)
        variants = {"base": base, "twin": twin}
        shown = {}

        def fake_warning(parent, title, text, *a, **k):
            shown["title"] = title
            shown["text"] = text
            from PyQt6.QtWidgets import QMessageBox
            return QMessageBox.StandardButton.Ok

        with patch("zbemt.gui.tabs.designer_window.QMessageBox.warning",
                    side_effect=fake_warning):
            window._warn_duplicate_variants(variants)
        self.assertEqual(shown.get("title"), "Duplicate variants")
        self.assertIn("'base'", shown["text"])
        self.assertIn("'twin'", shown["text"])

    def test_distinct_variants_stay_silent(self):
        from dataclasses import replace
        project = make_studies_project()
        window = self._window(project)
        base = window._session_base_geometry()
        other = replace(base, n_blades=base.n_blades + 1)
        called = []
        with patch("zbemt.gui.tabs.designer_window.QMessageBox.warning",
                    side_effect=lambda *a, **k: called.append(1)):
            window._warn_duplicate_variants(
                {"base": base, "other": other})
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
