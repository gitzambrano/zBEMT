"""Keep the Tools manual synchronized with labels and workflow of the real GUI."""
from __future__ import annotations

import html
import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import HAS_QT

if HAS_QT:  # pragma: no branch
    from PyQt6.QtWidgets import (
        QApplication,
        QCheckBox,
        QFormLayout,
        QPushButton,
        QRadioButton,
        QTableWidget,
    )

ROOT = Path(__file__).resolve().parents[2]


def _norm(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text or "")).split())


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestToolsDocumentationLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        from zbemt.gui.tabs.stability_window import StabilityWindow
        from zbemt.gui.tabs.transient_window import TransientWindow

        cls.windows = {
            "designer": GeometryDesignerWindow(AppState()),
            "optimizer": OptimizerWindow(AppState()),
            "transient": TransientWindow(AppState()),
            "stability": StabilityWindow(AppState()),
        }
        cls.document = (ROOT / "docs" / "documentation.html").read_text(
            encoding="utf-8")

    def _block(self, key: str) -> str:
        match = re.search(
            rf"<!-- TOOL-LABELS:{key} -->(.*?)<!-- /TOOL-LABELS:{key} -->",
            self.document,
            flags=re.S,
        )
        self.assertIsNotNone(match, f"missing generated Tool block for {key}")
        return match.group(1)

    def test_every_configurable_label_is_documented(self):
        from zbemt.gui.field_help import _widget_field

        for key, root in self.windows.items():
            block = self._block(key)
            for form in root.findChildren(QFormLayout):
                for index in range(form.rowCount()):
                    label_item = form.itemAt(index, QFormLayout.ItemRole.LabelRole)
                    role = (QFormLayout.ItemRole.SpanningRole if label_item is None
                            else QFormLayout.ItemRole.FieldRole)
                    field_item = form.itemAt(index, role)
                    widget = field_item.widget() if field_item is not None else None
                    if widget is None:
                        continue
                    field = _widget_field(widget)
                    if not field:
                        continue
                    if (label_item is not None and label_item.widget() is not None
                            and hasattr(label_item.widget(), "text")):
                        label = label_item.widget().text()
                    elif isinstance(widget, (QCheckBox, QRadioButton)):
                        label = widget.text()
                    else:
                        label = field
                    rows = re.findall(
                        rf'<tr data-field="{re.escape(field)}">(.*?)</tr>',
                        block,
                        flags=re.S,
                    )
                    with self.subTest(tool=key, field=field, label=_norm(label)):
                        self.assertTrue(rows)
                        self.assertTrue(any(_norm(label) in _norm(row) for row in rows))

            for widget_type in (QCheckBox, QRadioButton):
                for widget in root.findChildren(widget_type):
                    field = _widget_field(widget)
                    if not field:
                        continue
                    rows = re.findall(
                        rf'<tr data-field="{re.escape(field)}">(.*?)</tr>',
                        block,
                        flags=re.S,
                    )
                    with self.subTest(tool=key, field=field,
                                      label=_norm(widget.text())):
                        self.assertTrue(rows)
                        self.assertTrue(any(
                            _norm(widget.text()) in _norm(row) for row in rows))

    def test_guided_step_titles_are_documented(self):
        for key, root in self.windows.items():
            block = _norm(self._block(key))
            for title, _guidance in root.workflow_header.steps:
                with self.subTest(tool=key, step=title):
                    self.assertIn(_norm(title), block)

    def test_action_labels_are_documented(self):
        for key, root in self.windows.items():
            block = _norm(self._block(key))
            workflow_buttons = set(
                root.workflow_header.findChildren(QPushButton))
            for button in root.findChildren(QPushButton):
                if button in workflow_buttons:
                    continue
                label = _norm(button.text())
                if not label:
                    continue
                with self.subTest(tool=key, action=label):
                    self.assertIn(label, block)

    def test_table_column_labels_are_documented(self):
        for key, root in self.windows.items():
            block = _norm(self._block(key))
            for table in root.findChildren(QTableWidget):
                for column in range(table.columnCount()):
                    item = table.horizontalHeaderItem(column)
                    label = _norm(item.text()) if item is not None else ""
                    if not label:
                        continue
                    with self.subTest(tool=key, table_label=label):
                        self.assertIn(label, block)

    def test_launcher_tasks_are_documented(self):
        match = re.search(
            r"<!-- TOOLS-LAUNCHER -->(.*?)<!-- /TOOLS-LAUNCHER -->",
            self.document,
            flags=re.S,
        )
        self.assertIsNotNone(match, "missing generated Tools launcher block")
        from zbemt.gui.tool_ux import _TOOLS
        visible = _norm(match.group(1))
        for title, _key, purpose, requires, produces in _TOOLS:
            with self.subTest(task=title):
                self.assertIn(_norm(title), visible)
                self.assertIn(_norm(purpose), visible)
                self.assertIn(_norm(requires), visible)
                self.assertIn(_norm(produces), visible)


if __name__ == "__main__":
    unittest.main()
