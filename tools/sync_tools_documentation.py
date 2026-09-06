"""Synchronize the Tools chapters of ``docs/documentation.html`` with the GUI.

The four engineering Tools expose a guided workflow and many documented form
fields.  This script instantiates the real PyQt widgets, inventories their
configurable labels, verifies that every field resolves to an existing manual
anchor, writes an exact label reference into each Tool chapter, and refreshes
screenshots of the current layout.

Run from the repository root::

    QT_QPA_PLATFORM=offscreen python tools/sync_tools_documentation.py

The architecture test ``test_tools_documentation_labels.py`` prevents the
manual from drifting away from these generated blocks.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QCheckBox, QFormLayout

from tests.helpers import make_studies_project
from zbemt.gui import help_content
from zbemt.gui.common import AppState
from zbemt.gui.field_help import _widget_field
from zbemt.gui.field_help_data import field_anchor
from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
from zbemt.gui.tabs.optimizer_window import OptimizerWindow
from zbemt.gui.tabs.stability_window import StabilityWindow
from zbemt.gui.tabs.transient_window import TransientWindow
from zbemt.gui.tool_ux import ToolsLauncher, _TOOLS
from zbemt.models import FlightCondition

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "documentation.html"
IMAGE_DIR = ROOT / "docs" / "img" / "gui"


def _plain(text: str) -> str:
    """Return the visible text of a Qt/HTML label."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text or "")).split())


def _inventory(root) -> list[tuple[str, str, str, str]]:
    """Collect documented fields using the labels shown by the actual widget."""
    rows: list[tuple[str, str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(field: str | None, label: str) -> None:
        if not field:
            return
        key = (field, _plain(label))
        if key in seen:
            return
        seen.add(key)
        meta = help_content.FIELD_HELP.get(field, {})
        anchor = meta.get("anchor") or field_anchor(field)
        if not anchor:
            raise RuntimeError(
                f"{root.windowTitle()}: field {field!r} has no documentation anchor")
        rows.append((field, label or field, anchor, meta.get("title", field)))

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
            elif isinstance(widget, QCheckBox):
                label = widget.text()
            else:
                label = field
            add(field, label)

    # Documented checkboxes may live outside QFormLayout.
    for checkbox in root.findChildren(QCheckBox):
        add(_widget_field(checkbox), checkbox.text())
    return rows


def _replace_tool_block(document: str, key: str, chapter: str,
                        block: str) -> str:
    start = f"<!-- TOOL-LABELS:{key} -->"
    end = f"<!-- /TOOL-LABELS:{key} -->"
    if start in document:
        return re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _match: block,
            document,
            flags=re.S,
        )
    heading = re.compile(rf'(<h2 id="{re.escape(chapter)}">.*?</h2>)')
    match = heading.search(document)
    if not match:
        raise RuntimeError(f"manual chapter #{chapter} was not found")
    return document[:match.end()] + "\n" + block + document[match.end():]


def _tool_block(key: str, window, rows) -> str:
    steps = "".join(
        f"<li><b>{html.escape(title)}</b>: {html.escape(guidance)}</li>"
        for title, guidance in window.workflow_header.steps
    )
    table_rows = "".join(
        '<tr data-field="{}"><td><i>{}</i></td><td><code>{}</code></td>'
        '<td><a href="#{}">{}</a></td></tr>'.format(
            html.escape(field),
            label,
            html.escape(field),
            html.escape(anchor),
            html.escape(title),
        )
        for field, label, anchor, title in rows
    )
    return (
        f"<!-- TOOL-LABELS:{key} -->\n"
        '<div class="boxed tool-workflow-reference">'
        "<b>Guided workflow in the current GUI.</b> Use the numbered strip "
        "from left to right; the old tab bar is intentionally hidden."
        f"<ol>{steps}</ol>"
        "<b>Labels in this Tool.</b> This table is generated from the actual "
        "GUI controls. Each configurable label links to its full explanation "
        "in this manual."
        '<div class="tablewrap"><table><thead><tr><th>GUI label</th>'
        "<th>Field</th><th>Full documentation</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div></div>\n"
        f"<!-- /TOOL-LABELS:{key} -->"
    )


def _launcher_block() -> str:
    cards = "".join(
        '<li data-tool="{}"><b>{}</b> — {} <span class="footnote">{} {}</span></li>'.format(
            html.escape(key),
            html.escape(title),
            html.escape(purpose),
            html.escape(requires),
            html.escape(produces),
        )
        for title, key, purpose, requires, produces in _TOOLS
    )
    return (
        '<!-- TOOLS-LAUNCHER -->\n<div class="boxed" '
        'id="engineering-tools-launcher"><b>Engineering Tools launcher.</b> '
        "Open <i>Tools</i> and start from the engineering question. Each card "
        "states what is required and what the Tool produces."
        f"<ul>{cards}</ul>"
        '<figure><img src="img/gui/tools-launcher.png" '
        'alt="Engineering Tools launcher">'
        "<figcaption>The task-oriented launcher for the four engineering "
        "Tools.</figcaption></figure></div>\n<!-- /TOOLS-LAUNCHER -->"
    )


def _project_state() -> AppState:
    state = AppState()
    project = make_studies_project()
    if len(project.saved_cases) < 2:
        project.saved_cases = [
            FlightCondition(name="Hover", collective_deg=8.0, rpm=800.0),
            FlightCondition(name="Cruise", mu_x=0.18, collective_deg=7.0,
                            rpm=800.0),
        ]
    state.project = project
    return state


def synchronize() -> None:
    app = QApplication.instance() or QApplication([])
    state = _project_state()
    windows = {
        "designer": (GeometryDesignerWindow(state), "cap-designer"),
        "optimizer": (OptimizerWindow(state), "cap-optimization"),
        "transient": (TransientWindow(state), "cap-transiente"),
        "stability": (StabilityWindow(state), "cap-stability"),
    }

    document = DOC_PATH.read_text(encoding="utf-8")
    for key, (window, chapter) in windows.items():
        rows = _inventory(window)
        for field, _label, anchor, _title in rows:
            if f'id="{anchor}"' not in document:
                raise RuntimeError(
                    f"{key}: {field!r} points to missing manual anchor #{anchor}")
        document = _replace_tool_block(
            document, key, chapter, _tool_block(key, window, rows))

    launcher = _launcher_block()
    start = "<!-- TOOLS-LAUNCHER -->"
    end = "<!-- /TOOLS-LAUNCHER -->"
    if start in document:
        document = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _match: launcher,
            document,
            flags=re.S,
        )
    else:
        position = document.find('<h2 id="cap-designer">')
        if position < 0:
            raise RuntimeError("manual chapter #cap-designer was not found")
        document = document[:position] + launcher + "\n\n" + document[position:]
    DOC_PATH.write_text(document, encoding="utf-8")

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    launcher_window = ToolsLauncher(state)
    launcher_window.show()
    for _ in range(20):
        app.processEvents()
    if not launcher_window.grab().save(str(IMAGE_DIR / "tools-launcher.png")):
        raise RuntimeError("could not save Tools launcher screenshot")
    launcher_window.hide()

    names = {
        "designer": "designer.png",
        "optimizer": "optimizer.png",
        "transient": "transient.png",
        "stability": "stability.png",
    }
    for key, (window, _chapter) in windows.items():
        window.resize(1366, 768)
        window.show()
        window.pages.setCurrentIndex(0)
        for _ in range(30):
            app.processEvents()
        if not window.grab().save(str(IMAGE_DIR / names[key])):
            raise RuntimeError(f"could not save {key} screenshot")
        window.hide()


if __name__ == "__main__":
    synchronize()
