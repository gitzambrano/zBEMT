"""
Main GUI window (PyQt6).

Seven tabs, one per subject, in the natural work order:

    Project -> Geometry -> Airfoil -> Config/Engine -> Run Case ->
    Run Batch -> Results

The geometry-comparison tool (the former Design tab) lives in its own
window, opened from the Tools menu ("Geometry Designer"); design
optimization stays available through the CLI and the library only.

Each tab lives in ``zbemt/gui/tabs/``; this module only assembles them,
wires the shortcuts and maintains the ``FlowIndicatorBar`` (the
per-stage validation traffic light).

HARD RULE: no physics, no solver computation, no file read or write
lives in the GUI -- everything goes through ``zbemt.api``. Explicit
exception: purely preview operations (generating a NACA geometry to draw,
plotting Cl(alpha) from a freshly imported table) may call
``geometry``/``airfoils`` directly, because they do not run the solver nor touch disk.

Design principles, valid across every tab:
  1. Progressive disclosure -- no field appears before it makes sense.
  2. Rotor vs Propeller is decided once (Project tab) and propagates.
  3. A single source of truth per piece of data.
  4. Each setting lives next to the control that enables it.
  5. Results is the only tab with drawing on screen.

Execution: ``zbemt-gui`` or ``python -m zbemt.gui.app``.

For compatibility, this module re-exports the tabs' and infrastructure's
public names: ``from zbemt.gui import app as gui; gui.AirfoilTab`` still
works.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import QLocale, QCoreApplication, Qt, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence

from .. import validation
from . import styles

from .tabs import (
    ProjectTab,
    GeometryTab,
    AirfoilTab,
    ConfigMotorTab,
    RunCaseTab,
    RunBatchTab,
    ResultsTab,
)
# The geometry-comparison tool lives in its own window, not in a tab:
# it is wired by this module (Tools > Geometry Designer).
from .tabs.designer_window import GeometryDesignerWindow
from .common import AppState, open_help
from .wheel_guard import install_wheel_guard, adjust_focus_policy

# --- compatibility re-export ------------------------------------
# `zbemt.gui.app` was, throughout the project's whole lifetime, the GUI's
# single module; scripts and tests do `from zbemt.gui import app as gui`
# and then access any class from it. The names below are not used HERE --
# they exist so that access keeps working after the split into modules
# (item S1). A linter will call them dead imports: they are deliberate,
# do not remove.
from .common import (  # noqa: F401
    PROJECTS_ROOT, parse_list, show_error, MplCanvas, CanvasHost,
    require_project, confirm_run_despite_issues,
)
from .workers import (  # noqa: F401
    BatchRunnerWorker, ExternalPolarWorker, CompareWorker,
    launch_worker,
)
from .dialogs import GeometryGeneratorDialog  # noqa: F401
from .widgets import LongitudinalInput, AxialInput  # noqa: F401

#: Modules that define widgets and therefore have their own `QMessageBox`
#: (or `QInputDialog`) bound at import time. A test that needs to silence
#: modal dialogs has to patch ALL of them -- patching the name only here
#: does not reach the tabs. See `tests/helpers.patch_message_box_everywhere`.
GUI_MODULES = (
    "zbemt.gui.common", "zbemt.gui.dialogs", "zbemt.gui.widgets",
    "zbemt.gui.tabs.project", "zbemt.gui.tabs.geometry_tab",
    "zbemt.gui.tabs.airfoil", "zbemt.gui.tabs.config",
    "zbemt.gui.tabs.run_case", "zbemt.gui.tabs.run_batch",
    "zbemt.gui.tabs.designer_window",
    "zbemt.gui.tabs.results",
)


# =============================================================================
# Flow indicator bar between tabs (docs/plano_v3.md Part 6.2)
# =============================================================================

class FlowIndicatorBar(QWidget):
    """Project/Geometry/Airfoil/Config/Run Case/Run Batch/Results
    markers, colored by state (gray/amber/green/red).
    Click jumps straight to the tab. It does not lock free navigation."""

    #: Emitted by the Tools button (next to Help). The dedicated design
    #: windows live OUTSIDE the tab flow, and the old QMenuBar entry
    #: point rendered nearly invisible under the dark theme (dark-gray
    #: text on the black strip), so the menu is gone: the button IS the
    #: entry point now.
    tools_requested = pyqtSignal()

    _STAGES = ["Project", "Geometry", "Airfoil", "Config/Engine", "Run Case",
               "Run Batch", "Results"]

    #: The seven pills have the SAME width, and the width is measured (not
    #: fixed): "Project" and "Config/Engine" differ by approximately 50 px, and
    #: colored pills of different sizes read as different things,
    #: not as stages of the same flow. The measurement comes from the
    #: real `sizeHint`, after the QSS polish -- see `showEvent`.
    STAGE_HEIGHT = 26
    VERTICAL_MARGIN = 6
    STAGE_SPACING = 6

    def __init__(self, state: AppState, tabs: QTabWidget):
        super().__init__()
        self.state = state
        self.tabs = tabs
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, self.VERTICAL_MARGIN, 6, self.VERTICAL_MARGIN)
        layout.setSpacing(self.STAGE_SPACING)
        self._buttons: list[QPushButton] = []
        for i, name in enumerate(self._STAGES):
            btn = QPushButton(name)
            btn.setFlat(True)
            btn.setFixedHeight(self.STAGE_HEIGHT)
            # centered in the strip: without this the button stretches
            # vertically and the colored pill touches the top and bottom edges
            btn.setSizePolicy(QSizePolicy.Policy.Preferred,
                               QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _checked, i=i: self.tabs.setCurrentIndex(i))
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._buttons.append(btn)
        layout.addStretch(1)

        # Tools: same pill style and size as Help, immediately to its
        # left. Opens the dedicated design window directly -- no menu
        # bar (it hid itself against the dark strip; a dead entry point
        # is worse than none).
        self.btn_tools = QPushButton("Tools")
        self.btn_tools.setFlat(True)
        self.btn_tools.setMinimumWidth(54)
        self.btn_tools.setToolTip(
            "Tools: opens the Geometry Designer (compare blade variants)")
        self.btn_tools.setStyleSheet(
            "QPushButton { font-weight: bold; border: 1px solid #888; border-radius: 14px; }")
        self.btn_tools.clicked.connect(self.tools_requested.emit)
        layout.addWidget(self.btn_tools)

        # Global access to the documentation: explicit text, without the
        # ambiguous question-mark affordance. Fields and block titles
        # still open contextual help; this one opens the full index.
        self.btn_help = QPushButton("Help")
        self.btn_help.setFlat(True)
        self.btn_help.setMinimumWidth(54)
        self.btn_help.setToolTip("Help: features, shortcuts and physics of zBEMT (F1)")
        self.btn_help.setStyleSheet(
            "QPushButton { font-weight: bold; border: 1px solid #888; border-radius: 14px; }")
        self.btn_help.clicked.connect(lambda: open_help(self))
        layout.addWidget(self.btn_help)

        self.state.project_changed.connect(self.refresh)
        self.state.geometry_changed.connect(self.refresh)
        self.state.airfoil_changed.connect(self.refresh)
        self.state.config_changed.connect(self.refresh)
        self.state.history_changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event):
        """Equalizes the width of the seven pills on the FIRST display.

        After the QSS polish, and not before: only then does a button's
        `sizeHint` include the theme's padding (same pitfall as
        `common.equalize_button_widths`, and the same reason the
        width is not a constant in the code -- it changes with the font,
        the theme and the monitor's scale)."""
        super().showEvent(event)
        if getattr(self, "_stage_widths_revised", False):
            return
        self._stage_widths_revised = True
        self._equalize_stage_widths()

    def _equalize_stage_widths(self):
        width = max(
            [b.sizeHint().width() for b in self._buttons]
            + [b.minimumSizeHint().width() for b in self._buttons])
        for btn in self._buttons:
            btn.setMinimumWidth(width)
            # `setFixedWidth` would be overridden by any `max-width` rule
            # from the stylesheet (this is exactly what happened with the
            # Run Batch buttons); the min+max pair is not.
            btn.setMaximumWidth(width)

    #: Why the stage is in that color. Without this, the bar painted Run
    #: Case and Results amber with nothing anywhere saying what that
    #: means -- and amber on an engineering panel reads as "warning",
    #: which is not the case: it only means the result predates the
    #: still-unsaved edit.
    _DEFAULT_EXPLANATIONS = {
        "gray": "Nothing here yet.",
        "green": "Ready.",
        "amber": "Check the warnings on this tab.",
        "red": "This tab has an error that blocks running.",
    }

    def _set_status(self, index: int, status: str, explanation: str | None = None):
        color = styles.STATUS_COLORS[status]
        button = self._buttons[index]
        button.setStyleSheet(
            f"QPushButton {{ color: white; background: {color}; border-radius: 3px; padding: 3px 8px; }}")
        tip_text = explanation or self._DEFAULT_EXPLANATIONS.get(status, "")
        button.setToolTip(f"{self._STAGES[index]} — {tip_text}" if tip_text else self._STAGES[index])

    def refresh(self):
        project = self.state.project
        if project is None:
            for i in range(len(self._STAGES)):
                self._set_status(i, "gray")
            self._set_status(0, "gray")
            return
        self._set_status(0, "green")   # Project: exists and is loaded

        self._set_status(1, "green" if len(project.geometry.r_norm) >= 2 else "red")

        if project.airfoil_sections:
            issues = validation.validate_airfoil_sections(project.airfoil_sections)
        else:
            issues = validation.validate_airfoil_def(project.airfoil)
        self._set_status(2, self._status_from_issues(issues))

        cfg_issues = validation.validate_config(project.config, project.airfoil)
        self._set_status(3, self._status_from_issues(cfg_issues))

        has_case = any(e.kind == "case" for e in self.state.results_history)
        has_batch = any(e.kind == "batch" for e in self.state.results_history)
        stale = bool(self.state.unsaved)
        # The amber on these three stages is NOT a validation warning: it
        # means "a result exists, but the project changed after it was computed".
        STALE_MESSAGE = ("Results were computed before the current unsaved "
                         "edits. Run again to match the project as it is now.")
        for index, exists, empty_message in (
                (4, has_case, "No case has been run yet."),
                (5, has_batch, "No batch has been run yet."),
                (6, bool(self.state.results_history),
                 "No results to show yet.")):
            if not exists:
                self._set_status(index, "gray", empty_message)
            elif stale:
                self._set_status(index, "amber", STALE_MESSAGE)
            else:
                self._set_status(index, "green",
                                  "Results are up to date with the saved project.")

    @staticmethod
    def _status_from_issues(issues: list) -> str:
        if any(i.level == "error" for i in issues):
            return "red"
        if any(i.level == "warning" for i in issues):
            return "amber"
        return "green"


def _title_block(blocks: dict, title: str) -> str | None:
    """Help block id for a groupbox's title.

    Matches the whole title first and, only if that fails, the portion
    before the first parenthesis: some titles carry a counter that
    changes at runtime ("2. Case queue (empty)" -> "(3)") or an
    explanatory phrase that a copy revision rewrites. Matching only the
    exact string made these blocks' help vanish without warning.
    """
    title = title.strip()
    if title in blocks:
        return blocks[title]
    return blocks.get(title.split(" (")[0].strip())


# =============================================================================
# Main window
# =============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Integrated Aerodynamic Platform — zBEMT")
        self.resize(1360, 860)
        self.setMinimumSize(1024, 680)

        self.state = AppState()
        self._wheel_guard = install_wheel_guard(QApplication.instance())

        geometry_tab = GeometryTab(self.state)
        airfoil_tab = AirfoilTab(self.state)
        config_tab = ConfigMotorTab(self.state)

        self.tabs = QTabWidget()
        self.tabs.addTab(ProjectTab(self.state), "Project")
        self.tabs.addTab(geometry_tab, "Geometry")
        self.tabs.addTab(airfoil_tab, "Airfoil")
        self.tabs.addTab(config_tab, "Config/Engine")
        self.tabs.addTab(RunCaseTab(self.state), "Run Case")
        self.tabs.addTab(RunBatchTab(self.state), "Run Batch")
        self.tabs.addTab(ResultsTab(self.state, geometry_tab, airfoil_tab), "Results")
        adjust_focus_policy(self)
        # Bug 1: the FlowIndicatorBar already serves as navigation between
        # tabs; hiding the native tabBar() removes the visual duplication.
        self.tabs.tabBar().setVisible(False)

        # "Not saved to disk" asterisk on the tab title: Geometry,
        # Airfoil and Config/Engine apply every edit live to
        # `state.project` (no "Apply" button), so the per-tab asterisk is
        # just a visual mirror of `state.unsaved` -- `unsaved_work`
        # uses `state.unsaved` as the single source, it does not add one
        # item per tab. Run Case/Run Batch have no project field to
        # apply (running already uses the form directly), so there is no
        # "dirty" state to track there.
        geometry_tab.dirty_changed.connect(lambda dirty: self._set_tab_dirty(1, "Geometry", dirty))
        airfoil_tab.dirty_changed.connect(lambda dirty: self._set_tab_dirty(2, "Airfoil", dirty))
        config_tab.dirty_changed.connect(lambda dirty: self._set_tab_dirty(3, "Config/Engine", dirty))
        # Per-field popups: clickable labels in every tab's QFormLayout.
        from .field_help import install_field_popups
        from .common import (compact_form_fields, ensure_button_legibility,
                              ensure_row_spacing, align_form_labels,
                              show_all_options_in)
        for i in range(self.tabs.count()):
            install_field_popups(self.tabs.widget(i))
            # Reading width for numeric/enumeration fields: a window-level
            # policy, applied from the outside, so that the same quantity
            # has the same box in every tab (see
            # `common.compact_form_fields`).
            compact_form_fields(self.tabs.widget(i))
            # Minimum width per button, same reason and same place: nine
            # buttons scattered across the tabs had their label elided.
            ensure_button_legibility(self.tabs.widget(i))
            # Minimum row spacing, likewise: checkbox rows were sticking
            # to the following field row.
            ensure_row_spacing(self.tabs.widget(i))
            # Left-aligned labels, likewise: right-justified (style
            # default) makes each label's initial fall in a different column.
            align_form_labels(self.tabs.widget(i))
            # Every dropdown opens showing all of its options. Applied
            # here, from the outside, so that a combo added to any tab
            # gets it without having to ask.
            show_all_options_in(self.tabs.widget(i))

        # Per-block help: the TITLE of every relevant QGroupBox is
        # clickable (there is no more "?" button anywhere in the window).
        from .common import make_block_title_clickable
        from PyQt6.QtWidgets import QGroupBox as _QGB
        _BLOCKS: dict[str, str] = {
            # Project tab
            "Operation Mode":                        "operation_mode",
            # Geometry tab
            "Global Geometry":                       "global_geometry",
            "Blade Dynamics":                        "blade_dynamics",
            "Radial Distribution Table":             "radial_table",
            # Airfoil tab
            "Radial Sections":                       "radial_sections",
            "Navigate (r/R, Reynolds, Mach)":        "polar_navigator",
            "Aerodynamic Model":                     "aerodynamic_model",
            "Dynamic Stall":                         "dynamic_stall",
            "Compressibility and Reverse Flow Effects": "local_corrections",
            "Reverse flow":                          "reverse_flow",
            "Compressibility":                       "compressibility",
            "Data import / tabulated polar":         "table_import",
            "Polar Generation via External Engine":  "polar_generation",
            "2D Profile Geometry":                   "profile_2d",
            # Config tab
            "Mesh and atmospheric conditions":       "mesh_atmosphere",
            "Inflow model":                          "inflow",
            "Tip and root loss":                     "tip_root_loss",
            "3D rotational effects":                 "rotational_augmentation",
            "Pitt-Peters (finite-state dynamic inflow)": "pitt_peters",
            "Induced-inflow solver":                 "induction_solver",
            "Adaptive relaxation parameters":        "induction_solver",
            "Early exit":                            "early_exit",
            "Project configuration":                 "project_configuration",
            # Run Case / Run Batch
            "Run Case":                              "run_case",
            "Saved Cases":                           "saved_cases",
            "1. Generate cases":                     "run_batch",
            "Fixed values":                          "batch_fixed_values",
            "2. Case queue":                         "case_queue",
            "3. Run":                                "batch_run",
            "Export":                                "batch_export",
            # Geometry Designer window (opened from the Tools menu; not
            # a tab, but its groupbox titles resolve through this map)
            "Geometry comparison":                   "geometry_comparison",
            # Results tab
            "Results from this session":             "results",
            "Blade dynamics":                        "flap_plots",
            "3D view":                               "view_3d",
        }
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            for gb in tab.findChildren(_QGB):
                block_id = _title_block(_BLOCKS, gb.title())
                if block_id:
                    make_block_title_clickable(gb, block_id)

        # The Geometry Designer is a separate top-level window, but it
        # belongs to the same help system: its groupbox titles resolve
        # through the SAME _BLOCKS map, so a block that moved into the
        # window ("Geometry comparison") keeps its popup.
        self.geometry_designer = GeometryDesignerWindow(self.state, parent=self)
        for gb in self.geometry_designer.findChildren(_QGB):
            block_id = _title_block(_BLOCKS, gb.title())
            if block_id:
                make_block_title_clickable(gb, block_id)
        from .common import (compact_form_fields as _compact,
                             ensure_button_legibility as _legible,
                             ensure_row_spacing as _spacing,
                             align_form_labels as _align,
                             show_all_options_in as _all_options)
        _compact(self.geometry_designer)
        _legible(self.geometry_designer)
        _spacing(self.geometry_designer)
        _align(self.geometry_designer)
        _all_options(self.geometry_designer)

        # kept for the closing prompt (Q7): these are the tabs that know
        # how to distinguish "edited in the form" from "applied to the project"
        self._project_tab = self.tabs.widget(0)
        self._dirty_tabs = ((geometry_tab, "Geometry"), (airfoil_tab, "Airfoil"), (config_tab, "Config/Engine"))

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.flow_bar = FlowIndicatorBar(self.state, self.tabs)
        central_layout.addWidget(self.flow_bar)
        central_layout.addWidget(self.tabs, stretch=1)
        self.setCentralWidget(central)

        self._build_shortcuts()

        self.statusBar().showMessage("Ready.")

    def unsaved_work(self) -> list[str]:
        """What is lost if the window closes now. Geometry/Airfoil/
        Config apply every edit live (no separate "Apply" step), so
        `state.unsaved` is the single source -- the per-tab asterisk
        (`_dirty_tabs`) is just the visual mirror of that same flag, not a
        second layer of risk to add up here."""
        if getattr(self.state, "unsaved", False):
            return ["project: changes applied but not saved to disk"]
        return []

    def closeEvent(self, event):
        """Q7: previously, closing the window silently discarded
        everything -- nothing auto-saves. Today every edit is already in
        `state.project` live (no tab has a separate "Apply" step), so
        "Save" here writes exactly what the user saw on screen."""
        pendencias = self.unsaved_work()
        if not pendencias or self.state.project is None:
            event.accept()
            return
        resposta = QMessageBox.question(
            self, "Save before exit?",
            "There is unsaved work:\n\n  • " + "\n  • ".join(pendencias)
            + "\n\nSave the project before closing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if resposta == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if resposta == QMessageBox.StandardButton.Save:
            self._project_tab._save_project()
        event.accept()

    def _set_tab_dirty(self, index: int, base_name: str, dirty: bool):
        self.tabs.setTabText(index, f"{base_name} *" if dirty else base_name)

    def _build_shortcuts(self):
        """Global shortcuts (docs/plano_v3.md Part 6.4): Ctrl+S saves the
        project, Ctrl+Enter applies the current tab to the project, Ctrl+R
        runs the current tab's case/batch -- via QShortcut, each one
        delegating to the corresponding tab's already-existing method (no
        new execution/persistence logic is created here)."""
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._shortcut_save)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._shortcut_apply)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._shortcut_apply)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._shortcut_run)
        # Ctrl+N / Ctrl+O / Ctrl+1..7: the documentation (Section 0.3)
        # already promised them and they did not exist. Implementing them
        # is cheaper than removing from the documentation a shortcut the
        # user expects.
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._shortcut_new_project)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._shortcut_open_project)
        for i in range(self.tabs.count()):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                       activated=lambda i=i: self.tabs.setCurrentIndex(i))
        # F1 -- same destination as the FlowIndicatorBar's "?" button (docs/documentation.html).
        QShortcut(QKeySequence("F1"), self, activated=lambda: open_help(self))
        # The Tools BUTTON (FlowIndicatorBar, next to Help) replaced the
        # old QMenuBar: under the dark theme the menu bar's dark-gray text
        # on the black strip was effectively invisible, hiding the entry
        # point of the dedicated design windows.
        self.flow_bar.tools_requested.connect(self.open_geometry_designer)

    def open_geometry_designer(self):
        """Shows the non-modal Geometry Designer window, parented to
        this window so it stays on top of it while it is open."""
        window = self.geometry_designer
        window.show()
        window.raise_()
        window.activateWindow()

    def _shortcut_save(self):
        w = self.tabs.widget(0)   # ProjectTab
        if hasattr(w, "_save_project"):
            w._save_project()

    def _shortcut_new_project(self):
        self.tabs.setCurrentIndex(0)
        self._project_tab._new_project()

    def _shortcut_open_project(self):
        self.tabs.setCurrentIndex(0)
        self._project_tab._open_dialog()

    def _shortcut_apply(self):
        w = self.tabs.currentWidget()
        if hasattr(w, "_apply_to_project"):
            w._apply_to_project()
        elif hasattr(w, "_apply_table_edits"):
            w._apply_table_edits()

    def _shortcut_run(self):
        w = self.tabs.currentWidget()
        for method_name in ("_run_case", "_run_batch", "_run_factorial", "_run_saved_batch"):
            btn_name = {"_run_case": "btn_run_case", "_run_batch": "btn_run_batch",
                        "_run_factorial": "btn_run_factorial", "_run_saved_batch": None}.get(method_name)
            if hasattr(w, method_name) and (btn_name is None or getattr(w, btn_name, None) is None
                                              or getattr(w, btn_name).isEnabled()):
                getattr(w, method_name)()
                return


def main():
    QLocale.setDefault(QLocale.c())
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    # Fusion is Qt's flat base (no native OS widgets fighting with the
    # QSS below) -- the recommended starting point whenever a broad QSS
    # like styles.APP_QSS is applied (item 7, docs/plano_v3.md
    # Part 7).
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(max(font.pointSize(), 10))
    app.setFont(font)
    app.setStyleSheet(styles.APP_QSS)
    win = MainWindow()
    # Opens taking up as much screen as possible (item 7: "take up as
    # much screen as possible... may even be fullscreen"), but as a
    # normal maximized window (not showFullScreen(), which removes the
    # OS title/window bar) -- it stays resizable/restorable by the user
    # at any time, which is more predictable for a day-to-day work tool
    # than locking into borderless fullscreen.
    win.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
