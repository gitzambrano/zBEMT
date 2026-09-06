"""Synchronize the engineering-Tools documentation with the real GUI.

The four engineering Tools expose guided workflows, configurable fields and
user actions. This script instantiates the real PyQt widgets, inventories the
labels shown by those widgets, verifies that every configurable field resolves
to an existing manual anchor, writes generated reference blocks into
``docs/documentation.html``, keeps the corresponding durable requirements in
``docs/software_requirements.md``, and refreshes the official screenshots.

Run from the repository root::

    QT_QPA_PLATFORM=offscreen python tools/sync_tools_documentation.py

The architecture test ``test_tools_documentation_labels.py`` prevents the
manual from drifting away from the current GUI.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QPushButton,
    QRadioButton,
    QTableWidget,
)

from zbemt import geometry
from zbemt.gui import help_content
from zbemt.gui.common import AppState
from zbemt.gui.field_help import _widget_field
from zbemt.gui.field_help_data import field_anchor
from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
from zbemt.gui.tabs.optimizer_window import OptimizerWindow
from zbemt.gui.tabs.stability_window import StabilityWindow
from zbemt.gui.tabs.transient_window import TransientWindow
from zbemt.gui.tool_ux import ToolsLauncher, _TOOLS
from zbemt.models import AirfoilDef, FlightCondition, Project

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "documentation.html"
REQUIREMENTS_PATH = ROOT / "docs" / "software_requirements.md"
IMAGE_DIR = ROOT / "docs" / "img" / "gui"

PR14 = """- **PR-14 — Guided engineering Tools.** The Tools entry point presents each
  engineering Tool by the engineering question it answers, the input or
  prerequisite needed to start, and the result it produces. Each Tool window
  exposes an obvious numbered task sequence, current-action guidance, and
  Back/Next navigation while preserving direct step navigation for expert use.
  Advanced numerical tuning starts collapsed. An empty study teaches the first
  valid action instead of presenting an error. Method-inapplicable controls
  disappear as complete rows under PR-2 rather than remaining visibly blocked.
"""

DC12 = """- **DC-12** — The Engineering Tools launcher and the four Tool chapters stay
  synchronized with the real GUI. Their generated reference blocks document
  the current guided steps, every configurable control label, every Tool-owned
  action label, every table-column label, and every launcher card. Configurable
  labels link to their complete field documentation. The synchronizer is
  `tools/sync_tools_documentation.py`, and
  `tests/architecture/test_tools_documentation_labels.py` fails when the GUI
  and manual drift apart.
"""


def _plain(text: str) -> str:
    """Return visible plain text for one Qt/HTML string."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text or "")).split())


def _synchronize_requirements() -> None:
    """Ensure the durable requirements for the guided Tools are explicit."""
    document = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    if "**PR-14 — Guided engineering Tools.**" not in document:
        marker = "\n---\n\n## 3. Architectural Requirements"
        position = document.find(marker)
        if position < 0:
            raise RuntimeError("could not locate the end of Product Requirements")
        document = document[:position] + "\n" + PR14 + document[position:]
    if "**DC-12**" not in document:
        marker = "\n### 3.6 GUI tab behaviour"
        position = document.find(marker)
        if position < 0:
            raise RuntimeError("could not locate the end of Documentation requirements")
        document = document[:position] + DC12 + document[position:]
    REQUIREMENTS_PATH.write_text(document, encoding="utf-8")


def _inventory_fields(root) -> list[tuple[str, str, str, str]]:
    """Collect documented fields using labels shown by the actual widget."""
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
            elif isinstance(widget, (QCheckBox, QRadioButton)):
                label = widget.text()
            else:
                label = field
            add(field, label)

    for widget_type in (QCheckBox, QRadioButton):
        for widget in root.findChildren(widget_type):
            add(_widget_field(widget), widget.text())
    return rows


def _inventory_actions(root) -> list[str]:
    """Collect stable action labels shown by Tool-owned buttons."""
    workflow_buttons = set(root.workflow_header.findChildren(QPushButton))
    actions: list[str] = []
    seen: set[str] = set()
    for button in root.findChildren(QPushButton):
        if button in workflow_buttons:
            continue
        text = _plain(button.text())
        if not text or text in seen:
            continue
        seen.add(text)
        actions.append(text)
    return actions


def _inventory_table_headers(root) -> list[str]:
    """Collect non-empty column labels from Tool tables."""
    headers: list[str] = []
    seen: set[str] = set()
    for table in root.findChildren(QTableWidget):
        for column in range(table.columnCount()):
            item = table.horizontalHeaderItem(column)
            text = _plain(item.text()) if item is not None else ""
            if text and text not in seen:
                seen.add(text)
                headers.append(text)
    return headers


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


def _list_block(title: str, values: list[str], css_class: str) -> str:
    if not values:
        return ""
    items = "".join(f"<li>{html.escape(value)}</li>" for value in values)
    return f'<b>{title}</b><ul class="{css_class}">{items}</ul>'


def _tool_block(key: str, window, fields, actions, table_headers) -> str:
    steps = "".join(
        f"<li><b>{html.escape(title)}</b>: {html.escape(guidance)}</li>"
        for title, guidance in window.workflow_header.steps
    )
    table_rows = "".join(
        '<tr data-field="{}"><td><i>{}</i></td><td><code>{}</code></td>'
        '<td><a href="#{}">{}</a></td></tr>'.format(
            html.escape(field),
            html.escape(_plain(label)),
            html.escape(field),
            html.escape(anchor),
            html.escape(title),
        )
        for field, label, anchor, title in fields
    )
    return (
        f"<!-- TOOL-LABELS:{key} -->\n"
        '<div class="boxed tool-workflow-reference">'
        "<b>Guided workflow in the current GUI.</b> Use the numbered strip "
        "from left to right; the old tab bar is intentionally hidden."
        f"<ol>{steps}</ol>"
        "<b>Configurable labels in this Tool.</b> This table is generated "
        "from the actual GUI controls. Every configurable label links to its "
        "full explanation in this manual."
        '<div class="tablewrap"><table><thead><tr><th>GUI label</th>'
        "<th>Field</th><th>Full documentation</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div>"
        f'{_list_block("Action labels.", actions, "tool-action-labels")}'
        f'{_list_block("Table column labels.", table_headers, "tool-table-labels")}'
        "</div>\n"
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
    """Build a small valid project without importing the test suite."""
    geom = geometry.generate_tapered(
        root_chord_norm=0.10,
        tip_chord_norm=0.04,
        twist_root_deg=14.0,
        twist_tip_deg=2.0,
        root_cutout_norm=0.15,
        radius_m=1.0,
        n_stations=12,
    )
    airfoil = AirfoilDef(
        source="analytical",
        stall_model="clip",
        alpha_stall_pos_deg=15.0,
        alpha_stall_neg_deg=-6.0,
    )
    project = Project(
        name="documentation",
        geometry=geom,
        airfoil=airfoil,
        config=dict(Ne=8, Npsi=12, solver="fixed_point", max_iter=150),
    )
    project.saved_cases = [
        FlightCondition(name="Hover", collective_deg=8.0, rpm=800.0),
        FlightCondition(name="Cruise", mu_x=0.18, collective_deg=7.0,
                        rpm=800.0),
    ]
    state = AppState()
    state.project = project
    return state


def synchronize() -> None:
    _synchronize_requirements()
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
        fields = _inventory_fields(window)
        actions = _inventory_actions(window)
        table_headers = _inventory_table_headers(window)
        for field, _label, anchor, _title in fields:
            if f'id="{anchor}"' not in document:
                raise RuntimeError(
                    f"{key}: {field!r} points to missing manual anchor #{anchor}")
        document = _replace_tool_block(
            document,
            key,
            chapter,
            _tool_block(key, window, fields, actions, table_headers),
        )

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
    launcher_window.resize(700, 600)
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
