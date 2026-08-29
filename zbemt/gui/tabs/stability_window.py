"""Implement the Stability Derivatives window (SC-14).

Three pages, per plan phase 4.4: the trim point, the perturbation set,
and the run with its matrix, bar chart, sign checks and the optional
vehicle block. Every solve runs off the main thread through
`DerivativeWorker` (PR-11); the derivative machinery itself lives in
``derivatives.py`` reached through ``api.compute_derivatives``.
"""

from __future__ import annotations

import math
import time
from dataclasses import replace as dc_replace

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLabel, QLineEdit,
    QCheckBox, QTableWidget, QTableWidgetItem, QTabWidget, QProgressBar,
    QMessageBox, QHeaderView, QInputDialog, QFileDialog, QRadioButton,
    QTextEdit,
)

from ..common import AppState, CanvasHost, show_error, show_all_options_in, in_scroll_area
from ..workers import DerivativeWorker, launch_worker
from ... import api, nomenclature
from ...models import DerivativeRequest, FlightCondition
from ...viz import plots

#: The state/control variables and their display labels, in request order.
#: The SHORT symbol of each perturbation variable, for a heading with
#: no room for the sentence. "Omega" spelled out was a plain-text Greek
#: letter on a user-visible surface, which `PR-4` forbids; the rest of
#: the program has always printed the letter.
_VARIABLE_SYMBOL = {
    "u": "u", "v": "v", "w": "w", "p": "p", "q": "q",
    "Omega": "Ω",
    "theta_0": "θ₀",
    "theta_1c": "θ₁c",
    "theta_1s": "θ₁s",
}

_VARIABLE_UNIT = {
    "u": "m/s", "v": "m/s", "w": "m/s", "p": "rad/s", "q": "rad/s",
    "Omega": "rpm", "theta_0": "deg", "theta_1c": "deg", "theta_1s": "deg",
}

_VARIABLE_LABELS = tuple(
    (key, f"{_VARIABLE_SYMBOL[key]} — {text} [{_VARIABLE_UNIT[key]}]")
    for key, text in (
        ("u", "longitudinal speed"),
        ("v", "lateral speed"),
        ("w", "axial speed"),
        ("p", "roll rate"),
        ("q", "pitch rate"),
        ("Omega", "rotor speed"),
        ("theta_0", "collective"),
        ("theta_1c", "cyclic cosine"),
        ("theta_1s", "cyclic sine"),
    )
)
_STATE_NAMES = ("u", "v", "w", "p", "q", "Omega")
_CONTROL_NAMES = ("theta_0", "theta_1c", "theta_1s")
_OUTPUT_NAMES = ("Thrust", "H", "Y", "Mx_total", "My_total", "Torque")

#: Sign facts a textbook guarantees; the window shows pass/fail so a
#: wrong-sign engine change cannot hide (phase 4.5's spirit, on screen).
#: The damping pairs share an axis: `nomenclature` calls q the rate
#: about the psi=0 axis and M_x,total the tilting moment about that same
#: axis, so the pitch damping is dM_x/dq and the roll damping is
#: dM_y/dp. Pairing q with M_y reads the CROSS term, which on a rotor
#: whose flap response lags by nearly ninety degrees is the larger
#: number and carries no information about damping -- the panel reported
#: a pass while the damping itself was positive (SC-14).
_SIGN_CHECKS = (
    ("Heave damping", "Thrust", "w", -1.0),
    ("Pitch damping", "Mx_total", "q", -1.0),
    ("Roll damping", "My_total", "p", -1.0),
    ("Collective thrust", "Thrust", "theta_0", +1.0),
)


def _save_dialog(parent, default_name: str, kind: str = "csv") -> str:
    if kind == "html":
        path, _f = QFileDialog.getSaveFileName(
            parent, "Save report", default_name, "HTML report (*.html)")
    else:
        path, _f = QFileDialog.getSaveFileName(
            parent, "Save CSV", default_name, "Comma-separated (*.csv)")
    return path


class StabilityWindow(QWidget):
    """Three-page tool: Trim point, Perturbations, Run and results."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Stability Derivatives")
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1150, 760)

        self._worker = None
        self._thread = None
        self._run_started_at = None
        self._outcome = None
        self._last_request = None
        self._vehicle = None

        tabs = QTabWidget(self)
        tabs.addTab(in_scroll_area(self._build_trim_page()), "Trim point")
        tabs.addTab(in_scroll_area(self._build_perturbations_page()), "Perturbations")
        tabs.addTab(in_scroll_area(self._build_run_page()), "Run and results")
        outer = QVBoxLayout(self)
        outer.addWidget(tabs)
        show_all_options_in(self)

        self.state.project_changed.connect(self._refresh_from_project)
        self.state.geometry_changed.connect(lambda: self._refresh_gating())
        self._refresh_from_project()

    # ------------------------------------------------------------------
    # Page 1: Trim point
    # ------------------------------------------------------------------
    def _build_trim_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        left = QVBoxLayout()
        list_box = QGroupBox("Derivative studies stored in this project")
        list_form = QFormLayout(list_box)
        self.study_combo = QComboBox()
        self.study_combo.setToolTip(
            '"derivatives" — the studies persisted with this project in '
            "inputs/derivatives.bemt.")
        self.study_combo.currentIndexChanged.connect(self._on_study_selected)
        list_form.addRow(self.study_combo)
        btn_row = QHBoxLayout()
        for text, handler in (("New", self._new_study),
                              ("Duplicate", self._duplicate_study),
                              ("Rename", self._rename_study),
                              ("Delete", self._delete_study)):
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        list_form.addRow(btn_row)
        left.addWidget(list_box)

        cond_box = QGroupBox("Flight condition")
        cond_form = QFormLayout(cond_box)
        self.condition_combo = QComboBox()
        self.condition_combo.setToolTip(
            '"condition" — the saved case every perturbation flies at. It '
            "must carry an RPM.")
        cond_form.addRow("Saved case:", self.condition_combo)
        self.condition_combo.currentIndexChanged.connect(
            lambda _i: self._show_engine_mapping())
        self.mapping_label = QLabel("")
        self.mapping_label.setWordWrap(True)
        self.mapping_label.setStyleSheet("color: gray;")
        self.mapping_label.setToolTip(
            "How the chosen case reaches the engine: the in-plane speed "
            "becomes mu_x, the axial speed stays Vz, and the three "
            "perturbation inputs ride along.")
        cond_form.addRow(self.mapping_label)
        left.addWidget(cond_box)

        trim_box = QGroupBox("Trim")
        trim_form = QFormLayout(trim_box)
        self.trim_combo = QComboBox()
        self.trim_combo.addItem("None", "none")
        self.trim_combo.addItem("Zero flapping (cyclic)", "cyclic_flapback")
        self.trim_combo.addItem("Thrust", "thrust")
        self.trim_combo.setToolTip(
            '"trim" — fixes the reference controls before any '
            "perturbation. Zero flapping solves both cyclic harmonics so "
            "the blade tip-path plane is level at the trim point; Thrust "
            "solves collective to a target.")
        self.trim_combo.currentIndexChanged.connect(
            lambda _i: self._refresh_gating())
        trim_form.addRow("Mode:", self.trim_combo)
        self.trim_target_spin = QDoubleSpinBox()
        self.trim_target_spin.setRange(0.0, 1e7)
        self.trim_target_spin.setDecimals(2)
        self.trim_target_spin.setValue(0.0)
        self.trim_target_spin.setToolTip(
            "Target thrust [N] of the thrust trim. Leave 0 to use the "
            "untrimmed case's own thrust.")
        trim_form.addRow("Thrust target [N]:", self.trim_target_spin)
        left.addWidget(trim_box)
        left.addStretch(1)
        layout.addLayout(left, 0)

        right = QVBoxLayout()
        run_trim_box = QGroupBox("Check the trim alone")
        rt_layout = QVBoxLayout(run_trim_box)
        self.btn_trim = QPushButton("Run trim only")
        self.btn_trim.setToolTip(
            "Solves just the trim point so it can be judged before paying "
            "for the full derivative sweep.")
        self.btn_trim.clicked.connect(self._run_trim_only)
        rt_layout.addWidget(self.btn_trim)
        self.trim_result = QTextEdit()
        self.trim_result.setReadOnly(True)
        rt_layout.addWidget(self.trim_result, 1)
        right.addWidget(run_trim_box, 1)

        valid_box = QGroupBox("Validation")
        valid_layout = QVBoxLayout(valid_box)
        self.validation_panel = QTextEdit()
        self.validation_panel.setReadOnly(True)
        valid_layout.addWidget(self.validation_panel)
        right.addWidget(valid_box, 1)
        layout.addLayout(right, 1)
        return page

    # ------------------------------------------------------------------
    # Page 2: Perturbations
    # ------------------------------------------------------------------
    def _build_perturbations_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        states_box = QGroupBox("States")
        states_grid = QGridLayout(states_box)
        self.var_checks = {}
        row = 0
        for name, label in _VARIABLE_LABELS:
            if name in _STATE_NAMES:
                check = QCheckBox(label)
                check.setChecked(name in ("w", "q", "theta_0"))
                check.toggled.connect(self._refresh_step_table)
                check.toggled.connect(self._update_cost_estimate)
                states_grid.addWidget(check, row, 0)
                self.var_checks[name] = check
                row += 1
        layout.addWidget(states_box, 0)

        controls_box = QGroupBox("Controls")
        controls_grid = QGridLayout(controls_box)
        row = 0
        for name, label in _VARIABLE_LABELS:
            if name in _CONTROL_NAMES:
                check = QCheckBox(label)
                check.setChecked(name == "theta_0")
                check.toggled.connect(self._refresh_step_table)
                check.toggled.connect(self._update_cost_estimate)
                controls_grid.addWidget(check, row, 0)
                self.var_checks[name] = check
                row += 1
        layout.addWidget(controls_box, 0)

        outputs_box = QGroupBox("Outputs")
        outputs_grid = QGridLayout(outputs_box)
        self.output_checks = {}
        for i, name in enumerate(_OUTPUT_NAMES):
            # The LABEL is the rendered symbol; the engine key stays the
            # dictionary key, so `_collect_request` is untouched.
            check = QCheckBox(self._symbol(name))
            check.setToolTip(f'"{name}" — the engine key this column '
                              f"carries in the CSV and the report.")
            check.setChecked(True)
            outputs_grid.addWidget(check, i % 3, i // 3)
            self.output_checks[name] = check
        layout.addWidget(outputs_box, 0)

        right = QVBoxLayout()
        steps_box = QGroupBox("Steps (per variable, its own unit)")
        steps_layout = QVBoxLayout(steps_box)
        self.steps_table = QTableWidget(0, 2)
        self.steps_table.setHorizontalHeaderLabels(["Variable", "Step"])
        self.steps_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.steps_table.setToolTip(
            "Central differences trade truncation error, which grows "
            "with the square of the step, against round-off, which grows "
            "as the step shrinks. Each quantity gets its own stated step; "
            "the Richardson check repeats at half of it.")
        steps_layout.addWidget(self.steps_table)
        right.addWidget(steps_box, 1)

        options_box = QGroupBox("Options")
        options_form = QFormLayout(options_box)
        self.richardson_check = QCheckBox("Richardson half-step check")
        self.richardson_check.setChecked(True)
        self.richardson_check.toggled.connect(self._update_cost_estimate)
        options_form.addRow(self.richardson_check)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 64)
        self.workers_spin.setValue(1)
        self.workers_spin.setToolTip(
            "Requested evaluation processes; stored on the study. This "
            "build evaluates serially.")
        options_form.addRow("Parallel workers:", self.workers_spin)
        right.addWidget(options_box)

        cost_box = QGroupBox("Cost estimate")
        cost_layout = QVBoxLayout(cost_box)
        self.cost_label = QLabel("-")
        self.cost_label.setWordWrap(True)
        cost_layout.addWidget(self.cost_label)
        right.addWidget(cost_box)
        layout.addLayout(right, 1)
        return page

    # ------------------------------------------------------------------
    # Page 3: Run and results
    # ------------------------------------------------------------------
    def _build_run_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        run_row = QHBoxLayout()
        self.btn_run = QPushButton("Run derivatives")
        self.btn_run.clicked.connect(self._run)
        run_row.addWidget(self.btn_run)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel)
        run_row.addWidget(self.btn_cancel)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        run_row.addWidget(self.progress, 1)
        self.elapsed_label = QLabel("")
        run_row.addWidget(self.elapsed_label)
        layout.addLayout(run_row)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        mid = QHBoxLayout()
        matrix_box = QGroupBox("Derivative matrix")
        matrix_layout = QVBoxLayout(matrix_box)
        unit_row = QHBoxLayout()
        self.radio_dim = QRadioButton("Dimensional")
        self.radio_dim.setChecked(True)
        self.radio_dim.toggled.connect(self._refresh_matrix)
        self.radio_nondim = QRadioButton("Non-dimensional")
        self.radio_nondim.toggled.connect(self._refresh_matrix)
        unit_row.addWidget(self.radio_dim)
        unit_row.addWidget(self.radio_nondim)
        unit_row.addStretch(1)
        matrix_layout.addLayout(unit_row)
        self.matrix_table = QTableWidget(0, 0)
        self.matrix_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.matrix_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        matrix_layout.addWidget(self.matrix_table)
        mid.addWidget(matrix_box, 3)

        side = QVBoxLayout()
        sign_box = QGroupBox("Sign checks")
        sign_layout = QVBoxLayout(sign_box)
        self.sign_panel = QLabel("Run first.")
        self.sign_panel.setWordWrap(True)
        sign_layout.addWidget(self.sign_panel)
        side.addWidget(sign_box)

        vehicle_box = QGroupBox("Vehicle model (optional)")
        vehicle_layout = QVBoxLayout(vehicle_box)
        self.vehicle_check = QCheckBox("Build the rigid-body A/B matrices")
        self.vehicle_check.setToolTip(
            "One rotor only: no fuselage, no tail, no engine dynamics. "
            "Needs the speeds u/v/w and the rates p/q plus rotor speed among the states.")
        self.vehicle_check.setEnabled(False)
        self.vehicle_check.toggled.connect(self._refresh_vehicle)
        vehicle_layout.addWidget(self.vehicle_check)
        form = QFormLayout()
        self.mass_spin = self._spin(1.0, 1e6, 100.0, 1, "kg")
        self.ix_spin = self._spin(0.01, 1e7, 50.0, 1, "kg*m2")
        self.iy_spin = self._spin(0.01, 1e7, 80.0, 1, "kg*m2")
        self.iz_spin = self._spin(0.01, 1e7, 20.0, 1, "kg*m2")
        # The hub arm is what turns a hub FORCE into a moment about the
        # centre of gravity. It was not offered at all, so every matrix
        # was built with a zero arm -- a real modelling choice presented
        # as an absence.
        self.hub_x_spin = self._spin(-20.0, 20.0, 0.0, 3, "m")
        self.hub_z_spin = self._spin(-20.0, 20.0, 0.0, 3, "m")
        self.gravity_spin = self._spin(0.0, 30.0, 9.81, 3, "m/s2")
        rows = (("Mass [kg]:", self.mass_spin),
                 (nomenclature.to_html(r"$I_x$") + " [kg\u00b7m\u00b2]:",
                  self.ix_spin),
                 (nomenclature.to_html(r"$I_y$") + " [kg\u00b7m\u00b2]:",
                  self.iy_spin),
                 (nomenclature.to_html(r"$I_z$") + " [kg\u00b7m\u00b2]:",
                  self.iz_spin),
                 ("Hub ahead of the CG [m]:", self.hub_x_spin),
                 ("Hub above the CG [m]:", self.hub_z_spin),
                 (nomenclature.to_html(r"$g$") + " [m/s\u00b2]:",
                  self.gravity_spin))
        for label, w in rows:
            form.addRow(label, w)
        vehicle_layout.addLayout(form)
        self.eigen_canvas = CanvasHost()
        vehicle_layout.addWidget(self.eigen_canvas)
        side.addWidget(vehicle_box, 1)
        mid.addLayout(side, 2)
        layout.addLayout(mid, 3)

        bottom = QHBoxLayout()
        bar_box = QGroupBox("Bar chart — one output across variables")
        bar_layout = QHBoxLayout(bar_box)
        self.bar_output_combo = QComboBox()
        for name in _OUTPUT_NAMES:
            # Rendered text, engine key as the item's data: reading the
            # TEXT back would make the chart depend on how it is spelled.
            self.bar_output_combo.addItem(self._symbol(name), name)
        self.bar_output_combo.currentIndexChanged.connect(
            self._refresh_bar_chart)
        bar_layout.addWidget(self.bar_output_combo)
        self.bar_canvas = CanvasHost()
        bar_layout.addWidget(self.bar_canvas, 1)
        bottom.addWidget(bar_box, 2)

        export_box = QGroupBox("Export")
        export_layout = QVBoxLayout(export_box)
        btn_csv = QPushButton("Export CSV")
        btn_csv.clicked.connect(self._export_csv)
        export_layout.addWidget(btn_csv)
        btn_report = QPushButton("Export report")
        btn_report.clicked.connect(self._export_report)
        export_layout.addWidget(btn_report)
        export_layout.addStretch(1)
        bottom.addWidget(export_box, 1)
        layout.addLayout(bottom, 2)
        return page

    @staticmethod
    def _spin(lo, hi, value, decimals, tip_unit):
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(decimals)
        spin.setValue(value)
        spin.setToolTip(f"In {tip_unit}.")
        return spin

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------
    def _refresh_from_project(self):
        project = self.state.project
        self.study_combo.blockSignals(True)
        self.study_combo.clear()
        if project:
            for d in project.derivatives:
                self.study_combo.addItem(d.name)
        self.study_combo.blockSignals(False)
        self.condition_combo.blockSignals(True)
        self.condition_combo.clear()
        if project:
            for case in project.saved_cases:
                label = f"{case.name}"
                if case.rpm:
                    label += f" ({float(case.rpm):g} rpm)"
                self.condition_combo.addItem(label)
        self.condition_combo.blockSignals(False)
        if project and project.derivatives:
            self._fill_editor(project.derivatives[0])
        self._refresh_gating()
        self._refresh_step_table()
        self._update_cost_estimate()
        self._update_validation_panel()

    def _show_engine_mapping(self):
        """Point 5 of the diagnosis: makes the u/v/w -> engine mapping
        VISIBLE, so the user sees what a derivative perturbs."""
        condition = self._condition_by_index(
            max(self.condition_combo.currentIndex(), 0))
        if condition is None:
            self.mapping_label.setText("")
            return
        self.mapping_label.setText(
            f"Engine view: mu_x={float(condition.mu_x):g} · "
            f"Vz={float(condition.Vz):g} m/s · "
            f"ψw={float(getattr(condition, 'sideslip_deg', 0.0) or 0.0):g}° · "
            f"p={float(getattr(condition, 'p_rate_deg_s', 0.0) or 0.0):g}°/s · "
            f"q={float(getattr(condition, 'q_rate_deg_s', 0.0) or 0.0):g}°/s · "
            f"{float(condition.rpm or 0):g} rpm")

    def _selected_persisted(self):
        project = self.state.project
        idx = self.study_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.derivatives):
            return None
        return project.derivatives[idx]

    def _on_study_selected(self, _index: int):
        definition = self._selected_persisted()
        if definition is not None:
            self._fill_editor(definition)

    def _condition_by_index(self, index: int):
        project = self.state.project
        if project is None or not (0 <= index < len(project.saved_cases)):
            return None
        return dc_replace(project.saved_cases[index])

    def _current_request(self) -> DerivativeRequest:
        states = [n for n in _STATE_NAMES
                   if self.var_checks[n].isChecked()]
        controls = [n for n in _CONTROL_NAMES
                     if self.var_checks[n].isChecked()]
        outputs = [n for n in _OUTPUT_NAMES
                    if self.output_checks[n].isChecked()]
        steps = {}
        for r, (name, _label) in enumerate(
                (v for v in _VARIABLE_LABELS
                 if self.var_checks[v[0]].isChecked())):
            item = self.steps_table.item(r, 1)
            try:
                value = float(item.text()) if item else float("nan")
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value > 0:
                steps[name] = value
        condition = self._condition_by_index(
            max(self.condition_combo.currentIndex(), 0))
        return DerivativeRequest(
            name=(self.study_combo.currentText() or "derivatives 1"),
            condition=condition,
            trim=self.trim_combo.currentData(),
            trim_target_thrust=(self.trim_target_spin.value()
                                 if self.trim_target_spin.value() > 0
                                 else None),
            states=states, controls=controls, outputs=outputs,
            steps=steps, richardson_check=self.richardson_check.isChecked(),
            parallel_workers=self.workers_spin.value(),
            # The rigid-body block travels WITH the study. Left in the
            # spin boxes it was a session value: absent from the `.bemt`
            # file, unreachable from the CLI, and gone when the window
            # closed, although it decides every eigenvalue drawn beside
            # it (`PA-3`).
            vehicle_enabled=self.vehicle_check.isChecked(),
            vehicle_mass_kg=self.mass_spin.value(),
            vehicle_Ix_kg_m2=self.ix_spin.value(),
            vehicle_Iy_kg_m2=self.iy_spin.value(),
            vehicle_Iz_kg_m2=self.iz_spin.value(),
            hub_offset_x_m=self.hub_x_spin.value(),
            hub_offset_z_m=self.hub_z_spin.value(),
            gravity_m_s2=self.gravity_spin.value())

    def _fill_editor(self, request: DerivativeRequest):
        for name in _STATE_NAMES + _CONTROL_NAMES:
            self.var_checks[name].setChecked(
                name in (*request.states, *request.controls))
        for name in _OUTPUT_NAMES:
            self.output_checks[name].setChecked(name in request.outputs)
        idx = self.trim_combo.findData(request.trim or "cyclic_flapback")
        self.trim_combo.setCurrentIndex(max(idx, 0))
        self.richardson_check.setChecked(bool(request.richardson_check))
        self.workers_spin.setValue(int(max(request.parallel_workers, 1)))
        # `getattr` with the dataclass default, so a study written before
        # these fields existed loads without a migration step.
        self.vehicle_check.setChecked(
            bool(getattr(request, "vehicle_enabled", False)))
        for spin, attribute, fallback in (
                (self.mass_spin, "vehicle_mass_kg", 100.0),
                (self.ix_spin, "vehicle_Ix_kg_m2", 50.0),
                (self.iy_spin, "vehicle_Iy_kg_m2", 80.0),
                (self.iz_spin, "vehicle_Iz_kg_m2", 20.0),
                (self.hub_x_spin, "hub_offset_x_m", 0.0),
                (self.hub_z_spin, "hub_offset_z_m", 0.0),
                (self.gravity_spin, "gravity_m_s2", 9.81)):
            spin.setValue(float(getattr(request, attribute, fallback)))
        if request.condition is not None and self.state.project:
            for i, case in enumerate(self.state.project.saved_cases):
                if case.name == request.condition.name:
                    self.condition_combo.setCurrentIndex(i)
                    break
        self._refresh_step_table(force=request.steps)

    def state_notify(self):
        project = self.state.project
        idx = self.study_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.derivatives):
            return
        project.derivatives[idx] = self._current_request()

    def _refresh_gating(self):
        has_project = self.state.project is not None
        self.btn_run.setEnabled(has_project)
        self.btn_trim.setEnabled(has_project)
        rigid = False
        project = self.state.project
        if project:
            rigid = project.geometry.dynamics.flap_model == "rigid"
        # PR-2: real-but-inapplicable stays visible and disabled.
        flapback_index = self.trim_combo.findData("cyclic_flapback")
        self.trim_combo.model().item(flapback_index).setEnabled(not rigid)
        if rigid and self.trim_combo.currentData() == "cyclic_flapback":
            self.trim_combo.setCurrentIndex(
                self.trim_combo.findData("none"))
        for name in ("p", "q", "theta_1c", "theta_1s"):
            check = self.var_checks[name]
            check.setEnabled(not rigid)
            tooltip = "" if not rigid else (
                "Disabled: the blade has no flap freedom, so this "
                "rate/control cannot act on it.")
            check.setToolTip(tooltip)

    # ------------------------------------------------------------------
    # Steps / cost / validation
    # ------------------------------------------------------------------
    def _selected_variables(self):
        return [name for name, _label in _VARIABLE_LABELS
                 if self.var_checks[name].isChecked()]

    def _default_steps(self):
        from zbemt.derivatives import (_DEFAULT_STEPS,
                                        _OMEGA_STEP_FRACTION)
        project = self.state.project
        rpm = 600.0
        if project and project.saved_cases:
            first = project.saved_cases[0]
            rpm = float(first.rpm or 600.0)
        defaults = dict(_DEFAULT_STEPS)
        defaults["Omega"] = _OMEGA_STEP_FRACTION * rpm
        return defaults

    def _refresh_step_table(self, force=None):
        """Rebuilds the per-variable step table.

        ``force`` is the saved study's own steps, when there are any.
        This method is ALSO a slot of ``QCheckBox.toggled``, which
        delivers a bool -- so anything that is not a mapping means "no
        saved steps, use the defaults". Reading the bool as a mapping
        raised `AttributeError` inside a slot, and PyQt turns an
        unhandled exception in a slot into an abort: ticking any
        variable took the whole application down (`PR-11`).
        """
        defaults = self._default_steps()
        selected = force if isinstance(force, dict) else {}
        rows = [(name, label) for name, label in _VARIABLE_LABELS
                 if self.var_checks[name].isChecked()]
        self.steps_table.setRowCount(len(rows))
        for r, (name, label) in enumerate(rows):
            self.steps_table.setItem(r, 0, QTableWidgetItem(label))
            value = selected.get(name, defaults.get(name, ""))
            item = QTableWidgetItem(f"{float(value):g}")
            self.steps_table.setItem(r, 1, item)
        self._update_cost_estimate()

    def _update_cost_estimate(self, *_args):
        n_vars = len(self._selected_variables())
        per_var = 4 if self.richardson_check.isChecked() else 2
        total = n_vars * per_var + 1
        seconds = self._timed_evaluation_seconds()
        if seconds is not None:
            minutes = total * seconds / 60.0
            self.cost_label.setText(
                f"{n_vars} variables x {per_var} solves + 1 trim point "
                f"= about {total} solver calls (~{minutes:.0f} min at "
                f"the measured {seconds:.2f} s/solve).")
        else:
            self.cost_label.setText(
                f"{n_vars} variables x {per_var} solves + 1 trim point "
                f"= about {total} solver calls.")

    def _timed_evaluation_seconds(self):
        import time as _time
        project = self.state.project
        condition = self._condition_by_index(
            max(self.condition_combo.currentIndex(), 0))
        if project is None or condition is None or not condition.rpm:
            return None
        try:
            start = _time.perf_counter()
            api.run_case(project, condition)
            return _time.perf_counter() - start
        except Exception:
            return None

    def _update_validation_panel(self):
        issues = []
        project = self.state.project
        if project:
            issues = api.validate_project(project)
        self.validation_panel.setPlainText(
            "\n".join(str(i) for i in issues) if issues
            else "No findings.")

    # ------------------------------------------------------------------
    # Study list handlers
    # ------------------------------------------------------------------
    def _new_study(self):
        project = self.state.project
        if project is None:
            return
        name, ok = QInputDialog.getText(self, "New derivative study",
                                         "Name:")
        if not ok or not name.strip():
            return
        request = DerivativeRequest(
            name=name.strip(),
            condition=self._condition_by_index(0),
            trim="cyclic_flapback",
            states=["w"], controls=["theta_0"],
            outputs=list(_OUTPUT_NAMES))
        project.derivatives.append(request)
        self.study_combo.blockSignals(True)
        self.study_combo.addItem(request.name)
        self.study_combo.setCurrentIndex(self.study_combo.count() - 1)
        self.study_combo.blockSignals(False)
        self._fill_editor(request)
        self.state.notify_geometry()

    def _duplicate_study(self):
        source = self._current_request()
        new_name, ok = QInputDialog.getText(
            self, "Duplicate study", "Name:", text=source.name + " copy")
        if not ok or not new_name.strip():
            return
        project = self.state.project
        if project is None:
            return
        copy = dc_replace(source, name=new_name.strip())
        project.derivatives.append(copy)
        self.study_combo.blockSignals(True)
        self.study_combo.addItem(copy.name)
        self.study_combo.setCurrentIndex(self.study_combo.count() - 1)
        self.study_combo.blockSignals(False)
        self.state.notify_geometry()

    def _rename_study(self):
        old = self._selected_persisted()
        if old is None:
            return
        new_name, ok = QInputDialog.getText(self, "Rename study",
                                             "Name:", text=old.name)
        if not ok or not new_name.strip():
            return
        old.name = new_name.strip()
        idx = self.study_combo.currentIndex()
        self.study_combo.setItemText(idx, old.name)
        self.state.notify_geometry()

    def _delete_study(self):
        project = self.state.project
        idx = self.study_combo.currentIndex()
        if project is None or idx < 0 or idx >= len(project.derivatives):
            return
        confirm = QMessageBox.question(
            self, "Delete study",
            f"Delete study {project.derivatives[idx].name!r}?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        del project.derivatives[idx]
        self.study_combo.blockSignals(True)
        self.study_combo.removeItem(idx)
        self.study_combo.blockSignals(False)
        self.state.notify_geometry()
        self._refresh_from_project()

    # ------------------------------------------------------------------
    # Run page
    # ------------------------------------------------------------------
    def _run_trim_only(self):
        project = self.state.project
        if project is None:
            return
        self.state_notify()
        request = self._current_request()
        try:
            outcome = api.compute_derivatives(
                project, dc_replace(request, states=[], controls=[],
                                     richardson_check=False))
        except Exception as exc:
            show_error(self, "Error running trim", exc)
            return
        lines = [f"{k}: {v:.6g}" for k, v in outcome.trim_state.items()]
        self.trim_result.setPlainText("\n".join(lines))

    def _run(self):
        project = self.state.project
        if project is None:
            return
        self.state_notify()
        request = self._current_request()
        if not (*request.states, *request.controls):
            QMessageBox.information(
                self, "Nothing to perturb",
                "Select at least one state or control on the Perturbations "
                "page.")
            return
        self._last_request = request
        self.vehicle_check.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.message_label.setText("")
        self._run_started_at = time.time()
        self._worker = DerivativeWorker(project, request)
        self._thread = launch_worker(self._worker)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(lambda msg: show_error(
            self, "Error running derivatives", RuntimeError(msg)))

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)

    def _on_progress(self, done: int, total: int):
        elapsed = time.time() - (self._run_started_at or time.time())
        self.elapsed_label.setText(f"{elapsed:.1f}s - {done}/{total}")

    def _on_finished(self, outcome):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.progress.setVisible(False)
        self._outcome = outcome
        if outcome is None:
            return
        self.message_label.setText(outcome.message)
        variables = sorted({v for (_k, v) in outcome.matrix})
        keys = sorted({k for (k, _v) in outcome.matrix})
        # The engine keys are kept HERE, and only the symbols are shown.
        # Reading the key back out of the header text -- as this window
        # used to -- is what forced the raw `Mx_total` and `theta_0` on
        # screen: the moment the heading became readable, the lookup
        # broke (`PR-4`, `PR-8`).
        self._matrix_keys = keys
        self._matrix_variables = variables
        self.matrix_table.setColumnCount(1 + len(variables))
        self.matrix_table.setHorizontalHeaderLabels(
            ["Output", *(self._symbol(v) for v in variables)])
        self.matrix_table.setRowCount(len(keys))
        self.matrix_table.setVerticalHeaderLabels(
            [self._symbol(k) for k in keys])
        self._refresh_matrix()
        self._refresh_sign_checks(outcome)
        needed = {"u", "v", "w", "p", "q", "Omega"}
        self.vehicle_check.setEnabled(needed <= set(request_states(outcome)))
        self._refresh_bar_chart()

    def _condition_caption(self) -> str:
        """The flight condition a plot in this window was produced at.

        Every plot title must state it (the repository's plot rule): a
        stability derivative is a slope AT a point, and the same rotor
        gives different numbers at another one, so a chart that does not
        name its point cannot be compared with anything.
        """
        outcome = getattr(self, "_outcome", None)
        condition = getattr(outcome, "condition", None)
        if condition is None:
            index = self.condition_combo.currentIndex()
            cases = (self.state.project.saved_cases
                     if self.state and self.state.project else [])
            if 0 <= index < len(cases):
                condition = cases[index]
        if condition is None:
            return "condition not recorded"
        from ..common import describe_case_settings
        try:
            return describe_case_settings(
                {"mu_x": condition.mu_x, "Vz": condition.Vz,
                 "collective_deg": condition.collective_deg,
                 "rpm": condition.rpm})
        except Exception:
            return str(getattr(condition, "name", "") or "condition")

    def _symbol(self, engine_key: str) -> str:
        """The name the rest of the program shows for this quantity, in
        the project's own axis convention.

        The OUTPUTS are engine keys that `nomenclature` knows. The
        perturbation VARIABLES are not -- `theta_0` is a control of this
        window, not a summary column -- so they carry their own short
        symbols above."""
        if engine_key in _VARIABLE_SYMBOL:
            return f"{_VARIABLE_SYMBOL[engine_key]} [{_VARIABLE_UNIT[engine_key]}]"
        propeller = bool(self.state.is_propeller()) if self.state else False
        symbol = nomenclature.symbol_text(engine_key, propeller)
        unit = nomenclature.unit(engine_key)
        return f"{symbol} [{unit}]" if unit and unit != "-" else symbol

    def _refresh_matrix(self):
        outcome = self._outcome
        if outcome is None:
            return
        values = (outcome.matrix_nondim if self.radio_nondim.isChecked()
                   else outcome.matrix)
        for r, key in enumerate(getattr(self, "_matrix_keys", [])):
            for c, variable in enumerate(
                    getattr(self, "_matrix_variables", []), start=1):
                value = values.get((key, variable), "")
                text = (f"{float(value):.5g}"
                         if isinstance(value, (int, float)) else str(value))
                item = QTableWidgetItem(text)
                error = outcome.step_error.get((key, variable))
                if isinstance(error, float) and error > 0.05:
                    item.setForeground(QColor("#b00000"))
                    item.setToolTip(
                        f"step-size error {error:.1%}: trust the trend, "
                        "not the digits; a larger step usually helps.")
                elif isinstance(error, float):
                    item.setToolTip(f"step-size error {error:.2%}\n"
                                     f"step h = "
                                     f"{outcome.step_used.get(variable, ''):g}")
                self.matrix_table.setItem(r, c, item)

    def _refresh_sign_checks(self, outcome):
        lines = []
        for label, output, variable, wanted in _SIGN_CHECKS:
            value = outcome.matrix.get((output, variable))
            if value is None or not math.isfinite(float(value)):
                lines.append(f"{label}: n/a")
                continue
            ok = (value < 0.0) if wanted < 0 else (value > 0.0)
            mark = "PASS" if ok else "FAIL"
            lines.append(f"{label}: {mark} ({value:+.4g})")
        self.sign_panel.setText("\n".join(lines))

    def _refresh_bar_chart(self):
        outcome = self._outcome
        canvas = self.bar_canvas.use_simple()
        canvas.clear()
        if outcome is None:
            canvas.ax.text(0.5, 0.5, "Run first.", ha="center",
                            va="center", fontsize=10, color="0.35",
                            transform=canvas.ax.transAxes)
            canvas.draw()
            return
        chosen = self.bar_output_combo.currentData()
        if chosen is None:                      # nothing selected yet
            chosen = self.bar_output_combo.currentText()
        pairs = {(k, v): val for (k, v), val in outcome.matrix.items()
                  if k == chosen}
        names = list(dict.fromkeys(v for (_k, v) in pairs))
        if not names:
            canvas.draw()
            return
        values = [pairs[(chosen, n)] for n in names]
        colors = ["tab:red" if abs(v) == max(abs(x) for x in values)
                   else "tab:blue" for v in values]
        canvas.ax.bar(range(len(names)), values, color=colors)
        canvas.ax.set_xticks(range(len(names)))
        canvas.ax.set_xticklabels([self._symbol(n) for n in names],
                                   fontsize=8)
        canvas.ax.axhline(0.0, color="0.3", linewidth=0.8)
        # The condition belongs in the title: a derivative is a slope AT
        # a point, and the same rotor gives different numbers at another
        # one. This is the repository's rule for every plot.
        canvas.ax.set_title(
            f"∂{self._symbol(chosen)} / ∂(variable)\n"
            f"{self._condition_caption()}", fontsize=9)
        canvas.draw()

    def _refresh_vehicle(self):
        outcome = self._outcome
        canvas = self.eigen_canvas.use_simple()
        canvas.clear()
        if not (self.vehicle_check.isChecked() and outcome is not None):
            canvas.draw()
            return
        try:
            built = api.vehicle_matrices(
                outcome, mass=self.mass_spin.value(),
                Ix=self.ix_spin.value(), Iy=self.iy_spin.value(),
                Iz=self.iz_spin.value(),
                hub_offset=(self.hub_x_spin.value(), 0.0,
                             self.hub_z_spin.value()),
                g=self.gravity_spin.value())
        except Exception as exc:
            canvas.ax.text(0.5, 0.5, f"Cannot build: {exc}",
                            ha="center", va="center", fontsize=9,
                            color="0.35", transform=canvas.ax.transAxes)
            canvas.draw()
            return
        self._vehicle = built
        eigs = built["eigenvalues"]
        plots.plot_eigenvalues(eigs, ax=canvas.ax)
        canvas.draw()

    def _export_csv(self):
        if self._outcome is None:
            QMessageBox.information(self, "Nothing to export",
                                     "Run the derivatives first.")
            return
        path, _filter = _save_dialog(self, "derivatives.csv")
        if not path:
            return
        api.export_derivatives_csv(self._outcome, path)
        QMessageBox.information(self, "Exported", f"File written:\n{path}")

    def _export_report(self):
        if self._outcome is None:
            QMessageBox.information(self, "Nothing to export",
                                     "Run the derivatives first.")
            return
        path, _filter = _save_dialog(self, "derivatives_report.html",
                                      "html")
        if not path:
            return
        api.generate_derivatives_report(self._outcome, path,
                                         project=self.state.project,
                                         request=self._last_request)
        QMessageBox.information(self, "Exported", f"Report written:\n{path}")


def request_states(outcome) -> tuple:
    """Variables present on an outcome, whatever produced it."""
    return tuple({v for (_k, v) in outcome.matrix})

