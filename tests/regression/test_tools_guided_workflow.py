from __future__ import annotations
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:
    _HAS_QT = False

if _HAS_QT:
    from zbemt.gui.common import AppState
    from zbemt.gui.tool_ux import ToolWorkflowHeader, ToolsLauncher
    from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
    from zbemt.gui.tabs.transient_window import TransientWindow
    from zbemt.gui.tabs.optimizer_window import OptimizerWindow
    from zbemt.gui.tabs.stability_window import StabilityWindow


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestGuidedToolsUX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_launcher_is_task_oriented(self):
        launcher = ToolsLauncher(AppState())
        self.addCleanup(launcher.deleteLater)
        self.assertEqual(set(launcher.tool_buttons), {
            "geometry_designer", "transient_simulation",
            "design_optimization", "stability_derivatives"})
        visible_copy = " ".join(
            w.text() for w in launcher.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel))
        self.assertIn("engineering question", visible_copy.lower())
        self.assertIn("Produces:", visible_copy)

    def _assert_guided(self, window, expected_steps):
        self.addCleanup(window.deleteLater)
        self.assertIsInstance(window.workflow_header, ToolWorkflowHeader)
        self.assertEqual(len(window.workflow_header.steps), expected_steps)
        self.assertFalse(window.pages.tabBar().isVisible())
        if expected_steps > 1:
            window.workflow_header.next_button.click()
            self.assertEqual(window.pages.currentIndex(), 1)
            window.workflow_header.back_button.click()
            self.assertEqual(window.pages.currentIndex(), 0)

    def test_all_tools_have_guided_workflows(self):
        state = AppState()
        self._assert_guided(GeometryDesignerWindow(state), 3)
        self._assert_guided(TransientWindow(state), 2)
        self._assert_guided(OptimizerWindow(state), 2)
        self._assert_guided(StabilityWindow(state), 3)

    def test_optimizer_hides_numerical_tuning_by_default(self):
        window = OptimizerWindow(AppState())
        self.addCleanup(window.deleteLater)
        self.assertTrue(window.advanced_search_box.isCheckable())
        self.assertFalse(window.advanced_search_box.isChecked())
        self.assertEqual(window.obj_keys[1].itemData(0), "")

    def test_stability_does_not_expose_placeholder_workers(self):
        window = StabilityWindow(AppState())
        self.addCleanup(window.deleteLater)
        self.assertIsNone(window.workers_spin.parentWidget())

    def test_transient_empty_state_is_instructive(self):
        window = TransientWindow(AppState())
        self.addCleanup(window.deleteLater)
        window._update_validation_panel()
        self.assertIn("Start by", window.validation_panel.toPlainText())
