"""Temporary one-shot patch used by the notebook GUI audit."""
from pathlib import Path


def replace_once_or_verify(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 1:
        text = text.replace(old, new, 1)
        target.write_text(text, encoding="utf-8")
        return
    if count == 0 and new in text:
        return
    raise SystemExit(f"Unexpected replacement state in {path}: {count} old matches")


replace_once_or_verify(
    "zbemt/gui/tabs/optimizer_window.py",
    "from ..common import (AppState, CanvasHost, equalize_button_widths,\n"
    "                      show_error, show_all_options_in)",
    "from ..common import (AppState, CanvasHost, equalize_button_widths,\n"
    "                      show_error, show_all_options_in, in_scroll_area)",
)
replace_once_or_verify(
    "zbemt/gui/tabs/optimizer_window.py",
    "        tabs = QTabWidget(self)\n"
    "        tabs.addTab(self._build_definition_page(), \"Study\")\n"
    "        tabs.addTab(self._build_run_page(), \"Run and results\")",
    "        tabs = QTabWidget(self)\n"
    "        tabs.addTab(in_scroll_area(self._build_definition_page()), \"Study\")\n"
    "        tabs.addTab(in_scroll_area(self._build_run_page()), \"Run and results\")",
)

replace_once_or_verify(
    "zbemt/gui/tabs/transient_window.py",
    "from ..common import (AppState, CanvasHost, equalize_button_widths,\n"
    "                      install_rich_text_headings, show_error)",
    "from ..common import (AppState, CanvasHost, equalize_button_widths,\n"
    "                      install_rich_text_headings, show_error, in_scroll_area)",
)
replace_once_or_verify(
    "zbemt/gui/tabs/transient_window.py",
    "        tabs = QTabWidget(self)\n"
    "        tabs.addTab(self._build_trajectory_page(), \"Trajectory\")\n"
    "        tabs.addTab(self._build_run_page(), \"Run and results\")",
    "        tabs = QTabWidget(self)\n"
    "        tabs.addTab(in_scroll_area(self._build_trajectory_page()), \"Trajectory\")\n"
    "        tabs.addTab(in_scroll_area(self._build_run_page()), \"Run and results\")",
)

optimizer_test = Path("tests/regression/test_optimizer_window.py")
text = optimizer_test.read_text(encoding="utf-8")
if "class TestNotebookLayout(OptimizerWindowBase):" not in text:
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
    if text.count(marker) != 1:
        raise SystemExit("Optimizer test insertion point not unique")
    optimizer_test.write_text(text.replace(marker, addition + marker, 1),
                              encoding="utf-8")

small_test = Path("tests/regression/test_small_screen.py")
text = small_test.read_text(encoding="utf-8")
if "def test_the_optimizer_pages_are_scrollable" not in text:
    marker = "    def test_a_scrolled_page_still_reports_its_natural_size(self):\n"
    addition = """    def test_the_optimizer_pages_are_scrollable(self):
        from PyQt6.QtWidgets import QScrollArea, QTabWidget

        pages = self.window.optimizer_window.findChild(QTabWidget)
        self.assertIsNotNone(pages)
        for index in range(pages.count()):
            with self.subTest(page=pages.tabText(index)):
                self.assertIsInstance(pages.widget(index), QScrollArea)

    def test_the_transient_pages_are_scrollable(self):
        from PyQt6.QtWidgets import QScrollArea, QTabWidget

        pages = self.window.transient_window.findChild(QTabWidget)
        self.assertIsNotNone(pages)
        for index in range(pages.count()):
            with self.subTest(page=pages.tabText(index)):
                self.assertIsInstance(pages.widget(index), QScrollArea)

"""
    if text.count(marker) != 1:
        raise SystemExit("Small-screen test insertion point not unique")
    small_test.write_text(text.replace(marker, addition + marker, 1),
                          encoding="utf-8")
