"""Temporary one-shot patch used by the optimizer notebook audit."""
from pathlib import Path


src = Path("zbemt/gui/tabs/optimizer_window.py")
text = src.read_text(encoding="utf-8")
replacements = {
    "from ..common import (AppState, CanvasHost, equalize_button_widths,\n"
    "                      show_error, show_all_options_in)":
    "from ..common import (AppState, CanvasHost, equalize_button_widths,\n"
    "                      show_error, show_all_options_in, in_scroll_area)",
    "        tabs = QTabWidget(self)\n"
    "        tabs.addTab(self._build_definition_page(), \"Study\")\n"
    "        tabs.addTab(self._build_run_page(), \"Run and results\")":
    "        tabs = QTabWidget(self)\n"
    "        tabs.addTab(in_scroll_area(self._build_definition_page()), \"Study\")\n"
    "        tabs.addTab(in_scroll_area(self._build_run_page()), \"Run and results\")",
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one optimizer source match, found {count}: {old!r}")
    text = text.replace(old, new, 1)
src.write_text(text, encoding="utf-8")


test_path = Path("tests/regression/test_optimizer_window.py")
text = test_path.read_text(encoding="utf-8")
marker = "\n\nclass TestAlgorithmGating(OptimizerWindowBase):"
addition = """

class TestNotebookLayout(OptimizerWindowBase):
    def test_study_cost_estimate_is_reachable_on_notebook_screen(self):
        \"\"\"The Study page must scroll instead of clipping its last block.\"\"\"
        from PyQt6.QtWidgets import QScrollArea, QTabWidget

        self.window.resize(1100, 650)
        self.window.show()
        QApplication.processEvents()
        tabs = self.window.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        area = tabs.widget(0)
        self.assertIsInstance(area, QScrollArea)
        bar = area.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0,
                           \"the Study page must scroll at 1100x650\")
        bar.setValue(bar.maximum())
        QApplication.processEvents()
        top = self.window.cost_label.mapTo(
            area.viewport(), self.window.cost_label.rect().topLeft()).y()
        bottom = top + self.window.cost_label.height()
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(bottom, area.viewport().height() + 2)
"""
count = text.count(marker)
if count != 1:
    raise SystemExit(f"Expected one optimizer test insertion point, found {count}")
text = text.replace(marker, addition + marker, 1)
test_path.write_text(text, encoding="utf-8")
