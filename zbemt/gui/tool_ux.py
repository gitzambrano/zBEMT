"""Shared UX components for the dedicated engineering Tools windows.

The main GUI is a sequential workflow.  The Tools are not: they answer
separate engineering questions and previously opened directly into dense
parameter editors.  This module gives them a task-oriented launcher and a
small workflow header without moving solver logic into the GUI.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)


_TOOLS = (
    (
        "Compare blade geometries",
        "geometry_designer",
        "Change one geometry parameter or compare planform concepts at the same operating conditions.",
        "Start with: a loaded project and blade geometry.",
        "Produces: ranked geometry comparisons, deltas and overlays.",
    ),
    (
        "Simulate a transient maneuver",
        "transient_simulation",
        "March inflow, dynamic stall and flapping through a time-varying flight condition.",
        "Start with: preferably two saved Run Case conditions.",
        "Produces: time histories and maneuver reports.",
    ),
    (
        "Optimize a blade design",
        "design_optimization",
        "Search geometry variables against one or two engineering objectives and constraints.",
        "Start with: at least one saved Run Case condition.",
        "Produces: the best design or a Pareto front.",
    ),
    (
        "Compute stability derivatives",
        "stability_derivatives",
        "Linearize rotor forces and moments around a selected operating point.",
        "Start with: a saved Run Case condition; trim it first when appropriate.",
        "Produces: dimensional/non-dimensional derivative matrices and sign checks.",
    ),
)


class ToolsLauncher(QDialog):
    """Task-oriented replacement for the old four-name Tools menu."""

    tool_requested = pyqtSignal(str)

    def __init__(self, state=None, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Engineering Tools")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.resize(650, 560)

        outer = QVBoxLayout(self)
        title = QLabel("Engineering Tools")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        outer.addWidget(title)
        intro = QLabel(
            "Start from the engineering question, not from a parameter editor. "
            "Each tool uses the project currently open in zBEMT."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #777; margin-bottom: 6px;")
        outer.addWidget(intro)

        self.tool_buttons: dict[str, QPushButton] = {}
        for title_text, key, purpose, requires, produces in _TOOLS:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            row = QHBoxLayout(card)
            copy = QVBoxLayout()
            heading = QLabel(f"<b>{title_text}</b>")
            purpose_label = QLabel(purpose)
            purpose_label.setWordWrap(True)
            meta = QLabel(f"{requires}<br>{produces}")
            meta.setWordWrap(True)
            meta.setStyleSheet("color: #777; font-size: 11px;")
            copy.addWidget(heading)
            copy.addWidget(purpose_label)
            copy.addWidget(meta)
            row.addLayout(copy, 1)
            button = QPushButton("Open")
            button.setMinimumWidth(82)
            button.setSizePolicy(QSizePolicy.Policy.Fixed,
                                 QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, k=key: self._choose(k))
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
            outer.addWidget(card)
            self.tool_buttons[key] = button
        outer.addStretch(1)

    def _choose(self, key: str):
        self.tool_requested.emit(key)
        self.hide()


class ToolWorkflowHeader(QFrame):
    """Numbered task steps with explicit current-action guidance.

    The native tab bar is hidden: the numbered buttons below are the
    navigation, so a Tool no longer shows two competing navigation systems.
    """

    def __init__(self, tabs, steps, parent: QWidget | None = None):
        super().__init__(parent)
        self.tabs = tabs
        self.steps = list(steps)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(5)

        row = QHBoxLayout()
        self._step_buttons = []
        for i, (title, _guidance) in enumerate(self.steps):
            button = QPushButton(f"{i + 1}. {title}")
            button.setFlat(True)
            button.clicked.connect(
                lambda _checked=False, index=i: self.tabs.setCurrentIndex(index))
            row.addWidget(button)
            self._step_buttons.append(button)
        row.addStretch(1)
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Next")
        self.back_button.clicked.connect(self._back)
        self.next_button.clicked.connect(self._next)
        row.addWidget(self.back_button)
        row.addWidget(self.next_button)
        outer.addLayout(row)

        self.guidance = QLabel()
        self.guidance.setWordWrap(True)
        outer.addWidget(self.guidance)

        self.tabs.tabBar().setVisible(False)
        self.tabs.currentChanged.connect(self._sync)
        self._sync(self.tabs.currentIndex())

    def _sync(self, index: int):
        if not self.steps:
            return
        index = max(0, min(index, len(self.steps) - 1))
        for i, button in enumerate(self._step_buttons):
            if i == index:
                button.setStyleSheet(
                    "font-weight: 700; border: 1px solid #888; border-radius: 4px; padding: 4px 8px;")
            else:
                button.setStyleSheet(
                    "font-weight: 400; border: 1px solid transparent; padding: 4px 8px;")
        title, guidance = self.steps[index]
        self.guidance.setText(f"<b>Do this now:</b> {guidance}")
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < len(self.steps) - 1)
        if index < len(self.steps) - 1:
            self.next_button.setText(f"Next: {self.steps[index + 1][0]}")

    def _back(self):
        self.tabs.setCurrentIndex(max(0, self.tabs.currentIndex() - 1))

    def _next(self):
        self.tabs.setCurrentIndex(
            min(self.tabs.count() - 1, self.tabs.currentIndex() + 1))
